"""Allowlisted client for tenant-scoped NexDokandar data tools."""

from typing import Any

import httpx

from app.core.config import get_settings


ALLOWED_TOOLS = frozenset({
    "sales_summary", "product_performance", "inventory_valuation",
    "profit_loss", "sales_by_hour", "order_status_breakdown",
    "customer_retention", "stockout_risk", "deadstock_advisor",
    "auto_purchase_orders", "cash_flow_forecast", "expense_anomalies",
    "margin_advisor", "cross_sell_recommendations", "customer_credit_risk",
    "payment_reminders", "customer_churn", "staff_roi", "payroll_forecast",
    "branch_roi", "abc_analysis", "customer_lifetime_value",
    "supplier_performance", "executive_brief",
})


class ToolClientError(Exception):
    pass


async def call_saas_tool(
    tool_name: str,
    arguments: dict[str, Any],
    delegation_token: str,
) -> dict[str, Any]:
    if tool_name not in ALLOWED_TOOLS:
        raise ToolClientError("Unsupported data tool")

    settings = get_settings()
    if not settings.saas_internal_tools_url or not settings.saas_internal_service_key:
        raise ToolClientError("SaaS data tools are not configured")

    url = f"{settings.saas_internal_tools_url.rstrip('/')}/tools/{tool_name}"
    timeout_seconds = max(settings.ai_query_timeout_ms / 1000, 1)
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {delegation_token}",
                    "X-ZenAI-Service-Key": settings.saas_internal_service_key,
                    "Content-Type": "application/json",
                },
                json=arguments,
            )
    except httpx.TimeoutException as exc:
        raise ToolClientError("The business data request timed out") from exc
    except httpx.HTTPError as exc:
        raise ToolClientError("The business data service is unavailable") from exc

    if response.status_code != 200:
        raise ToolClientError("The business data tool rejected the request")
    payload = response.json()
    if not payload.get("success") or payload.get("tool") != tool_name:
        raise ToolClientError("The business data tool returned an invalid response")
    return payload
