"""
Unit Test Suite for UI Compliance Vault & Temporal Playback Integration
(tests/test_ui_bundle.py)

Validates static HTML/CSS/JS delivery, required DOM element IDs,
navigation tabs, and integration with backend APIs backing the UI views.
"""

import unittest
from fastapi.testclient import TestClient
from src.api.main import app


class TestUIBundleIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing UI Compliance Vault & Playback Test Suite ===")
        cls.client = TestClient(app)

    def test_01_static_ui_serving_and_tabs(self):
        """Verify index.html serves with 200 OK and contains the Compliance Vault and Playback tabs."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.text

        # Verify navigation tabs exist
        self.assertIn('id="tab-compliance"', html)
        self.assertIn('Compliance Vault (FRE 902)', html)
        self.assertIn('id="tab-playback"', html)
        self.assertIn('Temporal Playback', html)

        # Verify sections exist
        self.assertIn('id="view-compliance"', html)
        self.assertIn('id="view-playback"', html)
        print("PASS: Static UI index.html served with compliance and playback navigation tabs.")

    def test_02_compliance_vault_dom_elements(self):
        """Verify all interactive elements and security badges exist in index.html."""
        resp = self.client.get("/")
        html = resp.text

        required_ids = [
            'select-compliance-case',
            'btn-generate-bundle',
            'btn-verify-bundle',
            'btn-tamper-test',
            'vault-bundle-id',
            'vault-legal-status',
            'vault-status-tag',
            'vault-merkle-root',
            'vault-signature',
            'vault-signer',
            'vault-items-count',
            'vault-items-container',
            'vault-custody-timeline',
        ]
        for elem_id in required_ids:
            self.assertIn(f'id="{elem_id}"', html, f"Missing element id='{elem_id}' in index.html")
        print("PASS: All required compliance vault DOM elements verified.")

    def test_03_temporal_playback_dom_elements(self):
        """Verify playback scrubber and cytoscape canvas elements exist in index.html."""
        resp = self.client.get("/")
        html = resp.text

        required_ids = [
            'select-playback-case',
            'btn-load-playback',
            'btn-playback-step-back',
            'btn-playback-play',
            'btn-playback-step-forward',
            'playback-step-cur',
            'playback-step-total',
            'playback-exposure',
            'playback-risk',
            'playback-slider',
            'playback-milestones-container',
            'playback-caption-text',
            'cy-playback-container',
        ]
        for elem_id in required_ids:
            self.assertIn(f'id="{elem_id}"', html, f"Missing element id='{elem_id}' in index.html")
        print("PASS: All required temporal playback scrubber DOM elements verified.")

    def test_04_static_assets_css_js(self):
        """Verify app.js and style.css are served with 200 OK and contain new features."""
        # CSS
        resp_css = self.client.get("/style.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn(".certificate-card", resp_css.text)
        self.assertIn(".playback-slider", resp_css.text)
        self.assertIn(".vault-item-card", resp_css.text)

        # JS
        resp_js = self.client.get("/app.js")
        self.assertEqual(resp_js.status_code, 200)
        self.assertIn("loadEvidenceVault", resp_js.text)
        self.assertIn("verifyEvidenceVault", resp_js.text)
        self.assertIn("simulateTamperVault", resp_js.text)
        self.assertIn("loadPlaybackTimeline", resp_js.text)
        self.assertIn("renderPlaybackFrame", resp_js.text)
        print("PASS: Static CSS and JS assets verified with required functions and selectors.")

    def test_05_backend_payload_compatibility_for_ui(self):
        """Verify backend APIs return data conforming to UI consumption contracts."""
        # Evidence bundle
        resp_bundle = self.client.get("/api/cases/HHG-001/evidence-bundle")
        self.assertEqual(resp_bundle.status_code, 200)
        bdata = resp_bundle.json()
        self.assertIn("bundle_id", bdata)
        self.assertIn("merkle_root", bdata)
        self.assertIn("signature", bdata)
        self.assertIn("items", bdata)
        self.assertIn("chain_of_custody", bdata)

        # Playback
        resp_play = self.client.get("/api/graph/playback/HHG-001")
        self.assertEqual(resp_play.status_code, 200)
        pdata = resp_play.json()
        self.assertIn("case_id", pdata)
        self.assertIn("total_frames", pdata)
        self.assertIn("frames", pdata)
        self.assertIn("milestones", pdata)
        print("PASS: Backend API payload contracts verified for UI ingestion.")


if __name__ == "__main__":
    unittest.main()
