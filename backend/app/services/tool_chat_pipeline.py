"""Curated-tool chat pipeline for the NexDokandar integration MVP."""

import json
import logging
import uuid
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

from app.models.request_context import SaaSRequestContext
from app.services.reasoning import generate_reasoning
from app.services.tool_client import ToolClientError, call_saas_tool
from app.db import integrated_conversations as conversations


# These tools can contain commercially sensitive or identifiable rows. Their
# results must be rendered locally and must never enter generate_reasoning(),
# which may call an external model provider.
LOCAL_ONLY_TOOLS = frozenset({
    "stockout_risk", "deadstock_advisor", "auto_purchase_orders", "cash_flow_forecast", "expense_anomalies",
    "margin_advisor", "cross_sell_recommendations", "customer_credit_risk",
    "payment_reminders", "customer_churn", "staff_roi", "payroll_forecast",
    "branch_roi", "abc_analysis", "customer_lifetime_value",
    "supplier_performance", "executive_brief",
})

BN_REPORT_NAMES = {
    "stockout_risk": "স্টক শেষ হওয়ার ঝুঁকি রিপোর্ট",
    "deadstock_advisor": "ডেড-স্টক পরামর্শ",
    "auto_purchase_orders": "অটো পারচেজ অর্ডার ড্রাফট",
    "cash_flow_forecast": "ক্যাশ-ফ্লো পূর্বাভাস",
    "expense_anomalies": "অস্বাভাবিক খরচের রিপোর্ট",
    "margin_advisor": "মার্জিন পরামর্শ",
    "cross_sell_recommendations": "ক্রস-সেল পরামর্শ",
    "customer_credit_risk": "কাস্টমার ক্রেডিট ঝুঁকি রিপোর্ট",
    "payment_reminders": "পেমেন্ট রিমাইন্ডার তালিকা",
    "customer_churn": "কাস্টমার চার্ন রিপোর্ট",
    "staff_roi": "স্টাফ ROI রিপোর্ট",
    "payroll_forecast": "পে-রোল পূর্বাভাস",
    "branch_roi": "ব্রাঞ্চ ROI রিপোর্ট",
    "abc_analysis": "ABC পণ্য বিশ্লেষণ",
    "customer_lifetime_value": "কাস্টমার লাইফটাইম ভ্যালু রিপোর্ট",
    "supplier_performance": "সাপ্লায়ার পারফরম্যান্স রিপোর্ট",
    "executive_brief": "দৈনিক এক্সিকিউটিভ ব্রিফ",
}

BN_METRIC_LABELS = {
    "total_deadstock_items": "মোট ডেড-স্টক রেকর্ড",
    "total_locked_capital": "আটকে থাকা মোট মূলধন",
    "forecast_days": "পূর্বাভাসের দিন",
    "current_cash_balance": "বর্তমান নগদ ব্যালেন্স",
    "average_daily_cash_in": "দৈনিক গড় নগদ প্রবাহ",
    "average_daily_cash_out": "দৈনিক গড় নগদ বহিঃপ্রবাহ",
    "supplier_due_exposure": "সাপ্লায়ার বকেয়া",
    "next_month_payroll": "আগামী মাসের পে-রোল",
    "shortage_risk": "অর্থসংকটের ঝুঁকি",
    "projected_closing_balance": "সম্ভাব্য সমাপনী ব্যালেন্স",
    "analyzed_categories": "বিশ্লেষিত খরচের বিভাগ",
    "high_risk_alerts": "উচ্চ ঝুঁকির সতর্কতা",
    "medium_risk_alerts": "মাঝারি ঝুঁকির সতর্কতা",
    "analyzed_products": "বিশ্লেষিত পণ্য",
    "below_target_count": "লক্ষ্য মার্জিনের নিচে",
    "target_margin_percent": "লক্ষ্য মার্জিনের হার",
    "recommendation_count": "পরামর্শের সংখ্যা",
    "assessed_customers": "মূল্যায়িত কাস্টমার",
    "high_risk_count": "উচ্চ ঝুঁকির সংখ্যা",
    "medium_risk_count": "মাঝারি ঝুঁকির সংখ্যা",
    "total_due_exposure": "মোট বকেয়া ঝুঁকি",
    "reminder_count": "রিমাইন্ডারের সংখ্যা",
    "at_risk_customers": "ঝুঁকিতে থাকা কাস্টমার",
    "revenue_at_risk": "ঝুঁকিতে থাকা বিক্রয়মূল্য",
    "assessed_staff": "মূল্যায়িত স্টাফ",
    "employee_count": "কর্মীর সংখ্যা",
    "next_month_payroll_budget": "আগামী মাসের পে-রোল বাজেট",
    "branch_count": "ব্রাঞ্চের সংখ্যা",
    "total_products": "মোট পণ্য",
    "class_a_count": "ক্লাস A পণ্য",
    "class_b_count": "ক্লাস B পণ্য",
    "class_c_count": "ক্লাস C পণ্য",
    "total_gross_profit": "মোট স্থূল লাভ",
    "customer_count": "কাস্টমারের সংখ্যা",
    "average_clv": "গড় CLV",
    "average_basket_items": "গড় বাস্কেট আইটেম",
    "supplier_count": "সাপ্লায়ারের সংখ্যা",
    "total_sales": "মোট বিক্রয়",
    "order_count": "অর্ডারের সংখ্যা",
    "cash_collected_from_orders": "অর্ডার থেকে নগদ আদায়",
    "new_customer_due": "নতুন কাস্টমার বকেয়া",
    "previous_due_collected": "পুরোনো বকেয়া আদায়",
}


# The report picker is a deterministic UI contract. Resolve its exact prompts
# before fuzzy free-text matching so words such as "bundle" or "profit" cannot
# accidentally select a different tool.
CURATED_PROMPT_TO_TOOL = {
    "Generate auto purchase order drafts for products that need reordering": "auto_purchase_orders",
    "Which products may run out in the next 30 days?": "stockout_risk",
    "Show dead stock and recommend discounts or bundle offers": "deadstock_advisor",
    "Forecast cash flow and shortage risk for the next 30 days": "cash_flow_forecast",
    "Show unusual expense anomalies and high-risk cost increases": "expense_anomalies",
    "Use the margin advisor to recommend prices at a 25 percent target margin": "margin_advisor",
    "Which products are frequently bought together for cross-selling?": "cross_sell_recommendations",
    "Which customers have high or medium credit risk?": "customer_credit_risk",
    "Prepare professional payment reminder messages for customers with due balances": "payment_reminders",
    "Which regular customers are at risk of churn?": "customer_churn",
    "Show customer lifetime value and average basket size": "customer_lifetime_value",
    "Show staff ROI, sales per working hour, and gross profit contribution": "staff_roi",
    "Forecast next month's payroll budget": "payroll_forecast",
    "Compare branch ROI, operating costs, payroll, and net profit": "branch_roi",
    "Run an ABC analysis of products by gross profit": "abc_analysis",
    "Show supplier performance and commercial scores": "supplier_performance",
    "Prepare today's daily executive brief": "executive_brief",
    "পুনঃঅর্ডার প্রয়োজন এমন পণ্যের অটো পারচেজ অর্ডার ড্রাফট তৈরি করুন": "auto_purchase_orders",
    "আগামী ৩০ দিনে কোন পণ্যের স্টক শেষ হতে পারে?": "stockout_risk",
    "ডেড স্টক দেখিয়ে ডিসকাউন্ট বা বান্ডেল অফার সাজেস্ট করুন": "deadstock_advisor",
    "আগামী ৩০ দিনের ক্যাশ ফ্লো ও অর্থসংকটের ঝুঁকি দেখান": "cash_flow_forecast",
    "অস্বাভাবিক খরচ ও উচ্চ ঝুঁকির ব্যয় বৃদ্ধি দেখান": "expense_anomalies",
    "২৫ শতাংশ লক্ষ্য মার্জিন ধরে মার্জিন অ্যাডভাইজরের প্রস্তাবিত দাম দেখান": "margin_advisor",
    "ক্রস-সেলের জন্য কোন পণ্যগুলো সাধারণত একসাথে কেনা হয়?": "cross_sell_recommendations",
    "কোন কাস্টমারের ক্রেডিট ঝুঁকি বেশি বা মাঝারি?": "customer_credit_risk",
    "বকেয়া থাকা কাস্টমারদের জন্য পেশাদার পেমেন্ট রিমাইন্ডার তৈরি করুন": "payment_reminders",
    "কোন নিয়মিত কাস্টমাররা চার্নের ঝুঁকিতে আছেন?": "customer_churn",
    "কাস্টমার লাইফটাইম ভ্যালু ও গড় বাস্কেট সাইজ দেখান": "customer_lifetime_value",
    "স্টাফ ROI, কর্মঘণ্টা প্রতি বিক্রি ও মোট লাভে অবদান দেখান": "staff_roi",
    "আগামী মাসের পে-রোল বাজেট পূর্বাভাস দেখান": "payroll_forecast",
    "ব্রাঞ্চ ROI, পরিচালন খরচ, পে-রোল ও নিট লাভ তুলনা করুন": "branch_roi",
    "মোট লাভ অনুযায়ী পণ্যের ABC বিশ্লেষণ করুন": "abc_analysis",
    "সাপ্লায়ার পারফরম্যান্স ও কমার্শিয়াল স্কোর দেখান": "supplier_performance",
    "আজকের দৈনিক এক্সিকিউটিভ ব্রিফ তৈরি করুন": "executive_brief",
}
CURATED_PROMPT_TO_TOOL = {
    prompt.strip().casefold(): tool_name
    for prompt, tool_name in CURATED_PROMPT_TO_TOOL.items()
}


TOOL_TERMS = (
    ("executive_brief", ("executive brief", "evening summary", "daily brief", "daily summary", "দিনের সারাংশ", "সন্ধ্যার সারাংশ")),
    ("auto_purchase_orders", ("auto po", "purchase order draft", "auto purchase", "reorder draft", "অটো পারচেজ", "ক্রয় আদেশ", "ক্রয় আদেশ")),
    ("cash_flow_forecast", ("cash flow", "cashflow", "cash shortage", "cash forecast", "ক্যাশ ফ্লো", "নগদ প্রবাহ", "ক্যাশ শর্টেজ")),
    ("expense_anomalies", ("expense anomaly", "unusual expense", "fraud", "expense leak", "অস্বাভাবিক খরচ", "খরচের অসঙ্গতি", "জালিয়াতি", "জালিয়াতি")),
    ("margin_advisor", ("margin advisor", "dynamic pricing", "suggested price", "price recommendation", "মার্জিন পরামর্শ", "দাম সাজেস্ট", "মূল্য পরামর্শ")),
    ("cross_sell_recommendations", ("cross sell", "cross-sell", "bought together", "bundle offer", "বান্ডেল", "একসাথে কেনে", "সাথে কী কেনে")),
    ("customer_credit_risk", ("credit risk", "due risk", "new credit", "বাকির ঝুঁকি", "ক্রেডিট রিস্ক", "বাকি ঝুঁকি")),
    ("payment_reminders", ("payment reminder", "due reminder", "reminder message", "পেমেন্ট রিমাইন্ডার", "বকেয়া মেসেজ", "বকেয়া মেসেজ", "বাকি পরিশোধ")),
    ("customer_churn", ("customer churn", "churn alert", "inactive customer", "lost vip", "কাস্টমার চার্ন", "নিষ্ক্রিয় কাস্টমার", "নিষ্ক্রিয় কাস্টমার")),
    ("staff_roi", ("staff roi", "sales per employee", "sales per hour", "staff efficiency", "স্টাফ আরওআই", "কর্মী প্রতি বিক্রি", "স্টাফ দক্ষতা")),
    ("payroll_forecast", ("payroll budget", "payroll forecast", "next month salary", "পে-রোল বাজেট", "পেরোল বাজেট", "আগামী মাসের বেতন")),
    ("branch_roi", ("branch roi", "branch profitability", "location profitability", "ব্রাঞ্চ আরওআই", "শাখার লাভ", "লোকেশন লাভজনকতা")),
    ("abc_analysis", ("abc analysis", "80/20 product", "class a product", "product matrix", "এবিসি বিশ্লেষণ", "৮০/২০ পণ্য")),
    ("customer_lifetime_value", ("customer lifetime value", "clv", "basket report", "basket size", "লাইফটাইম ভ্যালু", "বাস্কেট রিপোর্ট", "গড় বাস্কেট", "গড় বাস্কেট")),
    ("supplier_performance", ("supplier performance", "supplier score", "late supplier", "সাপ্লায়ার পারফরম্যান্স", "সাপ্লায়ার পারফরম্যান্স", "সাপ্লায়ার স্কোর", "সাপ্লায়ার স্কোর")),
    ("deadstock_advisor", ("dead stock", "deadstock", "slow moving", "locked capital", "ডেড স্টক", "আটকে")),
    ("stockout_risk", ("stockout", "stock out", "run out", "low stock", "reorder", "স্টক শেষ", "লো স্টক")),
    ("inventory_valuation", ("inventory value", "stock value", "inventory valuation", "স্টকের মূল্য")),
    ("profit_loss", ("profit", "loss", "margin", "expense", "p&l", "লাভ", "ক্ষতি", "খরচ")),
    ("sales_by_hour", ("peak hour", "sales hour", "by hour", "best time", "ব্যস্ত সময়", "ঘণ্টা")),
    ("order_status_breakdown", ("order status", "pending order", "cancelled order", "canceled order", "অর্ডারের অবস্থা")),
    ("customer_retention", ("retention", "repeat customer", "returning customer", "নিয়মিত ক্রেতা")),
    ("product_performance", ("top product", "best product", "product performance", "পণ্যের পারফরম্যান্স", "সেরা পণ্য")),
    ("sales_summary", ("sale", "sales", "revenue", "order", "business", "summary", "বিক্র", "অর্ডার", "ব্যবসা", "সারাংশ")),
)

DATE_RANGE_TOOLS = frozenset({
    "sales_summary", "product_performance", "profit_loss",
    "sales_by_hour", "order_status_breakdown",
    "cash_flow_forecast", "cross_sell_recommendations", "staff_roi",
    "branch_roi", "abc_analysis", "customer_lifetime_value", "executive_brief",
})

TOOL_PRESENTATION = {
    "sales_summary": ("daily_trend", "line", "sales report"),
    "product_performance": (None, "bar", "product performance report"),
    "inventory_valuation": ("products", "bar", "inventory valuation report"),
    "profit_loss": ("expenses_breakdown", "bar", "profit and loss report"),
    "sales_by_hour": (None, "bar", "hourly sales report"),
    "order_status_breakdown": (None, "bar", "order status report"),
    "customer_retention": (None, "bar", "customer retention report"),
    "stockout_risk": ("predictions", "bar", "stockout risk report"),
    "deadstock_advisor": ("recommendations", "bar", "dead-stock report"),
    "auto_purchase_orders": ("draft_pos", "bar", "auto purchase-order drafts"),
    "cash_flow_forecast": ("forecast", "line", "cash-flow forecast"),
    "expense_anomalies": ("anomalies", "bar", "expense anomaly report"),
    "margin_advisor": ("recommendations", "bar", "margin advisor"),
    "cross_sell_recommendations": ("recommendations", "bar", "cross-sell recommendations"),
    "customer_credit_risk": ("customers", "bar", "customer credit-risk report"),
    "payment_reminders": ("reminders", "bar", "payment reminder list"),
    "customer_churn": ("customers", "bar", "customer churn report"),
    "staff_roi": ("staff", "bar", "staff ROI report"),
    "payroll_forecast": ("employees", "bar", "payroll forecast"),
    "branch_roi": ("branches", "bar", "branch ROI report"),
    "abc_analysis": ("products", "bar", "ABC product analysis"),
    "customer_lifetime_value": ("customers", "bar", "customer lifetime-value report"),
    "supplier_performance": ("suppliers", "bar", "supplier performance report"),
    "executive_brief": ("top_products", "bar", "daily executive brief"),
}


def _select_tool(question: str) -> Optional[str]:
    normalized = question.strip().casefold()
    curated_tool = CURATED_PROMPT_TO_TOOL.get(normalized)
    if curated_tool:
        return curated_tool
    for tool_name, terms in TOOL_TERMS:
        if any(term in normalized for term in terms):
            return tool_name
    return None


def _chart_data(tool_name: str, data: object) -> list[dict]:
    key, _, _ = TOOL_PRESENTATION[tool_name]
    rows = data.get(key, []) if key and isinstance(data, dict) else data
    if isinstance(rows, dict):
        return [{"metric": name, "value": value} for name, value in rows.items()]
    if not isinstance(rows, list):
        return []
    if tool_name != "stockout_risk":
        return rows[:50]

    cleaned_rows = []
    for row in rows[:50]:
        if not isinstance(row, dict):
            continue
        cleaned = dict(row)
        velocity = _number(cleaned.get("daily_velocity"))
        days_remaining = _number(cleaned.get("estimated_days_remaining"))
        if velocity <= 0 or days_remaining >= 999:
            cleaned["estimated_days_remaining"] = None
        cleaned_rows.append(cleaned)
    return cleaned_rows


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _bn_number(value: int) -> str:
    return str(value).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def _stockout_reasoning(data: dict, is_bangla: bool) -> dict:
    """Describe stockout evidence without turning missing sales into certainty."""
    rows = data.get("predictions") if isinstance(data.get("predictions"), list) else []
    horizon_days = 30
    at_risk = 0
    no_recent_sales = 0
    below_reorder = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        current_stock = _number(row.get("current_stock"))
        reorder_point = _number(row.get("reorder_point"))
        sold = _number(row.get("qty_sold_window"))
        velocity = _number(row.get("daily_velocity"))
        days_remaining = _number(row.get("estimated_days_remaining"))
        has_recent_sales = sold > 0 or velocity > 0
        is_below_reorder = current_stock <= reorder_point
        is_within_horizon = has_recent_sales and 0 <= days_remaining <= horizon_days
        risk_level = str(row.get("risk_level") or "").lower()

        no_recent_sales += int(not has_recent_sales)
        below_reorder += int(is_below_reorder)
        at_risk += int(
            is_below_reorder
            or is_within_horizon
            or risk_level in {"critical", "warning"}
        )

    total_records = len(rows)
    records_with_sales = max(0, total_records - no_recent_sales)
    confidence = (
        "low" if total_records == 0 or no_recent_sales == total_records
        else "medium" if no_recent_sales > 0
        else "high"
    )

    if is_bangla:
        total_bn = _bn_number(total_records)
        risk_bn = _bn_number(at_risk)
        horizon_bn = _bn_number(horizon_days)
        no_sales_bn = _bn_number(no_recent_sales)
        with_sales_bn = _bn_number(records_with_sales)
        below_reorder_bn = _bn_number(below_reorder)
        if at_risk:
            answer = (
                f"বর্তমান স্টক, পুনঃঅর্ডার সীমা এবং গত ৩০ দিনের রেকর্ডকৃত বিক্রি অনুযায়ী "
                f"{total_bn}টি ভ্যারিয়েন্ট–শাখা স্টক রেকর্ডের মধ্যে {risk_bn}টিতে "
                f"আগামী {horizon_bn} দিনের মধ্যে স্টক শেষ হওয়া বা পুনঃঅর্ডারের ঝুঁকি শনাক্ত হয়েছে।"
            )
        else:
            answer = (
                f"বর্তমান স্টক, পুনঃঅর্ডার সীমা এবং গত ৩০ দিনের রেকর্ডকৃত বিক্রি অনুযায়ী "
                f"{total_bn}টি ভ্যারিয়েন্ট–শাখা স্টক রেকর্ডের কোনোটিতে আগামী "
                f"{horizon_bn} দিনের মধ্যে স্টক শেষ হওয়ার ঝুঁকি শনাক্ত হয়নি।"
            )
        if no_recent_sales:
            answer += (
                f" তবে {no_sales_bn}টি রেকর্ডে সাম্প্রতিক বিক্রি নেই, তাই পূর্বাভাসটির "
                "নির্ভরযোগ্যতা সীমিত; নতুন চাহিদা তৈরি হলে ফল পরিবর্তিত হতে পারে।"
            )
        insights = [
            f"সাম্প্রতিক বিক্রি পাওয়া গেছে: {with_sales_bn}টি রেকর্ডে।",
            f"সাম্প্রতিক বিক্রি নেই: {no_sales_bn}টি রেকর্ডে।",
            f"পুনঃঅর্ডার সীমায় বা তার নিচে: {below_reorder_bn}টি রেকর্ড।",
        ]
    else:
        if at_risk:
            answer = (
                f"Based on current stock, reorder points, and the last 30 days of recorded sales, "
                f"{at_risk} of {total_records} variant–branch stock records show stockout or "
                f"reorder risk within the next {horizon_days} days."
            )
        else:
            answer = (
                f"Based on current stock, reorder points, and the last 30 days of recorded sales, "
                f"no stockout risk was detected among {total_records} variant–branch stock records "
                f"for the next {horizon_days} days."
            )
        if no_recent_sales:
            answer += (
                f" However, {no_recent_sales} records have no recent sales, so this is a "
                "limited-confidence forecast and may change when demand resumes."
            )
        insights = [
            f"Records with recent sales: {records_with_sales}.",
            f"Records without recent sales: {no_recent_sales}.",
            f"Records at or below reorder point: {below_reorder}.",
        ]

    return {
        "summary": answer,
        "insights": insights,
        "confidence_signal": confidence,
        "chart_type": "bar",
    }


LOCAL_ROW_LABELS_BN = {
    "deadstock_advisor": "ডেড-স্টক পরামর্শ",
    "auto_purchase_orders": "পারচেজ অর্ডার ড্রাফট",
    "cash_flow_forecast": "সাপ্তাহিক পূর্বাভাস পর্ব",
    "expense_anomalies": "অস্বাভাবিক খরচের সতর্কতা",
    "margin_advisor": "পণ্যের মূল্য পরামর্শ",
    "cross_sell_recommendations": "ক্রস-সেল পরামর্শ",
    "customer_credit_risk": "মূল্যায়িত কাস্টমার",
    "payment_reminders": "পেমেন্ট রিমাইন্ডার",
    "customer_churn": "ঝুঁকিতে থাকা কাস্টমার",
    "staff_roi": "স্টাফ রেকর্ড",
    "payroll_forecast": "কর্মীর বেতন পূর্বাভাস",
    "branch_roi": "ব্রাঞ্চ রেকর্ড",
    "abc_analysis": "পণ্য রেকর্ড",
    "customer_lifetime_value": "কাস্টমার রেকর্ড",
    "supplier_performance": "সাপ্লায়ার রেকর্ড",
    "executive_brief": "শীর্ষ পণ্য",
}

LOCAL_NO_DATA_BN = {
    "deadstock_advisor": "নির্ধারিত সময়সীমায় ডেড বা ধীরগতির স্টক পাওয়া যায়নি।",
    "auto_purchase_orders": "বর্তমানে পুনঃঅর্ডার প্রয়োজন এমন পণ্য পাওয়া যায়নি; তাই কোনো পারচেজ অর্ডার ড্রাফট তৈরি হয়নি।",
    "expense_anomalies": "সাম্প্রতিক খরচে নির্ধারিত সীমা অতিক্রম করা কোনো অস্বাভাবিকতা শনাক্ত হয়নি।",
    "margin_advisor": "মূল্য বিশ্লেষণের জন্য সক্রিয় পণ্য ও ক্রয়মূল্যের তথ্য পাওয়া যায়নি।",
    "cross_sell_recommendations": "একই অর্ডারে একাধিক ভিন্ন পণ্য কেনার ইতিহাস পাওয়া যায়নি; তাই নির্ভরযোগ্য ক্রস-সেল বান্ডেল প্রস্তাব করা যাচ্ছে না।",
    "customer_credit_risk": "বকেয়া বা ক্রেডিট ইতিহাসসহ মূল্যায়নযোগ্য কাস্টমার পাওয়া যায়নি।",
    "payment_reminders": "বর্তমানে বকেয়া ব্যালেন্সসহ কোনো কাস্টমার পাওয়া যায়নি; পেমেন্ট রিমাইন্ডার প্রয়োজন নেই।",
    "customer_churn": "কমপক্ষে ২টি অর্ডার করা এবং ৩০ দিনের বেশি নিষ্ক্রিয় কোনো কাস্টমার পাওয়া যায়নি।",
    "staff_roi": "নির্বাচিত সময়ে স্টাফের বিক্রি বা কর্মঘণ্টার তথ্য পাওয়া যায়নি।",
    "payroll_forecast": "সক্রিয় বেতন কাঠামোসহ কোনো কর্মী পাওয়া যায়নি।",
    "branch_roi": "বিশ্লেষণের জন্য কোনো সক্রিয় ব্রাঞ্চ পাওয়া যায়নি।",
    "abc_analysis": "নির্বাচিত সময়ে ABC বিশ্লেষণের উপযোগী বিক্রিত পণ্য পাওয়া যায়নি।",
    "customer_lifetime_value": "নির্বাচিত সময়ে কাস্টমার অর্ডারের ইতিহাস পাওয়া যায়নি।",
    "supplier_performance": "বিশ্লেষণের জন্য কোনো সক্রিয় সাপ্লায়ার পাওয়া যায়নি।",
    "executive_brief": "নির্বাচিত দিনে সম্পন্ন বিক্রয় বা শীর্ষ পণ্যের তথ্য পাওয়া যায়নি।",
}

LOCAL_NO_DATA_EN = {
    "deadstock_advisor": "No dead or slow-moving stock matched the selected window.",
    "auto_purchase_orders": "No products currently require reordering, so no purchase-order draft was created.",
    "expense_anomalies": "No expense increase crossed the configured anomaly threshold.",
    "margin_advisor": "No active product and cost data is available for price analysis.",
    "cross_sell_recommendations": "No orders containing multiple distinct products were found, so a reliable cross-sell bundle cannot be recommended.",
    "customer_credit_risk": "No customers with assessable due or credit history were found.",
    "payment_reminders": "No customer currently has an outstanding balance requiring a reminder.",
    "customer_churn": "No customer with at least two orders and more than 30 inactive days was found.",
    "staff_roi": "No staff sales or working-hour data was found for the selected period.",
    "payroll_forecast": "No employee with an active salary structure was found.",
    "branch_roi": "No active branch was found for analysis.",
    "abc_analysis": "No sold products were found for ABC analysis in the selected period.",
    "customer_lifetime_value": "No customer order history was found in the selected period.",
    "supplier_performance": "No active supplier was found for analysis.",
    "executive_brief": "No completed sales or top-product data was found for the selected day.",
}

LOCAL_DEFAULT_CONFIDENCE = {
    "deadstock_advisor": "medium", "auto_purchase_orders": "medium",
    "cash_flow_forecast": "medium", "expense_anomalies": "medium",
    "margin_advisor": "high", "cross_sell_recommendations": "medium",
    "customer_credit_risk": "medium", "payment_reminders": "high",
    "customer_churn": "medium", "staff_roi": "medium",
    "payroll_forecast": "medium", "branch_roi": "medium",
    "abc_analysis": "high", "customer_lifetime_value": "high",
    "supplier_performance": "medium", "executive_brief": "high",
}

LOCAL_NO_DATA_CONFIDENCE = {
    "deadstock_advisor": "high", "auto_purchase_orders": "high",
    "expense_anomalies": "medium", "margin_advisor": "low",
    "cross_sell_recommendations": "low", "customer_credit_risk": "low",
    "payment_reminders": "high", "customer_churn": "medium",
    "staff_roi": "low", "payroll_forecast": "low", "branch_roi": "low",
    "abc_analysis": "low", "customer_lifetime_value": "low",
    "supplier_performance": "low", "executive_brief": "medium",
}


def _summary_value(value: object, is_bangla: bool) -> str:
    if is_bangla and isinstance(value, (int, float)) and not isinstance(value, bool):
        return _bn_number(value)
    if is_bangla and isinstance(value, str):
        return {"low": "কম", "medium": "মাঝারি", "high": "উচ্চ"}.get(
            value.lower(), value
        )
    return str(value)


def _local_reasoning(tool_name: str, data: dict, is_bangla: bool) -> dict:
    """Build an evidence-calibrated summary without sending business rows to an LLM."""
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    technical_keys = {"ai_powered", "error_note"}
    populated = [
        (key, value) for key, value in summary.items()
        if value is not None and key not in technical_keys
    ]
    insight_lines = [
        f"{BN_METRIC_LABELS.get(key, key.replace('_', ' ').title())}: {_summary_value(value, True)}"
        for key, value in populated[:6]
    ] if is_bangla else [
        f"{key.replace('_', ' ').title()}: {_summary_value(value, False)}"
        for key, value in populated[:6]
    ]

    row_key = TOOL_PRESENTATION[tool_name][0]
    raw_rows = data.get(row_key) if row_key else None
    rows = raw_rows if isinstance(raw_rows, list) else []
    row_count = len(rows)
    no_data = row_key is not None and row_count == 0
    report_name = BN_REPORT_NAMES.get(tool_name, TOOL_PRESENTATION[tool_name][2]) \
        if is_bangla else TOOL_PRESENTATION[tool_name][2]

    if no_data:
        answer = (
            LOCAL_NO_DATA_BN.get(tool_name, f"{report_name}-এর জন্য কোনো তথ্য পাওয়া যায়নি।")
            if is_bangla else
            LOCAL_NO_DATA_EN.get(tool_name, f"No data was found for the {report_name}.")
        )
        confidence = LOCAL_NO_DATA_CONFIDENCE.get(tool_name, "low")
    else:
        if is_bangla:
            label = LOCAL_ROW_LABELS_BN.get(tool_name, "রেকর্ড")
            answer = (
                f"অনুমোদিত ব্যবসার তথ্য থেকে {report_name} প্রস্তুত হয়েছে। "
                f"মোট {_bn_number(row_count)}টি {label} বিশ্লেষণ করা হয়েছে।"
            )
        else:
            answer = (
                f"The {report_name} is ready from authorized business data. "
                f"{row_count} records were analyzed."
            )
        confidence = LOCAL_DEFAULT_CONFIDENCE.get(tool_name, "medium")

    if tool_name == "cross_sell_recommendations" and rows:
        strongest = max(
            (_number(row.get("bought_together_count")) for row in rows if isinstance(row, dict)),
            default=0,
        )
        confidence = "high" if strongest >= 3 else "medium" if strongest >= 2 else "low"
        note = (
            f"সর্বোচ্চ একসাথে কেনার রেকর্ড: {_bn_number(int(strongest))} বার।"
            if is_bangla else f"Strongest co-purchase count: {int(strongest)}."
        )
        insight_lines.append(note)
    elif tool_name == "cash_flow_forecast":
        if _number(summary.get("average_daily_cash_in")) == 0 and _number(summary.get("average_daily_cash_out")) == 0:
            confidence = "low"
    elif tool_name == "margin_advisor" and rows:
        if any(_number(row.get("unit_cost")) <= 0 for row in rows if isinstance(row, dict)):
            confidence = "medium"

    return {
        "summary": answer,
        "insights": insight_lines,
        "confidence_signal": confidence,
        "chart_type": TOOL_PRESENTATION[tool_name][1],
    }


async def process_tool_chat(
    question: str,
    conversation_id: Optional[str],
    date_range: Optional[dict],
    context: SaaSRequestContext,
    delegation_token: str,
    persist_messages: bool = False,
    persist_user_message: bool = True,
) -> AsyncGenerator[str, None]:
    session_id = conversation_id or str(uuid.uuid4())
    is_bangla = context.locale.lower().startswith("bn")
    if persist_messages and persist_user_message:
        await conversations.save_message(
            session_id, str(context.org_id), str(context.user_id), "user", question
        )
    yield json.dumps({
        "type": "meta",
        "request_id": context.request_id,
        "conversation_id": session_id,
        "scope": {
            "location_id": str(context.selected_location_id) if context.selected_location_id else None,
            **(date_range or {}),
        },
    }) + "\n"

    tool_name = _select_tool(question)
    if not tool_name:
        message_id = str(uuid.uuid4())
        answer_text = (
            "আমি এখনো এই প্রশ্নের নিরাপদ উত্তর দিতে পারছি না। বিক্রয়, পণ্য, ইনভেন্টরি, "
            "লাভ-ক্ষতি, অর্ডারের অবস্থা, ক্রেতা ধরে রাখা, স্টক শেষ হওয়ার ঝুঁকি বা "
            "ডেড স্টক সম্পর্কে প্রশ্ন করুন।"
            if is_bangla else
            "I cannot answer that safely yet. Try asking about sales, products, "
            "inventory, profit and loss, order status, retention, stockout risk, "
            "or dead stock."
        )
        if persist_messages:
            await conversations.save_message(
                session_id, str(context.org_id), str(context.user_id), "assistant",
                answer_text, message_id=message_id, confidence="low",
            )
        yield json.dumps({
            "type": "answer",
            "message_id": message_id,
            "answer": answer_text,
            "insights": [],
            "chart_type": "none",
            "chart_data": None,
            "confidence": "low",
            "sources": [],
        }) + "\n"
        yield json.dumps({"type": "done", "execution_ms": 0}) + "\n"
        return

    report_name = BN_REPORT_NAMES.get(tool_name, TOOL_PRESENTATION[tool_name][2]) \
        if is_bangla else TOOL_PRESENTATION[tool_name][2]
    yield json.dumps({
        "type": "status", "stage": "fetching_data",
        "message": f"অনুমোদিত {report_name} যাচাই করছি..." if is_bangla else f"Checking the authorized {report_name}...",
    }) + "\n"

    arguments = {}
    if date_range and tool_name in DATE_RANGE_TOOLS:
        arguments = {"from": date_range.get("from"), "to": date_range.get("to")}
    elif tool_name == "stockout_risk":
        arguments = {"horizon_days": 30}
    elif tool_name == "deadstock_advisor":
        arguments = {"idle_days": 60}
    elif tool_name == "cash_flow_forecast":
        arguments = {"forecast_days": 30}
    elif tool_name == "margin_advisor":
        arguments = {"target_margin_percent": 25}
    try:
        tool_result = await call_saas_tool(tool_name, arguments, delegation_token)
    except ToolClientError as exc:
        yield json.dumps({
            "type": "error", "code": "AI_TOOL_UNAVAILABLE",
            "message": str(exc), "retryable": True,
        }) + "\n"
        return

    yield json.dumps({
        "type": "status", "stage": "analyzing",
        "message": f"{report_name} বিশ্লেষণ করছি..." if is_bangla else f"Analyzing the {report_name}...",
    }) + "\n"

    data = tool_result.get("data") or {}
    chart_data = _chart_data(tool_name, data)
    _, default_chart_type, _ = TOOL_PRESENTATION[tool_name]
    reasoning_input = {
        "rows": len(chart_data) if chart_data else (1 if data else 0),
        "source": tool_name,
        "data": data,
    }
    if tool_name == "stockout_risk":
        reasoning = _stockout_reasoning(data, is_bangla)
    elif tool_name in LOCAL_ONLY_TOOLS:
        reasoning = _local_reasoning(tool_name, data, is_bangla)
    else:
        try:
            reasoning = await generate_reasoning(
                question,
                reasoning_input,
                default_chart_type if chart_data else "stat",
                locale=context.locale,
            )
        except Exception:
            logger.exception("LLM reasoning failed")
            yield json.dumps({
                "type": "error", "code": "AI_MODEL_UNAVAILABLE",
                "message": "The AI model is temporarily unavailable. Please try again in a moment.",
                "retryable": True,
            }) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return

    message_id = str(uuid.uuid4())
    answer_event = {
        "type": "answer",
        "message_id": message_id,
        "answer": reasoning.get(
            "summary", "বিক্রয়ের সারাংশ প্রস্তুত।" if is_bangla else "Sales summary is ready."
        ),
        "insights": reasoning.get("insights", []),
        "chart_type": reasoning.get("chart_type", "none"),
        "chart_data": chart_data,
        "confidence": reasoning.get("confidence_signal", "medium"),
        "sources": [{
            "tool": tool_name,
            "generated_at": tool_result.get("generated_at"),
            "scope": tool_result.get("scope"),
        }],
        "cached": False,
    }
    if persist_messages:
        await conversations.save_message(
            session_id, str(context.org_id), str(context.user_id), "assistant",
            answer_event["answer"], message_id=message_id,
            insights=answer_event["insights"], chart_type=answer_event["chart_type"],
            chart_data=answer_event["chart_data"], confidence=answer_event["confidence"],
            sources=answer_event["sources"],
        )
    yield json.dumps(answer_event, default=str) + "\n"
    yield json.dumps({"type": "done"}) + "\n"
