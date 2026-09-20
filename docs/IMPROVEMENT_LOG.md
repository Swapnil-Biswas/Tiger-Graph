# Continuous Improvement Log (docs/IMPROVEMENT_LOG.md)

---

## Iteration 000: Setup, Baseline Audit, and Improvement Scaffolding | 2026-09-20 16:32 | commit 2401641
- **Lens:** Setup & Baseline Audit (All Lenses)
- **Goal / hypothesis:** Establish the baseline continuous improvement infrastructure, state tracking files, and scoreboard across all evaluation metrics.
- **Changes (files):**
  - `docs/PRD.md`: Mirror PRD to docs/PRD.md
  - `.gitignore`: Added `.pem`, `.key`, `data/raw/`, `node_modules/`, `.venv/` security rules
  - `docs/DECISIONS.md`: Initialized architectural decision records
  - `docs/METRICS.md`: Initialized continuous improvement scoreboard with baseline run
  - `docs/BACKLOG.md`: Initialized prioritized backlog mapped to hackathon judging criteria
  - `docs/IMPROVEMENT_LOG.md`: Initialized continuous log
- **Tests added/updated:** All existing test suites verified:
  - `tests/test_phase1.py` (6/6 pass)
  - `tests/test_phase3.py` (3/3 pass)
  - `tests/test_phase4.py` (3/3 pass)
  - `tests/test_phase5.py` (2/2 pass)
  - Total: 14/14 tests passing
- **Metrics before -> after:**
  - Backtest Recall: 49.4%
  - Backtest Precision: 100.0%
  - Backtest F1: 66.1%
  - Benchmark Answers Valid: 20/20 (100%)
  - Evidence Finding Citation Validity: 100%
  - Policy Violations: 0
  - Demo Path: PASS
- **Verification gates:**
  - Unit tests: PASS (14/14)
  - Demo path: PASS
  - Answer-file validation (`eval/validate_answers.py`): PASS (20/20)
  - Backtest (`eval/backtest.py`): PASS (N=300, 19.4ms avg latency)
  - Secret scan: PASS (No secrets staged)
- **What I learned / what surprised me:** The baseline graph engine operates with 100% precision and 0 false positives, but recall on historical closed cases is 49.4% due to subtle account takeover and out-of-region signals not yet fully factored into the primary assessment rules. Expanding these signals will yield major accuracy gains.
- **Follow-ups added to backlog:** Items 1-5 prioritized for high-impact accuracy and next-best-action gains.
