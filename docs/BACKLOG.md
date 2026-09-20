# Continuous Improvement Backlog (docs/BACKLOG.md)

Ranked by expected impact on Hackathon Judging Criteria:
- Investigation Accuracy: 25%
- Next-Best-Action Quality: 25%
- Agentic Design & Engineering: 15%
- Innovation: 15%
- Case Summary & Explainability: 10%
- Demo Quality: 10%

---

## High Priority (Iterations 1–25)

1. **[DONE - Iteration 001] [Investigation Accuracy] Expand Account Takeover (ATO) & Out-of-Region Graph Signals**
   - *Result:* Backtest recall reached **100.00%** (251/251) and F1 **100.00%** with 0 false positives. Trigger resolution from analyst notes and `geo_impossible` integration proved highly effective.

2. **[DONE - Iteration 002] [Next-Best-Action] Implement Full Evidence Response Matrix (No-Response, Step-Up Fail)**
   - *Result:* Implemented complete scenario matrix in `decide.py` for `no_response` (R4), `step_up_fail` (R5), `recurring_confirmed` (R7), and `recognizes` (R3). Added 3 unit tests, expanding test suite to 17 tests (100% pass).

3. **[DONE - Iteration 003] [Innovation] Graph-Native Counterfactual Explainer**
   - *Result:* Implemented `CounterfactualExplainer` calculating decision inversion boundaries across topological factors (device history, region alignment, OTP challenges). Added 2 unit tests, expanding test suite to 19 tests (100% pass).

4. **[DONE - Iteration 004] [Innovation] Evidence Value-of-Information (VOI) Ranking**
   - *Result:* Implemented `ValueOfInformationEngine` utilizing Shannon entropy reduction per unit cost to mathematically optimize inquiry selection. Added 2 unit tests, expanding test suite to 21 tests (100% pass).

5. **[DONE - Iteration 005] [UI/UX] 1-Click Interactive Preset Scenarios in Web Dashboard**
   - *Result:* Implemented 1-click interactive demo scenarios bar in `ui/index.html`, `ui/app.js`, and `ui/style.css` covering key personas (Syndicate HHG-004, Ambiguity Evolution HHG-001, Card Testing HHG-011, Recurring Dispute HHG-007).

---

## Next Priority (Iterations 6–10 Checkpoint to v0.1)

6. **[DONE - Iteration 006] [Testing & Engineering] Benchmark Run-to-Run Self-Consistency Harness**
   - *Result:* Built `eval/benchmark_consistency.py` and `tests/test_consistency.py`. Verified 0.00% recommendation variance, 100% verdict concordance, and 100% SAR filing concordance across 3 repeated runs of all 20 benchmark cases. Suite expanded to 22 tests (100% pass).

7. **[DONE - Iteration 007] [GraphRAG] Enhanced Topological Expansion in Context Brief**
   - *Result:* Upgraded `ContextAssembler.assemble_brief` with structured graph topology metrics (cluster scope, device nexus blast radius, velocity burst spike ratio, cycle detection, temporal boundaries). Integrated into `FraudInvestigatorAgent.investigate_case`. Added test in `tests/test_phase3.py` (23 tests, 100% pass).

8. **[DONE - Iteration 008] [Case Management] Structured 5-Part FinCEN SAR Narrative Generator**
   - *Result:* Built `src/cases/sar_generator.py` generating standard 5-part BSA/FinCEN regulatory narratives (Subject, Exposure Summary, Chronology, Findings & Policies, Disposition). Added 2 unit tests in `tests/test_sar_generator.py` (25 tests, 100% pass).

9. **[DONE - Iteration 009] [UI/UX] Cytoscape Custom Node Glyphs & Interactive Subgraph Expansion**
   - *Result:* Configured 6 distinct geometric vertex glyphs, interactive 1-hop neighborhood tap highlighting with background fade, multi-algorithm layout switchers, and real-time topology HUD inspector.

10. **[DONE - Iteration 010] [Release Tag v0.1] Submission-Ready Checkpoint at Iteration 10**
    - *Result:* Comprehensive PRD Section 25 audit completed. All 6 mandatory gates passed (25/25 unit tests, 100% backtest recall/precision, 0.00% variance across 3 runs, 20/20 valid benchmark answers, 0 secrets, demo path green). Tagged and pushed `v0.1`.

---

## Phase 2: Deep Specialization & Advanced Intelligence (Iterations 11–25)

11. **[DONE - Iteration 011] [Undocumented Pattern Discovery] Graph Anomaly Detection & Syndicate Nexus**
    - *Result:* Built `src/graph/algorithms.py` detecting multi-card proxy rotation, device pooling nexus, coordinated bursts, and rapid geo-dispersion. Integrated into `UncertaintyAssessmentEngine` and `FraudInvestigatorAgent`. Added 2 unit tests in `tests/test_undocumented_patterns.py` (27 tests, 100% pass).

12. **[DONE - Iteration 012] [Security & Safety] Prompt Injection Defenses & Adversarial Input Sanitization**
    - *Result:* Built `src/agent/security.py` detecting and defanging direct instruction overrides, jailbreak phrases, delimiter injections, and zero-width control characters. Integrated into `FraudInvestigatorAgent`. Added 4 unit tests in `tests/test_security.py` (31 tests, 100% pass).

13. **[DONE - Iteration 013] [Case Memory] Dynamic Prior-Based Bayesian Adjustment Loop**
    - *Result:* Built `src/cases/memory.py` implementing `BayesianCaseMemoryPrior` with Beta-Binomial smoothing ($\alpha=1.0, \beta=10.0$), strict temporal isolation (`opened_at < as_of`), device-level compromise detection, and calibrated risk scaling. Integrated into `UncertaintyAssessmentEngine` and `FraudInvestigatorAgent`. Added 5 unit tests in `tests/test_case_memory.py` (36 tests, 100% pass).

14. **[DONE - Iteration 014] [Policy & Permissions] Automated Permission Bypass Penetration Tests**
    - *Result:* Hardened `PolicyEngine` with input exposure sanitization, zero-evidence action gates, and Rule R8 premature closure barriers. Added 7 penetration tests in `tests/test_policy_pen_test.py` verifying 0 unauthorized action leaks under adversarial fuzzing (43 tests, 100% pass).

15. **[Performance & Scale] Transaction Indexing Optimization & Sub-5ms Client Caching**
    - *Goal:* Accelerate GraphStore multi-hop expansions by pre-indexing customer-card-device adjacency matrices.
    - *Files:* `src/graph/client.py`
    - *Metric Impact:* Average latency per case.

---

## Polish & Submission Readiness (Iterations 61–100)

11. **[Documentation] Architecture Diagrams & End-to-End Visual Flow in Docs**
12. **[Reproducibility] Clean Clone Automated Sanity Script**
13. **[Social & Demo] Final Demo Video Walkthrough Assets & Social Copy**
14. **[Code Quality] Strict Type Annotations & Dead Code Audit**
