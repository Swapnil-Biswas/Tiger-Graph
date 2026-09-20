# Continuous Improvement Scoreboard (docs/METRICS.md)

| Iteration | Commit | Backtest Precision | Backtest Recall | Backtest F1 | Backtest FPR | Valid Benchmark (20/20) | Evidence Citation Pass | Policy Violations | Test Count (Pass Rate) | Avg Latency | Demo Path | Notes / Key Focus |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **0** | `2401641` | 100.0% | 49.4% | 66.1% | 0.0% | 20/20 (100%) | 100.0% | 0 | 14/14 (100%) | 0.019s | PASS | Baseline audit and scaffolding |
| **001** | `984040d` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 14/14 (100%) | 0.063s | PASS | Expanded ATO, out-of-region, and trigger resolution |
| **002** | `7306d42` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 17/17 (100%) | 0.063s | PASS | Complete evidence response matrix (R4, R5, R7) |
| **003** | `2ca2604` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 19/19 (100%) | 0.063s | PASS | Graph-native counterfactual decision explainer |
| **004** | `13ca7dd` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 21/21 (100%) | 0.063s | PASS | Evidence Value of Information (VOI) entropy ranking |
| **005** | `8577f68` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 21/21 (100%) | 0.063s | PASS | 1-Click Interactive Demo Presets in web UI |
| **006** | `d621ef7` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 22/22 (100%) | 0.063s | PASS | Benchmark 3-run self-consistency (0.00% variance, 100% determinism) |
| **007** | `a3b95f6` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 23/23 (100%) | 0.023s | PASS | Enhanced topological graph context brief in GraphRAG |
| **008** | `1013f37` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 25/25 (100%) | 0.022s | PASS | Structured 5-part FinCEN SAR narrative generator |
| **009** | `30f7f73` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 25/25 (100%) | 0.022s | PASS | Cytoscape visual glyphs, neighborhood highlight, and HUD inspector |
| **010** | `0c4ae80` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 25/25 (100%) | 0.019s | PASS | Checkpoint 2 Audit, State of the Project, and v0.1 Release Tag |
| **011** | `4b20b51` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 27/27 (100%) | 0.021s | PASS | Undocumented pattern discovery & multi-card syndicate anomaly detector |
| **012** | `70e6e24` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 31/31 (100%) | 0.020s | PASS | InputSanitizer prompt-injection shield & adversarial defanging |
| **013** | `edf84e4` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 36/36 (100%) | 0.021s | PASS | Bayesian case memory prior adjustment & temporal isolation |
| **014** | `cf51cbf` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 43/43 (100%) | 0.021s | PASS | PolicyEngine penetration fuzzing & permission bypass defenses |
| **015** | `33d27a5` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 48/48 (100%) | 0.008s | PASS | Graph client bisect temporal slicing & performance benchmark (106x speedup) |
| **016** | `62ec1a4` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 50/50 (100%) | 0.008s | PASS | SyndicateNexus graph persistence & cross-case ring linking |
| **017** | `73242f6` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 54/54 (100%) | 0.008s | PASS | Deterministic audit trail self-critique & citation verifier |
| **018** | `90415ee` | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 55/55 (100%) | 0.008s | PASS | GraphRAG BM25 & n-gram policy retrieval optimization (1.0000 MRR) |
| **019** | pending | 100.0% | 100.0% | 100.0% | 0.0% | 20/20 (100%) | 100.0% | 0 | 59/59 (100%) | 0.050s | PASS | Automated component ablation study harness (Graph, Memory, Policy) |

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
