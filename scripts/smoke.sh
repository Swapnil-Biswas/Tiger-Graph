#!/usr/bin/env bash
# TigerGraph Agentic Fraud Investigator - Fast Smoke Test (Linux / macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Running TigerGraph Fraud Investigator Smoke Test ==="
python3 "$SCRIPT_DIR/smoke_test.py" "$@"
