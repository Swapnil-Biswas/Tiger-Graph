"""
Unit tests for README.md integrity, file references, and architectural showcase
"""

import sys
import re
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


class TestReadmeIntegrity(unittest.TestCase):
    def setUp(self):
        self.readme_path = ROOT_DIR / "README.md"
        self.assertTrue(self.readme_path.is_file())
        self.content = self.readme_path.read_text(encoding="utf-8")

    def test_badges_present(self):
        self.assertIn("badge/release-v1.0", self.content)
        self.assertIn("badge/tests-409", self.content)
        self.assertIn("badge/python", self.content)
        self.assertIn("badge/TigerGraph", self.content)

    def test_quickstart_section(self):
        self.assertIn("Quickstart in 30 Seconds", self.content)
        self.assertIn("scripts/verify_install.py", self.content)
        self.assertIn("scripts/run_all.sh", self.content)
        self.assertIn("run_all.ps1", self.content)

    def test_cli_section(self):
        self.assertIn("python src/cli/investigate_cli.py --list", self.content)
        self.assertIn("python src/cli/investigate_cli.py --case HHG-001", self.content)
        self.assertIn("python src/cli/investigate_cli.py --benchmark", self.content)

    def test_query_catalog_table(self):
        self.assertIn("Graph Query Library Catalog (Q1 - Q26)", self.content)
        for q in range(1, 27):
            self.assertIn(f"**Q{q}**", self.content)

    def test_referenced_files_exist(self):
        # Extract relative markdown links like [text](path)
        pattern = r"\[.*?\]\((?!http)(.*?)\)"
        matches = re.findall(pattern, self.content)
        self.assertGreater(len(matches), 5)

        for rel_link in matches:
            clean_link = rel_link.split("#")[0].strip()
            if not clean_link:
                continue
            target_path = ROOT_DIR / clean_link
            self.assertTrue(
                target_path.exists(),
                f"Referenced link in README.md does not exist: {clean_link}"
            )


if __name__ == "__main__":
    unittest.main()
