"""
Unit tests for Demo Asset Packager and Video Script (scripts/package_demo_assets.py)
"""

import sys
import json
import shutil
import subprocess
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.package_demo_assets import DemoAssetPackager, compute_sha256


class TestDemoPackager(unittest.TestCase):
    def setUp(self):
        self.scratch_out = ROOT_DIR / "scratch" / "test_demo_bundle"
        if self.scratch_out.exists():
            shutil.rmtree(self.scratch_out)
        self.packager = DemoAssetPackager(root_dir=ROOT_DIR, output_dir=self.scratch_out)

    def tearDown(self):
        if self.scratch_out.exists():
            shutil.rmtree(self.scratch_out)

    def test_compute_sha256(self):
        test_file = ROOT_DIR / "requirements.txt"
        h = compute_sha256(test_file)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_demo_script_structure(self):
        demo_script = ROOT_DIR / "docs" / "DEMO_SCRIPT.md"
        self.assertTrue(demo_script.is_file())
        content = demo_script.read_text(encoding="utf-8")
        self.assertIn("Scene 1: The Problem", content)
        self.assertIn("Scene 2: Live Case Investigation", content)
        self.assertIn("Scene 3: Multi-Agent Collaborative Consensus", content)
        self.assertIn("Scene 4: Dual-Gate Next Best Actions", content)
        self.assertIn("Scene 5: Real-Time Streaming Influx", content)
        self.assertIn("Scene 6: Enterprise Production Readiness", content)
        self.assertIn("05:00", content)

    def test_package_and_verify_bundle(self):
        manifest = self.packager.package_assets()
        self.assertGreaterEqual(manifest["total_files"], 6)
        self.assertIn("sample_sar_filing.xml", manifest["files"])
        self.assertIn("index.html", manifest["files"])

        # Verify bundle
        ok, msg = self.packager.verify_bundle()
        self.assertTrue(ok)
        self.assertIn("verified", msg)

    def test_verify_bundle_detects_tamper(self):
        self.packager.package_assets()
        # Tamper with one file
        tamper_target = self.scratch_out / "sample_sar_filing.xml"
        tamper_target.write_text("<TamperedContent/>", encoding="utf-8")

        ok, msg = self.packager.verify_bundle()
        self.assertFalse(ok)
        self.assertIn("Checksum mismatch", msg)

    def test_cli_execution_json(self):
        script_path = ROOT_DIR / "scripts" / "package_demo_assets.py"
        test_dir = ROOT_DIR / "scratch" / "test_cli_bundle"
        cmd = [sys.executable, str(script_path), "--output-dir", str(test_dir.relative_to(ROOT_DIR)), "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))

        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertTrue(parsed["verified"])
        self.assertIn("manifest", parsed)

        if test_dir.exists():
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
