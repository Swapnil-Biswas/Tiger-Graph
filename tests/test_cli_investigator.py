"""
Unit tests for Terminal Fraud Investigator CLI (src/cli/investigate_cli.py)
"""

import sys
import json
import subprocess
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.cli.investigate_cli import FraudInvestigationCLI, _safe_str


class TestFraudInvestigatorCLI(unittest.TestCase):
    def setUp(self):
        self.cli = FraudInvestigationCLI(root_dir=ROOT_DIR)

    def test_safe_str_sanitization(self):
        self.assertEqual(_safe_str(None), "")
        self.assertEqual(_safe_str("\u2264 0.10"), "<= 0.10")
        self.assertEqual(_safe_str("\u2265 0.90"), ">= 0.90")
        self.assertEqual(_safe_str("A \u2192 B"), "A -> B")

    def test_list_cases(self):
        cases = self.cli.list_cases()
        self.assertEqual(len(cases), 20)
        first = cases[0]
        self.assertEqual(first["case_id"], "HHG-001")
        self.assertIn("verdict", first)
        self.assertIn("exposure_usd", first)
        self.assertIn("pattern", first)
        self.assertIn("sar_required", first)

    def test_get_case_normalization(self):
        case_full = self.cli.get_case("HHG-001")
        case_short = self.cli.get_case("001")
        case_lower = self.cli.get_case("hhg-001")

        self.assertIsNotNone(case_full)
        self.assertIsNotNone(case_short)
        self.assertIsNotNone(case_lower)
        self.assertEqual(case_full["case_id"], "HHG-001")
        self.assertEqual(case_short["case_id"], "HHG-001")
        self.assertEqual(case_lower["case_id"], "HHG-001")

    def test_get_case_invalid(self):
        invalid_case = self.cli.get_case("HHG-999")
        self.assertIsNone(invalid_case)

    def test_benchmark_analytics(self):
        analytics = self.cli.get_benchmark_analytics()
        self.assertEqual(analytics["total_cases"], 20)
        self.assertEqual(analytics["sar_filing_count"], 13)
        self.assertEqual(analytics["verdict_distribution"]["FRAUD"], 17)
        self.assertEqual(analytics["verdict_distribution"]["LEGITIMATE"], 3)
        self.assertGreater(analytics["total_exposure_usd"], 3000.0)

    def test_cli_subprocess_list_json(self):
        script_path = ROOT_DIR / "src" / "cli" / "investigate_cli.py"
        cmd = [sys.executable, str(script_path), "--list", "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))
        self.assertEqual(proc.returncode, 0)
        cases = json.loads(proc.stdout)
        self.assertEqual(len(cases), 20)

    def test_cli_subprocess_case_json(self):
        script_path = ROOT_DIR / "src" / "cli" / "investigate_cli.py"
        cmd = [sys.executable, str(script_path), "--case", "HHG-001", "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["case_id"], "HHG-001")
        self.assertIn("case", data)
        self.assertIn("next_best_actions", data)

    def test_cli_subprocess_benchmark_json(self):
        script_path = ROOT_DIR / "src" / "cli" / "investigate_cli.py"
        cmd = [sys.executable, str(script_path), "--benchmark", "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))
        self.assertEqual(proc.returncode, 0)
        analytics = json.loads(proc.stdout)
        self.assertEqual(analytics["total_cases"], 20)


if __name__ == "__main__":
    unittest.main()
