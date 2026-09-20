"""
Unit tests for Extended 50-Case High-Stress Benchmark Suite
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

from eval.extended_benchmark_generator import (
    generate_extended_case,
    generate_extended_benchmark,
)
from eval.extended_benchmark_evaluator import ExtendedBenchmarkEvaluator


class TestExtendedBenchmark(unittest.TestCase):
    def setUp(self):
        self.extended_dir = ROOT_DIR / "eval" / "extended_cases"
        self.scratch_dir = ROOT_DIR / "scratch" / "test_ext_cases"
        if self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir)

    def tearDown(self):
        if self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir)

    def test_generate_single_case(self):
        case_fraud = generate_extended_case(1)
        self.assertEqual(case_fraud["case_id"], "EXT-001")
        self.assertEqual(case_fraud["case"]["verdict"], "fraud")
        self.assertGreater(case_fraud["case"]["exposure_usd"], 0.0)
        self.assertGreater(len(case_fraud["case"]["affected_txn_ids"]), 0)

        case_legit = generate_extended_case(10)
        self.assertEqual(case_legit["case_id"], "EXT-010")
        self.assertEqual(case_legit["case"]["verdict"], "legitimate")
        self.assertEqual(case_legit["case"]["exposure_usd"], 0.0)
        self.assertEqual(len(case_legit["case"]["affected_txn_ids"]), 0)
        self.assertEqual(case_legit["case"]["first_suspicious_txn_id"], "")

    def test_generate_benchmark_batch(self):
        files = generate_extended_benchmark(self.scratch_dir, count=10)
        self.assertEqual(len(files), 10)
        for f in files:
            self.assertTrue(f.is_file())

    def test_evaluator_on_extended_suite(self):
        evaluator = ExtendedBenchmarkEvaluator(self.extended_dir)
        results = evaluator.evaluate_all()

        self.assertEqual(results["status"], "PASS")
        self.assertEqual(results["total_cases"], 50)
        self.assertEqual(results["passed_cases"], 50)
        self.assertEqual(results["failed_cases"], 0)
        self.assertEqual(results["pass_rate_pct"], 100.0)
        self.assertEqual(results["fraud_cases"], 38)
        self.assertEqual(results["legitimate_cases"], 12)

    def test_evaluator_detects_corrupt_case(self):
        # Generate small batch in scratch and corrupt one
        generate_extended_benchmark(self.scratch_dir, count=3)
        corrupt_file = self.scratch_dir / "EXT-001.json"
        data = json.loads(corrupt_file.read_text(encoding="utf-8"))
        del data["case"]["verdict"]  # Corrupt schema
        corrupt_file.write_text(json.dumps(data), encoding="utf-8")

        evaluator = ExtendedBenchmarkEvaluator(self.scratch_dir)
        results = evaluator.evaluate_all()
        self.assertEqual(results["status"], "FAIL")
        self.assertGreater(results["failed_cases"], 0)

    def test_cli_json_mode(self):
        script_path = ROOT_DIR / "eval" / "extended_benchmark_evaluator.py"
        cmd = [sys.executable, str(script_path), "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))

        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertEqual(parsed["status"], "PASS")
        self.assertEqual(parsed["total_cases"], 50)


if __name__ == "__main__":
    unittest.main()
