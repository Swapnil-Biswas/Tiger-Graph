"""
Unit Tests for Architecture Documentation Integrity and Component Link Verification
(tests/test_architecture_docs.py)
"""

import os
import re
import unittest


class TestArchitectureDocumentation(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.arch_doc_path = os.path.join(self.repo_root, "docs", "ARCHITECTURE.md")

    def test_01_architecture_doc_structure(self):
        """Verify ARCHITECTURE.md exists, has substantial content, and contains Mermaid diagrams."""
        self.assertTrue(os.path.exists(self.arch_doc_path), "docs/ARCHITECTURE.md must exist")
        with open(self.arch_doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(len(content) > 3000, f"Expected > 3000 characters, found {len(content)}")

        # Check for Mermaid code blocks
        mermaid_blocks = re.findall(r"```mermaid(.*?)```", content, re.DOTALL)
        self.assertTrue(len(mermaid_blocks) >= 4, f"Expected at least 4 Mermaid blocks, found {len(mermaid_blocks)}")

    def test_02_architecture_core_components_coverage(self):
        """Verify that all core platform components are documented in the architecture specification."""
        with open(self.arch_doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        core_components = [
            "FraudInvestigatorAgent",
            "AMLSpecialistAgent",
            "CyberForensicsAgent",
            "StreamingGraphMonitor",
            "EnterpriseTelemetryRegistry",
            "EnterpriseWebhookDispatcher",
            "FinCENSARXMLPackager",
            "ComplianceEvidencePackager",
            "AdaptiveGraphBudgeter",
            "FederatedMemoryBus",
            "Personalized PageRank",
            "HorizontalPodAutoscaler",
        ]
        for comp in core_components:
            self.assertIn(comp, content, f"Component {comp} must be referenced in docs/ARCHITECTURE.md")

    def test_03_component_reference_table_file_links(self):
        """Verify that all files referenced in the Component Reference table exist in the repository."""
        with open(self.arch_doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract file links like [`src/agent/graph.py`](file:///...)
        matches = re.findall(r"\[`([^`]+)`\]", content)
        self.assertTrue(len(matches) >= 10, f"Expected at least 10 linked components, found {len(matches)}")

        for rel_path in matches:
            abs_path = os.path.join(self.repo_root, rel_path)
            self.assertTrue(os.path.exists(abs_path), f"Referenced file {rel_path} does not exist at {abs_path}")


if __name__ == "__main__":
    unittest.main()
