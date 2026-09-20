#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Code Quality & Type Integrity Auditor
=============================================================================
Performs static AST analysis over the codebase to enforce strict type annotations,
docstring coverage, clean import practices, and zero-defect coding standards.

Usage:
    python eval/code_quality_auditor.py [src/] [--strict] [--json]
"""

import sys
import os
import ast
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class FileQualityMetrics:
    file_path: str
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    annotated_functions: int = 0
    return_annotated_functions: int = 0
    classes_with_docstring: int = 0
    functions_with_docstring: int = 0
    naked_except_count: int = 0
    wildcard_import_count: int = 0
    issues: List[str] = field(default_factory=list)

    @property
    def type_coverage(self) -> float:
        if self.total_functions == 0:
            return 100.0
        return round((self.annotated_functions / self.total_functions) * 100.0, 2)

    @property
    def docstring_coverage(self) -> float:
        total_items = self.total_classes + self.total_functions
        if total_items == 0:
            return 100.0
        documented = self.classes_with_docstring + self.functions_with_docstring
        return round((documented / total_items) * 100.0, 2)


@dataclass
class CodeQualityAuditReport:
    target_dir: str
    total_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    annotated_functions: int = 0
    overall_type_coverage: float = 0.0
    overall_docstring_coverage: float = 0.0
    naked_except_count: int = 0
    wildcard_import_count: int = 0
    overall_quality_score: float = 1.0
    file_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class CodeQualityAuditor:
    """Static AST analyzer for type annotations and code health."""

    def __init__(self, min_type_coverage: float = 70.0, strict: bool = False):
        self.min_type_coverage = min_type_coverage
        self.strict = strict

    def audit_file(self, file_path: Path) -> FileQualityMetrics:
        """Analyze a single Python file using AST traversal."""
        metrics = FileQualityMetrics(file_path=str(file_path))

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            metrics.issues.append(f"Failed to read file: {e}")
            return metrics

        metrics.total_lines = len(content.splitlines())

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            metrics.issues.append(f"SyntaxError on line {e.lineno}: {e.msg}")
            return metrics

        for node in ast.walk(tree):
            # Check for ClassDef
            if isinstance(node, ast.ClassDef):
                metrics.total_classes += 1
                if ast.get_docstring(node):
                    metrics.classes_with_docstring += 1

            # Check for FunctionDef and AsyncFunctionDef
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics.total_functions += 1

                if ast.get_docstring(node):
                    metrics.functions_with_docstring += 1

                # Check parameter type annotations
                args = node.args
                all_params = args.args + args.kwonlyargs
                # exclude 'self' or 'cls' for instance/class methods
                non_self_params = [
                    p for p in all_params
                    if p.arg not in ("self", "cls")
                ]

                has_return_anno = node.returns is not None
                if has_return_anno:
                    metrics.return_annotated_functions += 1

                annotated_params = [p for p in non_self_params if p.annotation is not None]

                # Function is considered annotated if:
                # - It has no params and has a return annotation, OR
                # - At least 50% of non-self params have annotations, OR
                # - It has a return annotation
                if len(non_self_params) == 0:
                    if has_return_anno or node.name.startswith("__"):
                        metrics.annotated_functions += 1
                else:
                    if len(annotated_params) >= (len(non_self_params) / 2) or has_return_anno:
                        metrics.annotated_functions += 1

            # Check for naked except: (except without type)
            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    metrics.naked_except_count += 1
                    metrics.issues.append(f"Naked except at line {node.lineno}")

            # Check for wildcard imports (from x import *)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        metrics.wildcard_import_count += 1
                        metrics.issues.append(f"Wildcard import at line {node.lineno}: from {node.module} import *")

        return metrics

    def audit_directory(self, dir_path: Path) -> CodeQualityAuditReport:
        """Scan all Python files under target directory recursively."""
        report = CodeQualityAuditReport(target_dir=str(dir_path))
        py_files = sorted(dir_path.glob("**/*.py"))

        total_annotated = 0
        total_functions = 0
        total_items_doc = 0
        total_items_all = 0

        for py_file in py_files:
            # Skip hidden files or __pycache__
            if "__pycache__" in py_file.parts or any(p.startswith(".") for p in py_file.parts):
                continue

            file_metrics = self.audit_file(py_file)
            report.total_files += 1
            report.total_lines += file_metrics.total_lines
            report.total_classes += file_metrics.total_classes
            report.total_functions += file_metrics.total_functions
            report.annotated_functions += file_metrics.annotated_functions
            report.naked_except_count += file_metrics.naked_except_count
            report.wildcard_import_count += file_metrics.wildcard_import_count

            total_annotated += file_metrics.annotated_functions
            total_functions += file_metrics.total_functions
            total_items_doc += (file_metrics.classes_with_docstring + file_metrics.functions_with_docstring)
            total_items_all += (file_metrics.total_classes + file_metrics.total_functions)

            rel_path = str(py_file.relative_to(dir_path.parent if dir_path.parent != py_file else dir_path))
            report.file_metrics[rel_path] = asdict(file_metrics)

        if total_functions > 0:
            report.overall_type_coverage = round((total_annotated / total_functions) * 100.0, 2)
        else:
            report.overall_type_coverage = 100.0

        if total_items_all > 0:
            report.overall_docstring_coverage = round((total_items_doc / total_items_all) * 100.0, 2)
        else:
            report.overall_docstring_coverage = 100.0

        # Calculate composite quality score [0.0, 1.0]
        type_comp = min(1.0, report.overall_type_coverage / 100.0)
        doc_comp = min(1.0, report.overall_docstring_coverage / 100.0)
        penalties = (report.naked_except_count * 0.05) + (report.wildcard_import_count * 0.05)
        raw_score = (0.60 * type_comp) + (0.40 * doc_comp) - penalties
        report.overall_quality_score = max(0.0, min(1.0, round(raw_score, 4)))

        # Determine pass/fail
        type_pass = report.overall_type_coverage >= self.min_type_coverage
        hygiene_pass = (report.naked_except_count == 0) and (report.wildcard_import_count == 0)
        report.passed = type_pass and hygiene_pass if self.strict else type_pass

        return report


def print_audit_report(report: CodeQualityAuditReport) -> None:
    """Render human-readable terminal report."""
    print("\n" + "=" * 70)
    print("  TIGERGRAPH AGENTIC FRAUD INVESTIGATOR - CODE QUALITY AUDIT")
    print("=" * 70)
    print(f"Target Directory         : {report.target_dir}")
    print(f"Total Python Files       : {report.total_files}")
    print(f"Total Lines of Code      : {report.total_lines:,}")
    print(f"Total Classes / Functions: {report.total_classes} / {report.total_functions}")
    print(f"Type Annotation Coverage : {report.overall_type_coverage}% ({report.annotated_functions}/{report.total_functions})")
    print(f"Docstring Coverage       : {report.overall_docstring_coverage}%")
    print(f"Naked Excepts Detected   : {report.naked_except_count}")
    print(f"Wildcard Imports Found   : {report.wildcard_import_count}")
    print(f"Overall Quality Score    : {report.overall_quality_score:.4f} / 1.0000")
    print("-" * 70)
    status_str = "PASS" if report.passed else "FAIL"
    print(f"AUDIT STATUS             : [{status_str}]")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Audit codebase type annotations and quality")
    parser.add_argument("directory", nargs="?", default="src", help="Target directory to audit (default: src)")
    parser.add_argument("--min-coverage", type=float, default=70.0, help="Minimum type coverage %% (default: 70.0)")
    parser.add_argument("--strict", action="store_true", help="Fail if any naked excepts or wildcard imports")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    target_dir = Path(args.directory).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    auditor = CodeQualityAuditor(min_type_coverage=args.min_coverage, strict=args.strict)
    report = auditor.audit_directory(target_dir)

    if args.json:
        print(report.to_json())
    else:
        print_audit_report(report)

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
