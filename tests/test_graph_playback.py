"""
Unit Test Suite for Interactive Temporal Graph Playback & Syndicate Cascade Visualizer (tests/test_graph_playback.py)
Tests frame-by-frame graph evolution, cumulative ego-net expansion,
BSA/velocity milestone detection, narrative cue generation, and FastAPI endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.playback import (
    TemporalGraphPlaybackEngine,
    PlaybackStep,
    PlaybackTimeline,
)
from src.graph.client import GraphClient
from src.api.main import app


class TestTemporalGraphPlaybackEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Temporal Graph Playback Test Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.engine = TemporalGraphPlaybackEngine(client=cls.client)

    def test_case_playback_generation(self):
        """Verify playback timeline generated with seed entities and final decision frames."""
        timeline = self.engine.generate_case_playback("HHG-001")

        self.assertEqual(timeline.case_id, "HHG-001")
        self.assertGreaterEqual(timeline.total_frames, 2)
        self.assertEqual(len(timeline.frames), timeline.total_frames)

        # Frame 0: Baseline Account Setup
        frame0 = timeline.frames[0]
        self.assertEqual(frame0.frame_index, 0)
        self.assertEqual(frame0.event_category, "SEED_ENTITY")
        self.assertIn("baseline established", frame0.narrative_caption.lower())

        # Final Frame: Consensus & Action Enforcement
        final_frame = timeline.frames[-1]
        self.assertEqual(final_frame.event_category, "FINAL_DECISION")
        self.assertIn("final", final_frame.narrative_caption.lower())
        print("PASS: Baseline and final playback frames verified.")

    def test_cumulative_ego_net_expansion(self):
        """Verify nodes and edges expand monotonically across the playback frames."""
        timeline = self.engine.generate_case_playback("HHG-001")

        node_counts = [len(f.cumulative_elements.get("nodes", [])) for f in timeline.frames]
        edge_counts = [len(f.cumulative_elements.get("edges", [])) for f in timeline.frames]

        # Each frame must maintain or increase graph elements
        for i in range(1, len(node_counts)):
            self.assertGreaterEqual(node_counts[i], node_counts[i - 1])
            self.assertGreaterEqual(edge_counts[i], edge_counts[i - 1])

        print("PASS: Monotonic cumulative ego-net expansion verified.")

    def test_milestone_detection(self):
        """Verify BSA structuring and baseline milestones are captured in timeline metadata."""
        timeline = self.engine.generate_case_playback("HHG-004")

        self.assertIn("baseline_opened", timeline.milestones)
        self.assertIn("decision_enforced", timeline.milestones)
        # Check exposure accumulation
        self.assertGreater(timeline.total_exposure_usd, 0.0)
        print("PASS: Milestone tracking and exposure accumulation verified.")

    def test_narrative_captions_and_highlights(self):
        """Verify each frame contains human-readable captions and highlighted active elements."""
        timeline = self.engine.generate_case_playback("HHG-001")

        for frame in timeline.frames:
            self.assertTrue(len(frame.narrative_caption) > 10)
            self.assertGreaterEqual(len(frame.highlight_node_ids), 1)
            self.assertTrue(0.0 <= frame.risk_score <= 1.0)
        print("PASS: Narrative captions, risk scoring, and element highlighting verified.")

    def test_fastapi_playback_endpoints(self):
        """Verify REST API endpoints for graph playback timeline and individual frames."""
        client = TestClient(app)

        # 1. Full playback timeline
        resp_tl = client.get("/api/graph/playback/HHG-001")
        self.assertEqual(resp_tl.status_code, 200)
        tl_data = resp_tl.json()
        self.assertEqual(tl_data["case_id"], "HHG-001")
        self.assertGreaterEqual(tl_data["total_frames"], 2)

        # 2. Individual frame query
        resp_f0 = client.get("/api/graph/playback/HHG-001/frame/0")
        self.assertEqual(resp_f0.status_code, 200)
        f0_data = resp_f0.json()
        self.assertEqual(f0_data["frame_index"], 0)
        self.assertEqual(f0_data["event_category"], "SEED_ENTITY")

        # 3. Out of range frame
        resp_err = client.get("/api/graph/playback/HHG-001/frame/9999")
        self.assertEqual(resp_err.status_code, 404)
        print("PASS: FastAPI graph playback REST endpoints verified.")


if __name__ == "__main__":
    unittest.main()
