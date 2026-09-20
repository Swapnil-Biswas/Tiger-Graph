#!/usr/bin/env bash
# ==============================================================================
# TigerGraph Agentic Fraud Investigator - Full Verification Runner (Bash)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=================================================================="
echo "  TigerGraph Agentic Fraud Investigator: Full Pipeline Runner     "
echo "=================================================================="

# 1. Environment and Clean Clone Sanity Check
echo -e "\n--> Running Sanity & Verification Check..."
python3 scripts/verify_install.py

# 2. Schema Validation
echo -e "\n--> Running Benchmark Schema Validator (eval/validate_answers.py)..."
python3 eval/validate_answers.py cases/

# 3. Unit Test Suite
echo -e "\n--> Running Unit Tests..."
python3 -m unittest discover -s tests -p "test_*.py"

# 4. Optional: Start FastAPI server if --serve is specified
if [[ "$1" == "--serve" ]]; then
    echo -e "\n--> Launching FastAPI Server on http://0.0.0.0:8000..."
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
fi

echo -e "\n--> All stages executed successfully!"
