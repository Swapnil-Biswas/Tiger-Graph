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

7. **[GraphRAG] Enhanced Topological Expansion in Context Brief**
   - *Goal:* Incorporate 2-hop community subgraph statistics and PageRank centrality into the assembled LLM brief.
   - *Files:* `src/rag/assemble.py`, `src/rag/retrieve.py`
   - *Metric Impact:* GraphRAG quality & retrieval relevance.

8. **[Case Management] Enhanced FinCEN SAR Narrative Generator with Structured Sections**
   - *Goal:* Structure SAR narratives with formal regulatory sections: Subject Demographics, Suspicious Activity Timeline, Topology Matrix, Regulatory Impact.
   - *Files:* `src/cases/manager.py`, `src/agent/graph.py`
   - *Metric Impact:* Explainability & Case Management score.

9. **[UI/UX] Cytoscape Custom Node Glyphs & Interactive Subgraph Expansion**
   - *Goal:* Add distinct SVG icon glyphs for Card, Customer, Device, Transaction, and Case vertices with on-click node expansion.
   - *Files:* `ui/app.js`, `ui/style.css`
   - *Metric Impact:* Demo Quality (10%).

10. **[Release Tag v0.1] Submission-Ready Checkpoint at Iteration 10**

6. **[Testing] Benchmark Run-to-Run Self-Consistency Harness**
   - *Goal:* Verify 0% recommendation variance across repeated runs of all 20 benchmark cases.
   - *Files:* `eval/benchmark_consistency.py`
   - *Metric Impact:* Engineering robustness.

7. **[GraphRAG] Enhanced Topological Expansion in Context Brief**
   - *Goal:* Incorporate 2-hop community subgraph statistics and PageRank centrality into the assembled LLM brief.
   - *Files:* `src/rag/assemble.py`, `src/rag/retrieve.py`
   - *Metric Impact:* GraphRAG quality & retrieval relevance.

8. **[Case Management] Enhanced FinCEN SAR Narrative Generator**
   - *Goal:* Structure SAR narratives with formal regulatory sections: Subject Demographics, Suspicious Activity Timeline, Topology Matrix, Regulatory Impact.
   - *Files:* `src/cases/manager.py`, `src/agent/graph.py`
   - *Metric Impact:* Explainability & Case Management score.

9. **[UI/UX] Cytoscape Custom Node Glyphs & Interactive Subgraph Expansion**
   - *Goal:* Add distinct SVG icon glyphs for Card, Customer, Device, Transaction, and Case vertices with on-click node expansion.
   - *Files:* `ui/app.js`, `ui/style.css`
   - *Metric Impact:* Demo Quality (10%).

10. **[Performance] GSQL Analytical Query Caching & Batch Ingestion**
    - *Goal:* Sub-10ms latency for batch case runs.
    - *Files:* `src/graph/client.py`, `src/graph/ingest.py`
    - *Metric Impact:* Performance and scale.

---

## Polish & Submission Readiness (Iterations 61–100)

11. **[Documentation] Architecture Diagrams & End-to-End Visual Flow in Docs**
12. **[Reproducibility] Clean Clone Automated Sanity Script**
13. **[Social & Demo] Final Demo Video Walkthrough Assets & Social Copy**
14. **[Code Quality] Strict Type Annotations & Dead Code Audit**
