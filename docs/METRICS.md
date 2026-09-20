# Continuous Improvement Scoreboard (docs/METRICS.md)

| Iteration | Commit | Backtest Precision | Backtest Recall | Backtest F1 | Backtest FPR | Valid Benchmark (20/20) | Evidence Citation Pass | Policy Violations | Test Count (Pass Rate) | Avg Latency | Demo Path | Notes / Key Focus |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **0** | `2401641` | 100.0% | 49.4% | 66.1% | 0.0% | 20/20 (100%) | 100.0% | 0 | 14/14 (100%) | 0.019s | PASS | Baseline audit and scaffolding |
| **001** | `984040d` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 14/14 (100%) | 0.063s | PASS | Expanded ATO, out-of-region, and trigger resolution |
| **002** | `7306d42` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 17/17 (100%) | 0.063s | PASS | Complete evidence response matrix (R4, R5, R7) |
| **003** | `pending` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 19/19 (100%) | 0.063s | PASS | Graph-native counterfactual decision explainer |

---

### Detailed Baseline Metrics (Iteration 0)
- **Historical Closed Cases Backtest (N=300 stratified):**
  - Precision: 100.00%
  - Recall (Detection Rate): 49.40%
  - F1-Score: 66.13%
  - False Positive Rate (FPR): 0.00%
  - Auto-Route Rate: 71.12%
  - Average Case Turnaround: 19.4 ms (vs historical 3.09 days)
- **Benchmark Evaluation (`HHG-001` - `HHG-020`):**
  - Schema Validation Pass: 20/20 (100%)
  - Evidence Finding Citation Validity: 100%
  - Unauthorized Actions: 0
- **Test Suite:**
  - `tests/test_phase1.py`: 6/6 passed
  - `tests/test_phase3.py`: 3/3 passed
  - `tests/test_phase4.py`: 3/3 passed
  - `tests/test_phase5.py`: 2/2 passed
  - Total: 14/14 tests passing (100%)
