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

3. **[Innovation] Graph-Native Counterfactual Explainer**
   - *Goal:* Generate deterministic "What would change this verdict?" counterfactuals (e.g., "If the device fingerprint had 3+ prior authentications, verdict would shift from fraud to legitimate").
   - *Files:* `src/agent/explainer_validator.py`, `src/agent/graph.py`
   - *Metric Impact:* Innovation (15%) and Explainability (10%).

4. **[Innovation] Evidence Value-of-Information (VOI) Ranking**
   - *Goal:* Formally calculate expected uncertainty reduction for candidate evidence requests before selecting the optimal inquiry.
   - *Files:* `src/agent/assess.py`, `src/agent/decide.py`
   - *Metric Impact:* Agentic Design (15%) and Next-Best-Action (25%).

5. **[UI/UX] 1-Click Interactive Preset Scenarios in Web Dashboard**
   - *Goal:* Add pre-configured 1-click demo buttons in UI for key personas (`Clear-Cut Syndicate HHG-004`, `Ambiguous Evolution HHG-001`, `Card Testing HHG-011`, `Disputed Recurring HHG-007`).
   - *Files:* `ui/index.html`, `ui/app.js`, `ui/style.css`
   - *Metric Impact:* Demo quality (10%).

---

## Medium Priority (Iterations 26–60)

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
