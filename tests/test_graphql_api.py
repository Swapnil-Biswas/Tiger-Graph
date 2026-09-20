"""
Unit tests for GraphQL Schema Definition, Query Resolvers, and FastAPI Endpoints
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.api.graphql_schema import GraphQLSchema, FraudGraphQLResolver, GraphQLParser
from src.api.main import app


class TestGraphQLSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = GraphQLSchema()
        cls.client = TestClient(app)

    def test_query_single_case(self):
        query = """
        query GetCase {
          case(caseId: "HHG-001") {
            case_id
            verdict
            fraud_probability
            exposure
            actions {
              action
              level
            }
            sar {
              file
              reason
            }
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        self.assertIn("data", res)
        case_data = res["data"]["case"]
        self.assertIsNotNone(case_data)
        self.assertEqual(case_data["case_id"], "HHG-001")
        self.assertEqual(case_data["verdict"].lower(), "fraud")
        self.assertGreater(case_data["fraud_probability"], 0.7)
        self.assertGreater(case_data["exposure"], 0)
        self.assertIsInstance(case_data["actions"], list)
        self.assertIn("file", case_data["sar"])

    def test_query_cases_list(self):
        query = """
        query ListCases {
          cases(limit: 3, verdict: "FRAUD") {
            case_id
            verdict
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        cases = res["data"]["cases"]
        self.assertLessEqual(len(cases), 3)
        for c in cases:
            self.assertEqual(c["verdict"].lower(), "fraud")

    def test_query_customer(self):
        query = """
        query GetCust {
          customer(customerId: "C1001") {
            customer_id
            card_count
            device_count
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        cust = res["data"]["customer"]
        self.assertEqual(cust["customer_id"], "C1001")
        self.assertGreaterEqual(cust["card_count"], 0)

    def test_query_audit_ledger(self):
        query = """
        query CheckAudit {
          auditLedger(limit: 3) {
            is_valid
            message
            block_count
            entries {
              index
              case_id
            }
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        ledger = res["data"]["auditLedger"]
        self.assertTrue(ledger["is_valid"])
        self.assertGreaterEqual(ledger["block_count"], 0)

    def test_query_benchmark_summary(self):
        query = """
        query GetBenchmark {
          benchmarkSummary {
            total_cases
            fraud_cases
            legitimate_cases
            precision
            f1_score
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        b = res["data"]["benchmarkSummary"]
        self.assertEqual(b["total_cases"], 20)
        self.assertEqual(b["fraud_cases"] + b["legitimate_cases"], 20)
        self.assertEqual(b["f1_score"], 1.0)

    def test_schema_introspection(self):
        query = """
        query Introspection {
          __schema {
            query_fields
          }
        }
        """
        res = self.schema.execute(query)
        self.assertNotIn("errors", res)
        qf = res["data"]["__schema"]["query_fields"]
        self.assertIn("case", qf)
        self.assertIn("cases", qf)
        self.assertIn("customer", qf)
        self.assertIn("auditLedger", qf)
        self.assertIn("benchmarkSummary", qf)

    def test_query_variables_and_aliases(self):
        query = """
        query AliasQuery($id: String!) {
          targetCase: case(caseId: $id) {
            case_id
            verdict
          }
        }
        """
        res = self.schema.execute(query, variables={"id": "HHG-002"})
        self.assertNotIn("errors", res)
        self.assertIn("targetCase", res["data"])
        self.assertEqual(res["data"]["targetCase"]["case_id"], "HHG-002")

    def test_syntax_error_and_invalid_field(self):
        bad_query = "query Bad { invalidField }"
        res = self.schema.execute(bad_query)
        self.assertIn("errors", res)
        self.assertIn("Cannot query field 'invalidField'", res["errors"][0]["message"])

    def test_fastapi_graphql_endpoints(self):
        # Test POST /graphql
        post_resp = self.client.post(
            "/graphql",
            json={"query": '{ case(caseId: "HHG-001") { case_id verdict } }'}
        )
        self.assertEqual(post_resp.status_code, 200)
        json_data = post_resp.json()
        self.assertIn("data", json_data)
        self.assertEqual(json_data["data"]["case"]["case_id"], "HHG-001")

        # Test GET /graphql with query parameter
        get_resp = self.client.get(
            "/graphql?query={ benchmarkSummary { total_cases } }"
        )
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()
        self.assertEqual(get_data["data"]["benchmarkSummary"]["total_cases"], 20)

        # Test GET /graphql without query parameter (returns GraphiQL HTML)
        html_resp = self.client.get("/graphql")
        self.assertEqual(html_resp.status_code, 200)
        self.assertIn("TigerGraph Agentic GraphQL Explorer", html_resp.text)


if __name__ == "__main__":
    unittest.main()
