import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.models.request_context import SaaSRequestContext
from app.services.tool_chat_pipeline import process_tool_chat
from app.services.tool_client import ToolClientError


class ResilienceTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        now = datetime.now(timezone.utc)
        return SaaSRequestContext(
            user_id=uuid4(),
            org_id=uuid4(),
            role="admin",
            allowed_location_ids=(uuid4(),),
            permissions=frozenset({"insights"}),
            features=frozenset({"ai_features"}),
            request_id="resilience-test",
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

    async def test_saas_tool_timeout_or_error_yields_graceful_error(self):
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new_callable=AsyncMock,
        ) as tool:
            tool.side_effect = ToolClientError("SaaS backend timeout or 503")
            events = await self.collect("Summarize sales")
            
        error_event = next(event for event in events if event["type"] == "error")
        self.assertEqual(error_event["code"], "AI_TOOL_UNAVAILABLE")
        self.assertIn("SaaS backend timeout", error_event["message"])
        self.assertTrue(error_event["retryable"])

    async def test_gemini_outage_yields_graceful_error_event(self):
        """
        When the LLM raises, process_tool_chat must not propagate the raw
        exception to the caller. It must yield a retryable error NDJSON event
        and then a done event, so the client can display a safe message.
        """
        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            new_callable=AsyncMock,
        ) as tool, patch(
            "app.services.tool_chat_pipeline.generate_reasoning",
            new_callable=AsyncMock,
        ) as llm:
            tool.return_value = {"success": True, "tool": "sales_summary", "data": {}}
            llm.side_effect = Exception("Gemini API 503 Service Unavailable")

            events = await self.collect("Summarize sales")

        event_types = [e["type"] for e in events]
        self.assertIn("error", event_types, "Must emit an error event, not propagate raw exception")
        error_event = next(e for e in events if e["type"] == "error")
        self.assertTrue(
            error_event.get("retryable"),
            "LLM outage error must be marked retryable",
        )
        # The raw exception message must not leak to the client
        self.assertNotIn(
            "Gemini API 503",
            error_event.get("message", ""),
            "Raw upstream error must not be forwarded to the client",
        )
        self.assertIn("done", event_types, "Must always end with a done event")

    async def test_browser_cancellation_propagates_upstream(self):
        """
        Confirms the generator can be abandoned mid-flight without hanging or
        raising an unhandled error, and that CancelledError propagates when
        the generator task is explicitly cancelled.
        """
        slow_tool_started = asyncio.Event()

        async def slow_tool(*args, **kwargs):
            slow_tool_started.set()
            await asyncio.sleep(30)
            return {"success": True, "tool": "sales_summary", "data": {}}

        with patch(
            "app.services.tool_chat_pipeline.call_saas_tool",
            side_effect=slow_tool,
        ):
            gen = process_tool_chat(
                "Summarize sales", None, None, self.context(), "delegation-token"
            )

            async def drain():
                async for _ in gen:
                    pass

            task = asyncio.create_task(drain())
            # Wait until the slow tool has started so we know the generator is running
            try:
                await asyncio.wait_for(slow_tool_started.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass  # Tool may not have been reached yet; cancel anyway

            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task


if __name__ == "__main__":
    unittest.main()
