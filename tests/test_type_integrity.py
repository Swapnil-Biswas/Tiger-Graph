"""
Unit tests for Type Annotation Integrity and Code Quality Auditor
"""

import sys
import subprocess
import json
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from eval.code_quality_auditor import CodeQualityAuditor, FileQualityMetrics


class TestTypeIntegrity(unittest.TestCase):
    def setUp(self):
        self.auditor = CodeQualityAuditor(min_type_coverage=70.0, strict=True)
        self.src_dir = ROOT_DIR / "src"

    def test_audit_file_clean_sample(self):
        # Audit a known well-typed file like src/api/telemetry.py
        telemetry_file = self.src_dir / "api" / "telemetry.py"
        metrics = self.auditor.audit_file(telemetry_file)

        self.assertGreater(metrics.total_lines, 0)
        self.assertGreater(metrics.total_functions, 0)
        self.assertEqual(metrics.naked_except_count, 0)
        self.assertEqual(metrics.wildcard_import_count, 0)
        self.assertGreaterEqual(metrics.type_coverage, 75.0)

    def test_detection_of_code_smells(self):
        # Create a temporary file with intentional code smells in scratch/
        scratch_dir = ROOT_DIR / "scratch"
        scratch_dir.mkdir(exist_ok=True)
        smelly_file = scratch_dir / "temp_smell_test.py"

        code = (
            "from math import *\n\n"
            "def untyped_func(a, b):\n"
            "    try:\n"
            "        return a + b\n"
            "    except:\n"
            "        return 0\n"
        )
        smelly_file.write_text(code, encoding="utf-8")

        try:
            metrics = self.auditor.audit_file(smelly_file)
            self.assertEqual(metrics.wildcard_import_count, 1)
            self.assertEqual(metrics.naked_except_count, 1)
            self.assertEqual(metrics.annotated_functions, 0)
            self.assertIn("Naked except", metrics.issues[1])
        finally:
            if smelly_file.exists():
                smelly_file.unlink()

    def test_src_codebase_type_coverage(self):
        report = self.auditor.audit_directory(self.src_dir)

        # Core assertions for enterprise code quality
        self.assertGreaterEqual(report.total_files, 50)
        self.assertGreater(report.total_lines, 10000)
        self.assertGreaterEqual(report.overall_type_coverage, 85.0)
        self.assertEqual(report.naked_except_count, 0, "No naked except statements allowed in src/")
        self.assertEqual(report.wildcard_import_count, 0, "No wildcard imports allowed in src/")
        self.assertGreaterEqual(report.overall_quality_score, 0.70)
        self.assertTrue(report.passed)

    def test_cli_json_audit(self):
        script_path = ROOT_DIR / "eval" / "code_quality_auditor.py"
        cmd = [sys.executable, str(script_path), "src", "--strict", "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))

        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertTrue(parsed["passed"])
        self.assertGreaterEqual(parsed["overall_type_coverage"], 85.0)
        self.assertEqual(parsed["naked_except_count"], 0)
        self.assertEqual(parsed["wildcard_import_count"], 0)

    def test_docstring_and_class_detection(self):
        # Verify classes and docstrings are recorded across src/
        report = self.auditor.audit_directory(self.src_dir)
        self.assertGreater(report.total_classes, 100)
        self.assertGreater(report.overall_docstring_coverage, 50.0)


if __name__ == "__main__":
    unittest.main()
