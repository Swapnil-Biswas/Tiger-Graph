#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Demo Asset Packager & Integrity Verifier
================================================================================
Packages key presentation artifacts, benchmark cases, architecture docs, and
sample FinCEN SAR XML filings into a self-contained demo bundle with SHA-256 manifest.

Usage:
    python scripts/package_demo_assets.py [--output-dir outputs/demo_bundle] [--verify] [--json]
"""

import sys
import os
import json
import hashlib
import shutil
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DemoAssetPackager:
    """Packages and verifies demo assets for presentations and submissions."""

    def __init__(self, root_dir: Path, output_dir: Path):
        self.root_dir = root_dir.resolve()
        self.output_dir = output_dir.resolve()

    def package_assets(self) -> Dict[str, Any]:
        """Collect and bundle demo files into output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "title": "TigerGraph Agentic Fraud Investigator - Demo Bundle",
            "version": "v0.8",
            "files": {},
            "total_files": 0,
        }

        # Key demo cases to bundle
        demo_cases = ["HHG-001.json", "HHG-006.json", "HHG-010.json"]
        cases_sub = self.output_dir / "cases"
        cases_sub.mkdir(exist_ok=True)

        for case_name in demo_cases:
            src_case = self.root_dir / "cases" / case_name
            if src_case.is_file():
                dest_case = cases_sub / case_name
                shutil.copy2(src_case, dest_case)
                manifest["files"][f"cases/{case_name}"] = {
                    "sha256": compute_sha256(dest_case),
                    "size_bytes": dest_case.stat().st_size,
                }

        # Key documentation
        docs_to_copy = ["DEMO_SCRIPT.md", "ARCHITECTURE.md"]
        docs_sub = self.output_dir / "docs"
        docs_sub.mkdir(exist_ok=True)

        for doc_name in docs_to_copy:
            src_doc = self.root_dir / "docs" / doc_name
            if src_doc.is_file():
                dest_doc = docs_sub / doc_name
                shutil.copy2(src_doc, dest_doc)
                manifest["files"][f"docs/{doc_name}"] = {
                    "sha256": compute_sha256(dest_doc),
                    "size_bytes": dest_doc.stat().st_size,
                }

        # Generate sample FinCEN Form 111 XML filing
        sample_xml = self.output_dir / "sample_sar_filing.xml"
        sample_xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FC2ElectronicFiling xmlns="http://www.fincen.gov/bsa">\n'
            '  <ActivitySeqNum>1</ActivitySeqNum>\n'
            '  <Activity>\n'
            '    <EFilingPriorDocumentNumber>00000000000000</EFilingPriorDocumentNumber>\n'
            '    <ActivityAssociation>\n'
            '      <InitialReportIndicator>Y</InitialReportIndicator>\n'
            '    </ActivityAssociation>\n'
            '    <SuspiciousActivityInformation>\n'
            '      <SuspiciousActivityTypeId>35</SuspiciousActivityTypeId>\n'
            '      <NarrativeText>Autonomous agentic investigation confirmed multi-card syndicate coordinated attack (HHG-010). Total exposure: $1,000.03. Filed per BSA 31 CFR 1020.320.</NarrativeText>\n'
            '    </SuspiciousActivityInformation>\n'
            '  </Activity>\n'
            '</FC2ElectronicFiling>\n'
        )
        sample_xml.write_text(sample_xml_content, encoding="utf-8")
        manifest["files"]["sample_sar_filing.xml"] = {
            "sha256": compute_sha256(sample_xml),
            "size_bytes": sample_xml.stat().st_size,
        }

        # Generate HTML index overview
        index_html = self.output_dir / "index.html"
        index_content = (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "  <meta charset='UTF-8'>\n"
            "  <title>TigerGraph Agentic Fraud Investigator - Demo Hub</title>\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }\n"
            "    .card { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; border: 1px solid #334155; }\n"
            "    h1, h2 { color: #38bdf8; }\n"
            "    a { color: #818cf8; text-decoration: none; }\n"
            "    a:hover { text-decoration: underline; }\n"
            "    code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>TigerGraph Agentic Fraud Investigator - Demo Hub</h1>\n"
            "  <div class='card'>\n"
            "    <h2>Presentation Resources</h2>\n"
            "    <ul>\n"
            "      <li><a href='docs/DEMO_SCRIPT.md'>5-Minute Video Walkthrough Script</a></li>\n"
            "      <li><a href='docs/ARCHITECTURE.md'>System Architecture &amp; Visual Workflows</a></li>\n"
            "      <li><a href='sample_sar_filing.xml'>Sample FinCEN Form 111 XML Filing</a></li>\n"
            "    </ul>\n"
            "  </div>\n"
            "  <div class='card'>\n"
            "    <h2>Key Benchmark Cases</h2>\n"
            "    <ul>\n"
            "      <li><a href='cases/HHG-001.json'>Case HHG-001 (Out of Region Use)</a></li>\n"
            "      <li><a href='cases/HHG-006.json'>Case HHG-006 (Card Not Present New Device)</a></li>\n"
            "      <li><a href='cases/HHG-010.json'>Case HHG-010 (Syndicate Cluster $1,000+ Exposure)</a></li>\n"
            "    </ul>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )
        index_html.write_text(index_content, encoding="utf-8")
        manifest["files"]["index.html"] = {
            "sha256": compute_sha256(index_html),
            "size_bytes": index_html.stat().st_size,
        }

        manifest["total_files"] = len(manifest["files"])

        # Write manifest.json
        manifest_file = self.output_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return manifest

    def verify_bundle(self) -> Tuple[bool, str]:
        """Verify checksums in manifest.json match files on disk."""
        manifest_file = self.output_dir / "manifest.json"
        if not manifest_file.is_file():
            return False, "manifest.json not found"

        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"Failed to parse manifest: {e}"

        files = manifest.get("files", {})
        for rel_path, meta in files.items():
            target_file = self.output_dir / rel_path
            if not target_file.is_file():
                return False, f"Missing file: {rel_path}"
            curr_sha = compute_sha256(target_file)
            if curr_sha != meta.get("sha256"):
                return False, f"Checksum mismatch in {rel_path}"

        return True, f"All {len(files)} files verified against manifest SHA-256"


def main():
    parser = argparse.ArgumentParser(description="Package and verify demo assets")
    parser.add_argument("--output-dir", default="outputs/demo_bundle", help="Target output directory")
    parser.add_argument("--verify", action="store_true", help="Verify existing bundle against manifest")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    out_dir = root_dir / args.output_dir

    packager = DemoAssetPackager(root_dir=root_dir, output_dir=out_dir)

    if args.verify:
        ok, msg = packager.verify_bundle()
        if args.json:
            print(json.dumps({"verified": ok, "message": msg}))
        else:
            print(f"[{'PASS' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)
    else:
        manifest = packager.package_assets()
        ok, msg = packager.verify_bundle()
        if args.json:
            print(json.dumps({"manifest": manifest, "verified": ok, "message": msg}, indent=2))
        else:
            print(f"\nSuccessfully packaged {manifest['total_files']} demo assets into: {out_dir}")
            print(f"Verification: [{ 'PASS' if ok else 'FAIL' }] {msg}\n")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
