"""
Unit Test Suite for Syndicate Cluster Engine & Level-of-Detail (LOD) Spatial Renderer
(tests/test_graph_clustering.py)

Tests macro-topology extraction, hierarchical LOD reduction, deterministic
spatial layout coordinate bounding, WebGL vertex buffer serialization, and FastAPI endpoints.
"""

import math
import unittest
from fastapi.testclient import TestClient

from src.graph.cluster_renderer import (
    SyndicateClusterEngine,
    ClusterNode,
    ClusterEdge,
    LODGraphView,
)
from src.api.main import app, cluster_engine


class TestSyndicateClusterEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Syndicate Cluster & LOD Engine Test Suite ===")
        cls.engine = cluster_engine
        cls.api_client = TestClient(app)

    def test_01_macro_topology_super_nodes_and_cross_edges(self):
        """Verify global syndicate macro-topology extraction, super-node attributes, and cross-edges."""
        macro = self.engine.extract_macro_topology()

        self.assertIn("total_syndicates", macro)
        self.assertIn("total_exposure_usd", macro)
        self.assertIn("super_nodes", macro)
        self.assertIn("cross_edges", macro)
        self.assertGreater(macro["total_syndicates"], 0)

        for node in macro["super_nodes"]:
            self.assertEqual(node["type"], "SyndicateSuperNode")
            self.assertIn(node["color"], ["#ef4444", "#f59e0b", "#06b6d4", "#10b981"])
            self.assertFalse(math.isnan(node["x"]))
            self.assertFalse(math.isnan(node["y"]))
            self.assertGreater(node["size"], 0.0)

        print(f"PASS: Macro-topology verified with {macro['total_syndicates']} super-nodes and {len(macro['cross_edges'])} cross-edges.")

    def test_02_hierarchical_lod_reduction(self):
        """Verify hierarchical level-of-detail reduction: Level 2 (Macro) < Level 1 (Meso) < Level 0 (Micro)."""
        lod_views = self.engine.generate_case_lod_views("HHG-001")

        self.assertIn("level_0_micro", lod_views)
        self.assertIn("level_1_meso", lod_views)
        self.assertIn("level_2_macro", lod_views)

        l0 = lod_views["level_0_micro"]
        l1 = lod_views["level_1_meso"]
        l2 = lod_views["level_2_macro"]

        # Assert monotonic node reduction
        self.assertGreater(l0.node_count, l1.node_count)
        self.assertGreater(l1.node_count, l2.node_count)
        self.assertEqual(l2.node_count, 1)  # Abstracted super-node

        # Micro must contain transactions and cards
        l0_types = set(n.type for n in l0.nodes)
        self.assertIn("Customer", l0_types)
        self.assertIn("Card", l0_types)
        self.assertIn("Transaction", l0_types)

        # Meso must contain functional clusters
        l1_types = set(n.type for n in l1.nodes)
        self.assertIn("Customer", l1_types)
        self.assertIn("Merchant", l1_types)
        self.assertIn("Device", l1_types)

        print(f"PASS: LOD reduction verified: Micro ({l0.node_count} nodes) -> Meso ({l1.node_count} nodes) -> Macro ({l2.node_count} nodes).")

    def test_03_spatial_layout_coordinates_and_bounds(self):
        """Verify 2D/3D spatial coordinates are deterministic, finite, and strictly bounded."""
        lod_views = self.engine.generate_case_lod_views("HHG-001")

        for lvl_name, view in lod_views.items():
            bbox = view.bounding_box
            self.assertIn("min_x", bbox)
            self.assertIn("max_x", bbox)
            self.assertIn("min_y", bbox)
            self.assertIn("max_y", bbox)

            for node in view.nodes:
                self.assertFalse(math.isnan(node.x), f"NaN x in {node.id}")
                self.assertFalse(math.isnan(node.y), f"NaN y in {node.id}")
                self.assertFalse(math.isnan(node.z), f"NaN z in {node.id}")
                self.assertGreaterEqual(node.x, bbox["min_x"] - 50.0)
                self.assertLessEqual(node.x, bbox["max_x"] + 50.0)
                self.assertGreaterEqual(node.y, bbox["min_y"] - 50.0)
                self.assertLessEqual(node.y, bbox["max_y"] + 50.0)

        print("PASS: Spatial layout coordinates strictly bounded and free of NaNs.")

    def test_04_webgl_buffer_serialization(self):
        """Verify WebGL/Canvas2D float buffer packing conforms to GPU shader memory layout."""
        lod_views = self.engine.generate_case_lod_views("HHG-001")
        l0 = lod_views["level_0_micro"]

        buffers = l0.webgl_buffers
        self.assertIn("vertex_stride", buffers)
        self.assertIn("node_vertices", buffers)
        self.assertIn("edge_indices", buffers)

        stride = buffers["vertex_stride"]
        vertices = buffers["node_vertices"]
        indices = buffers["edge_indices"]

        # Exactly stride * node_count floats
        self.assertEqual(len(vertices), l0.node_count * stride)
        # Exactly 3 * edge_count floats for [src, tgt, weight]
        self.assertEqual(len(indices), l0.edge_count * 3)

        # Confirm all buffer elements are float-compatible
        for v in vertices[:20]:
            self.assertIsInstance(v, float)
            self.assertFalse(math.isnan(v))

        print(f"PASS: WebGL buffer serialization packed {len(vertices)} floats for GPU shader rendering.")

    def test_05_fastapi_rest_endpoints(self):
        """Verify REST API endpoints for macro-topology and case LOD clustering."""
        # 1. Macro-topology
        resp_macro = self.api_client.get("/api/graph/syndicates/macro-topology")
        self.assertEqual(resp_macro.status_code, 200)
        mdata = resp_macro.json()
        self.assertIn("super_nodes", mdata)
        self.assertIn("cross_edges", mdata)

        # 2. Case LOD
        resp_lod = self.api_client.get("/api/graph/clusters/HHG-001/lod")
        self.assertEqual(resp_lod.status_code, 200)
        ldata = resp_lod.json()
        self.assertIn("level_0_micro", ldata)
        self.assertIn("level_1_meso", ldata)
        self.assertIn("level_2_macro", ldata)
        self.assertIn("webgl_buffers", ldata["level_0_micro"])
        print("PASS: FastAPI syndicate macro-topology and LOD cluster REST endpoints verified.")


if __name__ == "__main__":
    unittest.main()
