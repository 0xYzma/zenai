"""
Result Processor — Pandas-based tiered summarization + deterministic chart data.

Per PRD §5.5 and §6:
- Tiered strategy: ≤50 rows → full; 51-500 → stats + top/bottom 10; >500 → aggregates + sampled
- Chart data generated deterministically by Pandas, never by the LLM
- Gemini only recommends chart TYPE, never chart DATA
"""
import pandas as pd
import json
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ProcessedResult:
    summary: dict
    chart_data: Optional[list] = None
    chart_type: str = "none"
    full_data: list = field(default_factory=list)
    row_count: int = 0


def process_result(
    columns: list[str],
    rows: list[dict],
    question: str = "",
) -> ProcessedResult:
    """
    Process raw query results into tiered summaries + deterministic chart data.

    Per PRD §6.1 tiered strategy:
    - ≤50 rows: send full result
    - 51-500 rows: summary stats + top/bottom 10
    - >500 rows: aggregates, trends, outliers + sampled top/bottom 10
    §6.2: question-aware summarization
    """
    if not rows:
        return ProcessedResult(
            summary={"rows": 0, "message": "No results found"},
            full_data=[],
            row_count=0,
        )

    df = pd.DataFrame(rows, columns=columns)
    row_count = len(df)

    # Build tiered summary (§6.2: question-aware)
    summary = _build_summary(df, row_count, question)

    # Deterministic chart data generation
    chart_data, chart_type = _generate_chart_data(df, question)

    return ProcessedResult(
        summary=summary,
        chart_data=chart_data,
        chart_type=chart_type,
        full_data=rows[:2000],  # Full data for download
        row_count=row_count,
    )


def _build_summary(df: pd.DataFrame, row_count: int, question: str = "") -> dict:
    """Build a tiered summary based on result size. §6.2: question-aware."""
    summary = {"rows": row_count}

    # §6.2: Question-aware facts
    q_lower = question.lower()
    is_revenue = any(w in q_lower for w in ["revenue", "sales", "income", "money", "total"])
    is_ranking = any(w in q_lower for w in ["top", "most", "highest", "best", "rank", "least", "lowest", "worst"])
    is_time = any(w in q_lower for w in ["daily", "weekly", "monthly", "trend", "over time", "each day", "each week"])
    is_comparison = any(w in q_lower for w in ["compare", "vs", "versus", "difference", "growth", "change"])

    if row_count <= 50:
        summary["tier"] = "full"
        summary["data"] = _serialize_df(df).to_dict(orient="records")

    elif row_count <= 500:
        summary["tier"] = "stats"
        summary["numeric_stats"] = _get_numeric_stats(df)
        summary["top10"] = _get_top_bottom(df, "top", 10)
        summary["bottom10"] = _get_top_bottom(df, "bottom", 10)

    else:
        summary["tier"] = "aggregates"
        summary["numeric_stats"] = _get_numeric_stats(df)
        summary["top10"] = _get_top_bottom(df, "top", 10)
        summary["bottom10"] = _get_top_bottom(df, "bottom", 10)
        summary["outliers"] = _get_outliers(df)

    # §6.2: Compute question-specific facts
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    string_cols = df.select_dtypes(include=["object"]).columns.tolist()

    if is_revenue and numeric_cols:
        col = numeric_cols[0]
        summary["question_facts"] = {
            "total": round(float(df[col].sum()), 2),
            "average": round(float(df[col].mean()), 2),
            "min": round(float(df[col].min()), 2),
            "max": round(float(df[col].max()), 2),
        }
    elif is_ranking and numeric_cols and string_cols:
        cat_col = string_cols[0]
        val_col = numeric_cols[0]
        top = df.nlargest(5, val_col)
        summary["question_facts"] = {
            "top_entities": top[[cat_col, val_col]].to_dict(orient="records"),
            "leader": top.iloc[0][cat_col] if len(top) > 0 else None,
        }
    elif is_time and len(numeric_cols) >= 1:
        col = numeric_cols[0]
        if len(df) >= 2:
            first_val = float(df[col].iloc[0])
            last_val = float(df[col].iloc[-1])
            change_pct = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0
            summary["question_facts"] = {
                "first_value": round(first_val, 2),
                "last_value": round(last_val, 2),
                "change_pct": round(change_pct, 1),
                "trend": "increasing" if change_pct > 0 else "decreasing" if change_pct < 0 else "flat",
            }
    elif is_comparison and numeric_cols:
        col = numeric_cols[0]
        if len(df) >= 2:
            summary["question_facts"] = {
                "values": df[col].tolist()[:10],
                "total": round(float(df[col].sum()), 2),
            }

    return summary


def _get_numeric_stats(df: pd.DataFrame) -> dict:
    """Get summary statistics for numeric columns."""
    stats = {}
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    for col in numeric_cols:
        col_stats = {
            "mean": round(float(df[col].mean()), 2) if not df[col].isna().all() else None,
            "median": round(float(df[col].median()), 2) if not df[col].isna().all() else None,
            "std": round(float(df[col].std()), 2) if not df[col].isna().all() and len(df) > 1 else None,
            "min": round(float(df[col].min()), 2) if not df[col].isna().all() else None,
            "max": round(float(df[col].max()), 2) if not df[col].isna().all() else None,
            "sum": round(float(df[col].sum()), 2) if not df[col].isna().all() else None,
            "count": int(df[col].count()),
        }
        stats[col] = col_stats

    return stats


def _get_top_bottom(df: pd.DataFrame, direction: str, n: int) -> list[dict]:
    """Get top or bottom N rows by the first numeric column."""
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return _serialize_df(df.head(n)).to_dict(orient="records") if direction == "top" else _serialize_df(df.tail(n)).to_dict(orient="records")

    sort_col = numeric_cols[0]
    if direction == "top":
        result = df.nlargest(n, sort_col)
    else:
        result = df.nsmallest(n, sort_col)

    return _serialize_df(result).to_dict(orient="records")


def _get_outliers(df: pd.DataFrame) -> list[dict]:
    """Get outliers (>2 std from mean) for numeric columns."""
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols or len(df) < 3:
        return []

    outlier_rows = []
    for col in numeric_cols:
        if df[col].std() == 0 or df[col].isna().all():
            continue
        mean = df[col].mean()
        std = df[col].std()
        outliers = df[(df[col] < mean - 2 * std) | (df[col] > mean + 2 * std)]
        if not outliers.empty:
            outlier_rows.extend(_serialize_df(outliers.head(5)).to_dict(orient="records"))

    return outlier_rows


def _serialize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convert DataFrame to JSON-serializable format."""
    result = df.copy()
    for col in result.columns:
        if result[col].dtype == "datetime64[ns]" or "datetime" in str(result[col].dtype):
            result[col] = result[col].dt.isoformat()
        elif result[col].dtype == "object":
            result[col] = result[col].astype(str)
    return result


def _generate_chart_data(df: pd.DataFrame, question: str) -> tuple[Optional[list], str]:
    """
    Deterministically generate chart data from the DataFrame.

    Per PRD §5.5:
    - Time series (date + numeric) → Line chart
    - Categorical comparison (top N) → Bar chart
    - Part-to-whole → Pie chart
    - Two numeric variables → Scatter plot
    - Single number → Stat card (no chart)
    - Doesn't fit → No chart

    Chart DATA is generated by Pandas, never by the LLM.
    """
    if df.empty:
        return None, "none"

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    string_cols = df.select_dtypes(include=["object"]).columns.tolist()
    datetime_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower() or "created" in c.lower()]

    # Single numeric value → stat card
    if len(df) == 1 and len(numeric_cols) == 1:
        return [{"value": float(df.iloc[0][numeric_cols[0]])}], "stat"

    # Time series detection: datetime column + numeric column
    if datetime_cols and numeric_cols:
        time_col = datetime_cols[0]
        value_col = numeric_cols[0]
        chart_df = df[[time_col, value_col]].dropna().sort_values(time_col)
        chart_data = chart_df.rename(columns={time_col: "date", value_col: "value"})
        chart_data["date"] = chart_data["date"].astype(str)
        return chart_data.to_dict(orient="records"), "line"

    # Categorical comparison: string column + numeric column
    if string_cols and numeric_cols:
        cat_col = string_cols[0]
        value_col = numeric_cols[0]
        chart_df = df[[cat_col, value_col]].dropna()

        # If many categories, take top 10
        if len(chart_df) > 10:
            chart_df = chart_df.nlargest(10, value_col)

        chart_data = chart_df.rename(columns={cat_col: "name", value_col: "value"})

        # Part-to-whole check: if all values are positive and relatively close
        total = chart_data["value"].sum()
        if total > 0 and all(chart_data["value"] > 0):
            percentages = chart_data["value"] / total * 100
            # If it looks like a distribution (no single dominant value)
            if percentages.max() < 80 and len(chart_data) <= 7:
                return chart_data.to_dict(orient="records"), "pie"

        return chart_data.to_dict(orient="records"), "bar"

    # Two numeric variables → scatter
    if len(numeric_cols) >= 2:
        chart_df = df[numeric_cols[:2]].dropna()
        chart_df.columns = ["x", "y"]
        return chart_df.to_dict(orient="records"), "scatter"

    return None, "none"
