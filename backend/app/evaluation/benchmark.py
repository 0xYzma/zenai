"""
AI Evaluation Benchmark — §18, §20

30-50 curated questions against a test schema.
Measures: execution accuracy, result correctness, graceful fallback,
confidence calibration, latency.
"""
import json
from pathlib import Path

BENCHMARK_QUESTIONS = [
    # ── Simple Lookups ──────────────────────────────────────────────
    {
        "id": "Q01",
        "question": "What are the names of all stores?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "stores"],
        "expected_columns": ["name"],
        "category": "lookup",
    },
    {
        "id": "Q02",
        "question": "How many products do we have?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "COUNT"],
        "expected_columns": ["count"],
        "category": "aggregation",
    },
    {
        "id": "Q03",
        "question": "What are the different order statuses?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "DISTINCT"],
        "expected_columns": ["status"],
        "category": "lookup",
    },
    {
        "id": "Q04",
        "question": "List all categories with their names.",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "categories"],
        "expected_columns": ["name"],
        "category": "lookup",
    },
    {
        "id": "Q05",
        "question": "What is the total number of customers?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "COUNT"],
        "expected_columns": ["count"],
        "category": "aggregation",
    },

    # ── Aggregations ────────────────────────────────────────────────
    {
        "id": "Q06",
        "question": "What was our total revenue last month?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "orders"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q07",
        "question": "What is the average order value?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "AVG"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q08",
        "question": "How many orders were placed each day this week?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "COUNT", "GROUP BY"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q09",
        "question": "What is the total quantity sold per product?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "GROUP BY"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q10",
        "question": "What is the refund rate across all orders?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "COUNT", "CASE"],
        "expected_columns": [],
        "category": "aggregation",
    },

    # ── Comparisons ─────────────────────────────────────────────────
    {
        "id": "Q11",
        "question": "How does this month's revenue compare to last month?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM"],
        "expected_columns": [],
        "category": "comparison",
    },
    {
        "id": "Q12",
        "question": "Which store had the highest revenue last week?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "ORDER BY"],
        "expected_columns": [],
        "category": "ranking",
    },
    {
        "id": "Q13",
        "question": "What are the top 5 products by revenue?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "LIMIT"],
        "expected_columns": [],
        "category": "ranking",
    },
    {
        "id": "Q14",
        "question": "Which category has the most orders?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "COUNT", "GROUP BY", "ORDER BY"],
        "expected_columns": [],
        "category": "ranking",
    },
    {
        "id": "Q15",
        "question": "Show me daily revenue for the past 7 days.",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "GROUP BY"],
        "expected_columns": [],
        "category": "time_series",
    },

    # ── Complex / Multi-step ────────────────────────────────────────
    {
        "id": "Q16",
        "question": "What percentage of total revenue comes from each store?",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "SUM", "GROUP BY"],
        "expected_columns": [],
        "category": "ratio",
    },
    {
        "id": "Q17",
        "question": "Which customers have placed more than 5 orders?",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "COUNT", "GROUP BY", "HAVING"],
        "expected_columns": [],
        "category": "filter",
    },
    {
        "id": "Q18",
        "question": "What is the month-over-month revenue growth rate?",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "SUM"],
        "expected_columns": [],
        "category": "comparison",
    },
    {
        "id": "Q19",
        "question": "Show me each store's revenue breakdown by category.",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "SUM", "GROUP BY"],
        "expected_columns": [],
        "category": "breakdown",
    },
    {
        "id": "Q20",
        "question": "What are the busiest hours for orders across all stores?",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "COUNT", "GROUP BY"],
        "expected_columns": [],
        "category": "time_series",
    },

    # ── Unanswerable (§2.2 — should gracefully fail) ────────────────
    {
        "id": "Q21",
        "question": "What's our customer churn rate?",
        "difficulty": "unanswerable",
        "expected_sql_contains": [],
        "expected_columns": [],
        "category": "unanswerable",
        "expected_behavior": "should_respond_no_data",
    },
    {
        "id": "Q22",
        "question": "What is the employee satisfaction score?",
        "difficulty": "unanswerable",
        "expected_sql_contains": [],
        "expected_columns": [],
        "category": "unanswerable",
        "expected_behavior": "should_respond_no_data",
    },
    {
        "id": "Q23",
        "question": "Show me the marketing campaign ROI.",
        "difficulty": "unanswerable",
        "expected_sql_contains": [],
        "expected_columns": [],
        "category": "unanswerable",
        "expected_behavior": "should_respond_no_data",
    },
    {
        "id": "Q24",
        "question": "What is the inventory turnover rate?",
        "difficulty": "unanswerable",
        "expected_sql_contains": [],
        "expected_columns": [],
        "category": "unanswerable",
        "expected_behavior": "should_respond_no_data",
    },
    {
        "id": "Q25",
        "question": "Which supplier has the fastest delivery time?",
        "difficulty": "unanswerable",
        "expected_sql_contains": [],
        "expected_columns": [],
        "category": "unanswerable",
        "expected_behavior": "should_respond_no_data",
    },

    # ── More simple/medium for breadth ──────────────────────────────
    {
        "id": "Q26",
        "question": "What is the most expensive product?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "ORDER BY", "LIMIT"],
        "expected_columns": [],
        "category": "ranking",
    },
    {
        "id": "Q27",
        "question": "How many orders were refunded?",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "COUNT", "WHERE"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q28",
        "question": "Show me orders from the last 30 days.",
        "difficulty": "simple",
        "expected_sql_contains": ["SELECT", "WHERE"],
        "expected_columns": [],
        "category": "filter",
    },
    {
        "id": "Q29",
        "question": "What is the total revenue by store for this quarter?",
        "difficulty": "medium",
        "expected_sql_contains": ["SELECT", "SUM", "GROUP BY"],
        "expected_columns": [],
        "category": "aggregation",
    },
    {
        "id": "Q30",
        "question": "Which products have never been ordered?",
        "difficulty": "hard",
        "expected_sql_contains": ["SELECT", "LEFT JOIN"],
        "expected_columns": [],
        "category": "filter",
    },
]


def load_benchmark() -> list[dict]:
    """Load the benchmark question set."""
    return BENCHMARK_QUESTIONS


def get_questions_by_difficulty(difficulty: str) -> list[dict]:
    """Filter benchmark questions by difficulty."""
    return [q for q in BENCHMARK_QUESTIONS if q["difficulty"] == difficulty]


def get_questions_by_category(category: str) -> list[dict]:
    """Filter benchmark questions by category."""
    return [q for q in BENCHMARK_QUESTIONS if q["category"] == category]


def export_benchmark(output_path: str):
    """Export benchmark to JSON file for external use."""
    with open(output_path, "w") as f:
        json.dump(BENCHMARK_QUESTIONS, f, indent=2)
    print(f"Exported {len(BENCHMARK_QUESTIONS)} questions to {output_path}")
