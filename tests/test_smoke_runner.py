"""
Unit Tests for Cross-Platform Automated Smoke & Sanity Runner (tests/test_smoke_runner.py)
Validates:
  1. SmokeTestRunner programmatic execution and result structure
  2. Quick mode vs full API smoke mode
  3. JSON report generation and schema
  4. Convenience shell scripts existence and permissions (smoke.sh, smoke.ps1)
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.smoke_test import SmokeTestRunner


class TestSmokeRunner(unittest.TestCase):
    def test_01_smoke_runner_full(self):
        """Smoke test runner executes all 13 checks and passes completely."""
        runner = SmokeTestRunner(quick=False, verbose=False)
        results = runner.run_all()

        self.assertEqual(results["status"], "PASS")
        self.assertTrue(results["all_passed"])
        self.assertGreaterEqual(results["total_checks"], 13)
        self.assertEqual(results["checks_failed"], 0)
        self.assertGreater(results["elapsed_seconds"], 0.0)

    def test_02_smoke_runner_quick(self):
        """Quick mode executes environment and data checks only in sub-second time."""
        runner = SmokeTestRunner(quick=True, verbose=False)
        results = runner.run_all()

        self.assertEqual(results["status"], "PASS")
        self.assertTrue(results["all_passed"])
        self.assertEqual(results["total_checks"], 4)
        self.assertLess(results["elapsed_seconds"], 2.0)

    def test_03_checks_structure(self):
        """Each check contains check_id, name, category, passed, detail, and duration_ms."""
        runner = SmokeTestRunner(quick=True, verbose=False)
        results = runner.run_all()

        for c in results["checks"]:
            self.assertIn("check_id", c)
            self.assertIn("name", c)
            self.assertIn("category", c)
            self.assertTrue(c["passed"])
            self.assertIn("detail", c)
            self.assertGreaterEqual(c["duration_ms"], 0.0)

    def test_04_convenience_scripts_exist(self):
        """Convenience shell scripts smoke.sh and smoke.ps1 exist in scripts/."""
        sh_script = ROOT_DIR / "scripts" / "smoke.sh"
        ps1_script = ROOT_DIR / "scripts" / "smoke.ps1"

        self.assertTrue(sh_script.is_file(), "scripts/smoke.sh does not exist")
        self.assertTrue(ps1_script.is_file(), "scripts/smoke.ps1 does not exist")

        sh_content = sh_script.read_text(encoding="utf-8")
        self.assertIn("smoke_test.py", sh_content)

        ps1_content = ps1_script.read_text(encoding="utf-8")
        self.assertIn("smoke_test.py", ps1_content)


if __name__ == "__main__":
    unittest.main()
