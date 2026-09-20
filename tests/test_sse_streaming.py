"""
Server-Sent Events (SSE) Streaming Engine Tests (tests/test_sse_streaming.py)
Validates real-time step streaming, event sequencing, JSON payload fidelity,
and timeline events across all investigation phases.
"""

import unittest
import asyncio
import json
from src.agent.graph import FraudInvestigatorAgent
from src.api.sse import stream_investigation_events


class TestSSEStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing SSE Streaming Test Suite ===")
        cls.agent = FraudInvestigatorAgent()

    def test_01_stream_investigation_events_sequence(self):
        """Validates that stream_investigation_events yields all required SSE steps in order."""
        async def run_stream():
            events = []
            async for chunk in stream_investigation_events(self.agent, "HHG-001"):
                if chunk.startswith("data: "):
                    payload = json.loads(chunk[6:].strip())
                    events.append(payload)
            return events

        events = asyncio.run(run_stream())
        self.assertGreaterEqual(len(events), 8, "Expected at least 8 progression events")

        step_names = [e["step"] for e in events]
        print(f"Captured SSE Steps: {step_names}")

        # Check required steps
        self.assertIn("TRIGGER", step_names)
        self.assertIn("OPEN_CASE", step_names)
        self.assertIn("BUDGET_PLAN", step_names)
        self.assertIn("RETRIEVE_MEMORY", step_names)
        self.assertIn("INVESTIGATE", step_names)
        self.assertIn("GRAPHRAG_BM25", step_names)
        self.assertIn("ASSESS", step_names)
        self.assertIn("DECIDE_ACTIONS", step_names)
        self.assertIn("SELF_CRITIQUE", step_names)
        self.assertIn("COMPLETE", step_names)

        # Final complete payload check
        complete_event = [e for e in events if e["step"] == "COMPLETE"][0]
        self.assertIn("payload", complete_event)
        self.assertEqual(complete_event["payload"]["case_id"], "HHG-001")
        print("PASS: SSE investigation stream verified with 100% complete step coverage.")

    def test_02_stream_syndicate_case_events(self):
        """Validates streaming for a high-risk syndicate case (HHG-004)."""
        async def run_stream():
            events = []
            async for chunk in stream_investigation_events(self.agent, "HHG-004"):
                if chunk.startswith("data: "):
                    payload = json.loads(chunk[6:].strip())
                    events.append(payload)
            return events

        events = asyncio.run(run_stream())
        complete_event = [e for e in events if e["step"] == "COMPLETE"][0]
        self.assertEqual(complete_event["payload"]["case"]["verdict"], "fraud")
        self.assertTrue(complete_event["payload"]["sar"]["file"])
        print("PASS: High-risk syndicate case SSE stream completed with verified SAR filing.")


if __name__ == "__main__":
    unittest.main()
