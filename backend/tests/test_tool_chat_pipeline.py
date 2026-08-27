import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.models.request_context import SaaSRequestContext
from app.services.tool_chat_pipeline import (
    _local_reasoning,
    _select_tool,
    _stockout_reasoning,
    process_tool_chat,
)


class ToolChatPipelineTests(unittest.IsolatedAsyncioTestCase):
    def test_curated_question_router(self):
        cases = {
            "Which products may run out soon?": "stockout_risk",
            "How much money is locked in dead stock?": "deadstock_advisor",
            "Show my top product performance": "product_performance",
            "What is our inventory value?": "inventory_valuation",
            "Summarize profit and expenses": "profit_loss",
            "What are our peak hours?": "sales_by_hour",
            "Show the order status breakdown": "order_status_breakdown",
            "How many returning customers do we have?": "customer_retention",
            "Summarize sales": "sales_summary",
            "Forecast our cash flow for the next month": "cash_flow_forecast",
            "Show unusual expense anomalies": "expense_anomalies",
            "Generate auto purchase order drafts": "auto_purchase_orders",
            "Which customers are high credit risk?": "customer_credit_risk",
            "Show branch ROI": "branch_roi",
            "Run an ABC analysis": "abc_analysis",
            "Prepare today's executive brief": "executive_brief",
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
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(_select_tool(question), expected)

    def context(self):
        now = datetime.now(timezone.utc)
        return SaaSRequestContext(
            user_id=uuid4(),
            org_id=uuid4(),
            role="admin",
            allowed_location_ids=(uuid4(),),
            permissions=frozenset({"insights"}),
            features=frozenset({"ai_features"}),
            request_id="pipeline-test",
            token_id=str(uuid4()),
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )

    async def collect(self, question):
        return [
            json.loads(line)
            async for line in process_tool_chat(
                question, None, None, self.context(), "delegation-token"
            )
        ]

    async def test_unsupported_question_fails_honestly_without_tool_call(self):
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new_callable=AsyncMock,
        ) as tool:
            events = await self.collect("Tell me about payroll tax law")
        tool.assert_not_awaited()
        self.assertEqual([event["type"] for event in events], ["meta", "answer", "done"])
        self.assertEqual(events[1]["confidence"], "low")

    async def test_sales_question_uses_allowlisted_tool(self):
        tool_response = {
            "success": True,
            "tool": "sales_summary",
            "generated_at": "2026-08-19T00:00:00Z",
            "scope": {"location_id": None},
            "data": {
                "summary": {"total_orders": 2, "total_revenue": 500},
                "daily_trend": [{"date": "2026-08-19", "revenue": 500}],
            },
        }
        reasoning_response = {
            "summary": "Revenue was 500 across two orders.",
            "insights": ["Average revenue per order was 250."],
            "confidence_signal": "high",
            "chart_type": "line",
        }
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new=AsyncMock(return_value=tool_response),
        ) as tool, patch(
            "app.services.tool_chat_pipeline.generate_reasoning",
            new=AsyncMock(return_value=reasoning_response),
        ):
            events = await self.collect("Summarize sales")

        tool.assert_awaited_once_with("sales_summary", {}, "delegation-token")
        answer = next(event for event in events if event["type"] == "answer")
        self.assertEqual(answer["confidence"], "high")
        self.assertEqual(answer["chart_data"][0]["revenue"], 500)

    async def test_stockout_question_uses_bounded_default_window(self):
        tool_response = {
            "success": True, "tool": "stockout_risk",
            "generated_at": "2026-08-19T00:00:00Z", "scope": {"location_id": None},
            "data": {"summary": {"critical_count": 1}, "predictions": [
                {"product_name": "Rice", "risk_level": "critical", "current_stock": 1},
            ]},
        }
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new=AsyncMock(return_value=tool_response),
        ) as tool, patch(
            "app.services.tool_chat_pipeline.generate_reasoning",
            new=AsyncMock(return_value={
                "summary": "One product is at critical risk.", "insights": [],
                "confidence_signal": "high", "chart_type": "bar",
            }),
        ) as reasoning:
            events = await self.collect("Which products may run out soon?")

        tool.assert_awaited_once_with(
            "stockout_risk", {"horizon_days": 30}, "delegation-token"
        )
        reasoning.assert_not_awaited()
        answer = next(event for event in events if event["type"] == "answer")
        self.assertEqual(answer["chart_data"][0]["product_name"], "Rice")

    def test_stockout_wording_discloses_missing_sales_in_bangla(self):
        reasoning = _stockout_reasoning({"predictions": [
            {
                "product_name": "Rice", "current_stock": 100,
                "reorder_point": 10, "qty_sold_window": 0,
                "daily_velocity": 0, "estimated_days_remaining": 999,
                "risk_level": "healthy",
            },
        ]}, True)

        self.assertIn("ভ্যারিয়েন্ট–শাখা স্টক রেকর্ড", reasoning["summary"])
        self.assertIn("নির্ভরযোগ্যতা সীমিত", reasoning["summary"])
        self.assertEqual(reasoning["confidence_signal"], "low")

    def test_empty_cross_sell_is_honest_and_low_confidence_in_bangla(self):
        reasoning = _local_reasoning(
            "cross_sell_recommendations",
            {"summary": {"recommendation_count": 0}, "recommendations": []},
            True,
        )

        self.assertIn("একই অর্ডারে একাধিক ভিন্ন পণ্য", reasoning["summary"])
        self.assertEqual(reasoning["confidence_signal"], "low")

    def test_single_cross_sell_observation_stays_low_confidence(self):
        reasoning = _local_reasoning(
            "cross_sell_recommendations",
            {
                "summary": {"recommendation_count": 1},
                "recommendations": [{"bought_together_count": 1}],
            },
            True,
        )

        self.assertEqual(reasoning["confidence_signal"], "low")
        self.assertIn("১ বার", reasoning["insights"][-1])

    async def test_sensitive_credit_risk_report_never_calls_external_reasoning(self):
        tool_response = {
            "success": True, "tool": "customer_credit_risk",
            "generated_at": "2026-08-24T00:00:00Z", "scope": {"location_id": None},
            "data": {
                "summary": {"assessed_customers": 1, "high_risk_count": 1},
                "customers": [{
                    "customer_id": "private-id", "customer_name": "Private Customer",
                    "current_due": 5000, "risk_level": "high",
                }],
            },
        }
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new=AsyncMock(return_value=tool_response),
        ), patch(
            "app.services.tool_chat_pipeline.generate_reasoning",
            new_callable=AsyncMock,
        ) as reasoning:
            events = await self.collect("Which customers are high credit risk?")

        reasoning.assert_not_awaited()
        answer = next(event for event in events if event["type"] == "answer")
        self.assertEqual(answer["confidence"], "medium")
        self.assertEqual(answer["chart_data"][0]["customer_name"], "Private Customer")


if __name__ == "__main__":
    unittest.main()
