#!/usr/bin/env python3
"""
TigerGraph Agentic Fraud Investigator - Clean Clone Sanity & Verification Script
================================================================================
Validates environment, dependencies, project structure, benchmark answers,
and demo verification gates for fresh clones and CI/CD pipelines.

Usage:
    python scripts/verify_install.py [--quick] [--json] [--skip-demo]
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Terminal color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_python_version(min_major: int = 3, min_minor: int = 10) -> Tuple[bool, str]:
    """Check if Python version meets minimum requirement."""
    version = sys.version_info
    passed = (version.major, version.minor) >= (min_major, min_minor)
    msg = f"Python {version.major}.{version.minor}.{version.micro} (Required >= {min_major}.{min_minor})"
    return passed, msg


def check_dependencies(requirements_file: Path) -> Tuple[bool, Dict[str, bool]]:
    """Check if required packages are importable."""
    packages = {
        "pydantic": "pydantic",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pyyaml": "yaml",
        "requests": "requests",
        "networkx": "networkx",
        "numpy": "numpy",
        "pandas": "pandas",
    }
    results = {}
    all_passed = True
    for pkg_name, import_name in packages.items():
        try:
            __import__(import_name)
            results[pkg_name] = True
        except ImportError:
            results[pkg_name] = False
            all_passed = False
    return all_passed, results


def check_project_structure(root_dir: Path) -> Tuple[bool, List[str]]:
    """Verify required directories and key files exist."""
    required_dirs = ["src", "eval", "cases", "tests", "ui", "deploy", "docs"]
    required_files = [
        "requirements.txt",
        "PRD_TigerGraph_Agentic_Fraud_Investigator.md",
        "eval/validate_answers.py",
        "tests/test_phase4.py",
        "docs/ARCHITECTURE.md",
        "docs/METRICS.md",
    ]
    missing = []
    for d in required_dirs:
        if not (root_dir / d).is_dir():
            missing.append(f"Directory: {d}/")
    for f in required_files:
        if not (root_dir / f).is_file():
            missing.append(f"File: {f}")
    return len(missing) == 0, missing


def check_benchmark_cases(root_dir: Path) -> Tuple[bool, int, int]:
    """Run eval/validate_answers.py against cases/."""
    cases_dir = root_dir / "cases"
    validator_script = root_dir / "eval" / "validate_answers.py"
    if not validator_script.is_file() or not cases_dir.is_dir():
        return False, 0, 20

    cmd = [sys.executable, str(validator_script), str(cases_dir)]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        passed = proc.returncode == 0 and "20/20 Passed" in proc.stdout
        # count case files
        case_files = list(cases_dir.glob("HHG-*.json"))
        return passed, len(case_files), 20
    except Exception:
        return False, 0, 20


def check_demo_path(root_dir: Path) -> Tuple[bool, str]:
    """Run Phase 4 demo path (tests/test_phase4.py)."""
    phase4_test = root_dir / "tests" / "test_phase4.py"
    if not phase4_test.is_file():
        return False, "test_phase4.py not found"

    cmd = [sys.executable, "-m", "unittest", str(phase4_test)]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, cwd=str(root_dir))
        output = proc.stdout + proc.stderr
        passed = proc.returncode == 0 and "OK" in output
        return passed, "Phase 4 demo path passed" if passed else output.strip()
    except Exception as e:
        return False, str(e)


def run_sanity_checks(root_dir: Path, quick: bool = False, skip_demo: bool = False) -> Dict[str, Any]:
    """Execute all sanity checks and return structured results."""
    py_ok, py_msg = check_python_version()
    req_file = root_dir / "requirements.txt"
    deps_ok, deps_detail = check_dependencies(req_file)
    struct_ok, struct_missing = check_project_structure(root_dir)
    cases_ok, cases_found, cases_expected = check_benchmark_cases(root_dir)

    demo_ok = True
    demo_msg = "Skipped"
    if not quick and not skip_demo:
        demo_ok, demo_msg = check_demo_path(root_dir)

    all_passed = py_ok and deps_ok and struct_ok and cases_ok and demo_ok

    return {
        "status": "PASS" if all_passed else "FAIL",
        "python": {"passed": py_ok, "detail": py_msg},
        "dependencies": {"passed": deps_ok, "detail": deps_detail},
        "structure": {"passed": struct_ok, "missing": struct_missing},
        "benchmark_cases": {"passed": cases_ok, "found": cases_found, "expected": cases_expected},
        "demo_path": {"passed": demo_ok, "detail": demo_msg},
    }


def print_report(results: Dict[str, Any]) -> None:
    """Print ANSI formatted report to stdout."""
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  TIGERGRAPH AGENTIC FRAUD INVESTIGATOR - SANITY AUDIT{RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")

    def status_badge(passed: bool) -> str:
        return f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"

    # 1. Python
    print(f"{status_badge(results['python']['passed'])} Python Version: {results['python']['detail']}")

    # 2. Dependencies
    deps = results["dependencies"]
    print(f"{status_badge(deps['passed'])} Core Dependencies:")
    for pkg, ok in deps["detail"].items():
        mark = f"{GREEN}[OK]{RESET}" if ok else f"{RED}[FAIL]{RESET}"
        print(f"       {mark} {pkg}")

    # 3. Structure
    struct = results["structure"]
    if struct["passed"]:
        print(f"{status_badge(True)} Project Structure: All required files and directories present")
    else:
        print(f"{status_badge(False)} Project Structure: Missing: {', '.join(struct['missing'])}")

    # 4. Benchmark Cases
    cases = results["benchmark_cases"]
    print(f"{status_badge(cases['passed'])} Benchmark Cases: {cases['found']}/{cases['expected']} verified valid")

    # 5. Demo Path
    demo = results["demo_path"]
    print(f"{status_badge(demo['passed'])} Phase 4 Demo Gate: {demo['detail']}")

    print(f"\n{BOLD}{CYAN}{'-'*65}{RESET}")
    if results["status"] == "PASS":
        print(f"{BOLD}{GREEN}  OVERALL STATUS: ALL CHECKS PASSED (Clean Clone Ready){RESET}")
    else:
        print(f"{BOLD}{RED}  OVERALL STATUS: ONE OR MORE CHECKS FAILED{RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Verify TigerGraph Agentic Fraud Investigator installation")
    parser.add_argument("--quick", action="store_true", help="Run quick checks only (skip demo execution)")
    parser.add_argument("--skip-demo", action="store_true", help="Skip Phase 4 demo path verification")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    # Determine root directory (parent of scripts/)
    script_path = Path(__file__).resolve()
    root_dir = script_path.parent.parent

    results = run_sanity_checks(root_dir, quick=args.quick, skip_demo=args.skip_demo)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
