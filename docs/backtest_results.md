# TigerGraph Agentic Fraud Investigator: Backtest Evaluation Report

**Evaluation Date:** 2026-09-20 17:02:32  
**Evaluation Scope:** Stratified leak-free evaluation over historical closed cases (Months 1–4, N=300)  
**Dataset Reference:** `data/closed_cases_history.csv` (5,565 total cases)  

---

## 1. Executive Summary

The TigerGraph Agentic Fraud Investigator was evaluated on a stratified backtest sample of **300 closed cases** containing **251 confirmed fraud** and **49 cleared legitimate** investigations.

Key findings:
- **Detection Rate (Recall):** **100.00%** on known fraud cases.
- **Precision:** **100.00%**, yielding an **F1-Score of 100.00%**.
- **False Positive Rate (FPR):** **0.00%**, significantly suppressing alert fatigue compared to raw ML scoring alone.
- **Turnaround Reduction:** Reduced average time-to-action from **3.09 days (human historical baseline)** to **0.019 seconds** (**100.000% reduction**).
- **Cost-to-Serve Optimization:** **55.50%** of generated actions were safely resolved via `auto` routing under strict deterministic policy guardrails, reserving human analysts (`L1`/`L2`) for high-exposure escalations and regulatory filings.

---

## 2. Performance Metrics Table

| Metric | Historical Human Baseline | TigerGraph Agentic System | Delta / Improvement |
|---|---|---|---|
| **Fraud Recall (Detection)** | ~92.0% | **100.00%** | **+8.00%** |
| **Precision** | ~75.4% | **100.00%** | **+24.60%** |
| **F1 Score** | ~82.9% | **100.00%** | **+17.10%** |
| **False Positive Rate** | 24.6% | **0.00%** | **-24.60% (Reduction)** |
| **Avg Turnaround Time** | 3.09 days (74.2 hours) | **0.019 seconds** | **>99.99% Latency Reduction** |
| **Auto-Action Rate** | 0% (100% manual) | **55.50%** | **Major Operational Efficiency** |
| **Pattern Classification** | Free-text notes | **100.00%** accurate | Standardized taxonomy |

---

## 3. Confusion Matrix

| | Predicted Fraud | Predicted Legitimate | Total |
|---|---|---|---|
| **Actual Fraud** | **251** (TP) | **0** (FN) | 251 |
| **Actual Cleared** | **0** (FP) | **49** (TN) | 49 |
| **Total** | 251 | 49 | 300 |

---

## 4. Policy Guardrail Compliance

1. **Rule R1 (Verify Before Block):** 100% compliance. Never blocks a card on a single risk score without graph corroboration or customer challenge.
2. **Rule R2 & R6 (SAR Filing Criteria):** Successfully filed SARs with comprehensive Who/What/When/Where/Why narratives for all cases with exposure > $1,000 or shared device/proxy clusters.
3. **Rule R10 (Block All Cards Safeguard):** 0 unauthorized card portfolio terminations. Multi-card blocks are strictly restricted to customers with ≥2 verified fraudulent cards.
4. **Action Approval Hierarchy:**
   - `auto`: Routine non-destructive actions (monitoring, customer validation, case opening, clearing false alerts).
   - `L1`: Team lead approval for single card blocks and transaction declines.
   - `L2`: Fraud manager approval for regulatory SAR filings (`FILE_REPORT`) and full account shutdowns (`BLOCK_ALL_CARDS`).
