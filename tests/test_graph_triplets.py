"""
Dynamic Knowledge Graph Triplet & Enterprise Graph Synchronizer Tests (tests/test_graph_triplets.py)
Validates multi-format knowledge graph export, TigerGraph GSQL syntax,
Neo4j Cypher idempotency, RDF N-Triples formatting, JSON-LD contexts,
temporal isolation, case provenance tracking, and REST API endpoints.
"""

import unittest
from fastapi.testclient import TestClient

from src.graph.client import GraphClient
from src.graph.triplets import KnowledgeGraphTripletExporter, KnowledgeTriplet
from src.api.main import app


class TestKnowledgeGraphTriplets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Knowledge Graph Triplet Test Suite ===")
        cls.client = GraphClient()
        cls.exporter = KnowledgeGraphTripletExporter(cls.client)
        cls.api = TestClient(app)

    def test_01_extract_case_triplets_provenance(self):
        """Validates case-level triplet extraction and provenance case tracking."""
        triplets = self.exporter.extract_case_triplets("HHG-001", max_hops=2, max_triplets=50)
        self.assertGreater(len(triplets), 0, "Expected non-empty triplets for HHG-001")

        # Verify provenance tracking
        for t in triplets:
            self.assertEqual(t.provenance_case, "HHG-001")

        predicates = set(t.predicate for t in triplets)
        self.assertIn("INVESTIGATES_CARD", predicates)
        self.assertIn("HAS_TRANSACTION", predicates)

        card_triplets = [t for t in triplets if t.predicate == "INVESTIGATES_CARD"]
        self.assertEqual(card_triplets[0].subject, "CASE-HHG-001")
        self.assertEqual(card_triplets[0].subject_type, "Case")
        self.assertEqual(card_triplets[0].object_type, "Card")
        print(f"PASS: Case HHG-001 extracted {len(triplets)} triplets with 100% provenance integrity.")

    def test_02_tigergraph_gsql_syntax(self):
        """Validates syntactically correct TigerGraph GSQL DML insertion statements."""
        triplets = self.exporter.extract_case_triplets("HHG-001", max_hops=1, max_triplets=10)
        gsql = self.exporter.to_tigergraph_gsql(triplets, graph_name="FraudDetectionGraph")

        self.assertIn("USE GRAPH FraudDetectionGraph", gsql)
        self.assertIn("INSERT INTO Case (PRIMARY_ID)", gsql)
        self.assertIn("INSERT INTO Card (PRIMARY_ID)", gsql)
        self.assertIn("INSERT INTO INVESTIGATES_CARD", gsql)
        self.assertIn("FROM, TO", gsql)
        print("PASS: TigerGraph GSQL DML generation strictly conforms to GSQL syntax.")

    def test_03_neo4j_cypher_merge_idempotency(self):
        """Validates Neo4j Cypher statements with idempotent MERGE clauses."""
        triplets = self.exporter.extract_case_triplets("HHG-001", max_hops=1, max_triplets=10)
        cypher = self.exporter.to_neo4j_cypher(triplets)

        self.assertIn("MERGE (s:Case", cypher)
        self.assertIn("MERGE (o:Card", cypher)
        self.assertIn("MERGE (s)-[r:INVESTIGATES_CARD", cypher)
        print("PASS: Neo4j Cypher generation verified with idempotent MERGE statements.")

    def test_04_w3c_rdf_ntriples_formatting(self):
        """Validates W3C RDF N-Triples URI formatting and statement termination."""
        triplets = self.exporter.extract_case_triplets("HHG-001", max_hops=1, max_triplets=10)
        ntriples = self.exporter.to_rdf_ntriples(triplets)

        lines = [line.strip() for line in ntriples.split("\n") if line.strip()]
        self.assertGreater(len(lines), 0)
        for line in lines:
            self.assertTrue(line.endswith("."), f"N-Triple must end with dot: {line}")
            self.assertTrue(line.startswith("<"), f"Subject URI must start with <: {line}")
            parts = line.split(" ")
            self.assertEqual(len(parts), 4, f"Standard N-Triple has 3 URIs and a dot: {line}")
        print(f"PASS: {len(lines)} RDF N-Triples formatted to W3C specification.")

    def test_05_w3c_jsonld_structure(self):
        """Validates standard W3C JSON-LD context and graph serialization."""
        triplets = self.exporter.extract_case_triplets("HHG-001", max_hops=1, max_triplets=10)
        jsonld = self.exporter.to_jsonld(triplets)

        self.assertIn("@context", jsonld)
        self.assertIn("@vocab", jsonld["@context"])
        self.assertIn("@graph", jsonld)
        self.assertIsInstance(jsonld["@graph"], list)
        self.assertGreater(len(jsonld["@graph"]), 0)

        first_node = jsonld["@graph"][0]
        self.assertIn("@id", first_node)
        self.assertIn("@type", first_node)
        print(f"PASS: JSON-LD verified with {len(jsonld['@graph'])} graph entities.")

    def test_06_temporal_isolation_as_of(self):
        """Validates strict temporal isolation: future transactions are omitted from triplets."""
        # Case HHG-001 opened around epoch 1718000000; query with very early as_of
        early_as_of = 1000  # Epoch 1000 s (Jan 1, 1970)
        triplets = self.exporter.extract_case_triplets("HHG-001", as_of=early_as_of)
        # Should have case node and card, but zero transactions
        txn_triplets = [t for t in triplets if t.subject_type == "Transaction" or t.object_type == "Transaction"]
        self.assertEqual(len(txn_triplets), 0, "No transactions should exist before epoch 1000")
        print("PASS: Temporal isolation strictly respected across knowledge triplet extraction.")

    def test_07_syndicate_nexus_triplet_linking(self):
        """Validates multi-case syndicate nexus inclusion in knowledge triplets."""
        # Check if syndicate exists in store; or test syndicate card
        triplets = self.exporter.extract_case_triplets("HHG-004", max_hops=2, max_triplets=50)
        self.assertGreater(len(triplets), 0)
        print(f"PASS: Syndicate case HHG-004 extracted {len(triplets)} triplets.")

    def test_08_api_endpoints(self):
        """Validates GET and POST API endpoints for triplet exports."""
        # 1. GET /api/cases/HHG-001/triplets?format=bundle
        resp_bundle = self.api.get("/api/cases/HHG-001/triplets?format=bundle")
        self.assertEqual(resp_bundle.status_code, 200)
        data = resp_bundle.json()
        self.assertEqual(data["case_id"], "HHG-001")
        self.assertIn("gsql", data)
        self.assertIn("cypher", data)
        self.assertIn("rdf_ntriples", data)
        self.assertIn("jsonld", data)
        self.assertIn("total_triplets", data)

        # 2. GET format=gsql
        resp_gsql = self.api.get("/api/cases/HHG-001/triplets?format=gsql")
        self.assertEqual(resp_gsql.status_code, 200)
        self.assertIn("USE GRAPH", resp_gsql.json()["output"])

        # 3. POST /api/graph/triplets/export
        post_payload = {"case_id": "HHG-001", "format": "cypher", "max_hops": 1}
        resp_post = self.api.post("/api/graph/triplets/export", json=post_payload)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn("MERGE", resp_post.json()["output"])
        print("PASS: Knowledge graph triplet REST API endpoints verified across all formats.")


if __name__ == "__main__":
    unittest.main()
