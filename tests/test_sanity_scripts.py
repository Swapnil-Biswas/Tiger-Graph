"""
Unit tests for Clean Clone Sanity & Verification Script (scripts/verify_install.py)
"""

import sys
import subprocess
import json
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.verify_install import (
    check_python_version,
    check_dependencies,
    check_project_structure,
    check_benchmark_cases,
    run_sanity_checks,
)


class TestSanityScripts(unittest.TestCase):
    def test_check_python_version(self):
        passed, msg = check_python_version(min_major=3, min_minor=10)
        self.assertTrue(passed)
        self.assertIn("Python", msg)

        # Test failure case for future version
        failed, fail_msg = check_python_version(min_major=4, min_minor=99)
        self.assertFalse(failed)

    def test_check_dependencies(self):
        req_file = ROOT_DIR / "requirements.txt"
        all_passed, results = check_dependencies(req_file)
        self.assertTrue(all_passed)
        self.assertIn("pydantic", results)
        self.assertIn("fastapi", results)
        self.assertTrue(results["pydantic"])
        self.assertTrue(results["fastapi"])

    def test_check_project_structure(self):
        passed, missing = check_project_structure(ROOT_DIR)
        self.assertTrue(passed)
        self.assertEqual(len(missing), 0)

        # Test failure case on empty directory
        fake_dir = ROOT_DIR / "tests"
        fail_passed, fail_missing = check_project_structure(fake_dir)
        self.assertFalse(fail_passed)
        self.assertGreater(len(fail_missing), 0)

    def test_check_benchmark_cases(self):
        passed, found, expected = check_benchmark_cases(ROOT_DIR)
        self.assertTrue(passed)
        self.assertEqual(found, 20)
        self.assertEqual(expected, 20)

    def test_run_sanity_checks_quick(self):
        results = run_sanity_checks(ROOT_DIR, quick=True)
        self.assertEqual(results["status"], "PASS")
        self.assertTrue(results["python"]["passed"])
        self.assertTrue(results["dependencies"]["passed"])
        self.assertTrue(results["structure"]["passed"])
        self.assertTrue(results["benchmark_cases"]["passed"])
        self.assertEqual(results["demo_path"]["detail"], "Skipped")

    def test_cli_json_mode(self):
        script_path = ROOT_DIR / "scripts" / "verify_install.py"
        cmd = [sys.executable, str(script_path), "--quick", "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT_DIR))
        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertEqual(parsed["status"], "PASS")
        self.assertIn("python", parsed)
        self.assertIn("dependencies", parsed)

    def test_convenience_scripts_exist(self):
        sh_script = ROOT_DIR / "scripts" / "run_all.sh"
        ps1_script = ROOT_DIR / "scripts" / "run_all.ps1"
        self.assertTrue(sh_script.is_file())
        self.assertTrue(ps1_script.is_file())
        self.assertIn("verify_install.py", sh_script.read_text(encoding="utf-8"))
        self.assertIn("verify_install.py", ps1_script.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
