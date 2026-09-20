# Verification & Open Questions Resolution (Phase 0)

All items marked **[VERIFY]** in `PRD_TigerGraph_Agentic_Fraud_Investigator.md` are resolved here using the active dataset and `README_dataset.md`.

---

## 1. Resolved [VERIFY] Items

### 1.1 Dataset Filenames & Join Keys
- **Question:** What are the exact filenames, column names, and join keys?
- **Resolved:**
  - `data/transactions.csv` (590,742 rows): Primary key `TransactionID`. Key columns: `customer_id`, `ts`, `channel`, `risk_score`, `ProductCD`, `TransactionAmt`, `addr1`, `addr2`, `card1`..`card6`, `P_emaildomain`, `R_emaildomain`.
  - `data/identity.csv` (144,432 rows): Joined to `transactions.csv` on `TransactionID` for online transactions (`ProductCD != 'W'`). Columns include `DeviceInfo`, `DeviceType`, `id_15` (New/Found), `id_23` (proxy), `id_30` (OS), `id_31` (browser), `id_33` (screen).
  - `data/closed_cases_history.csv` (5,565 rows): Historical labeled cases with `customer_id`, `card_id`, `opened_at`, `closed_at`, `outcome` (`confirmed_fraud` / `cleared`), `pattern`, `first_fraud_txn_id`, `txn_ids`, `exposure_usd`, `connected_card_ids`, `actions_taken`, `report_filed`, `analyst_notes`.
  - `data/case_pack.csv` (20 rows): Benchmark cases `HHG-001` to `HHG-020` with `trigger_type`, `trigger_text`, `flagged_txn_id`, `card_id`, `customer_id`, `risk_score`.

### 1.2 Customer and Card Entity Resolution
- **Question:** How are customers and cards keyed?
- **Resolved:**
  - `customer_id`: Already present in `transactions.csv` and `closed_cases_history.csv` (e.g. `C00259`, `C12382`).
  - `card_id`: Formatted as `<customer_id>-K<N>` (e.g. `C00259-K1`, `C08623-K2`). Directly provided in `closed_cases_history.csv` and `case_pack.csv`. In `transactions.csv`, transactions are mapped to card vertices based on customer and issuer `(card1, card2, card3, card4, card5, card6)` signatures.

### 1.3 Answer Format & Output Adapters
- **Question:** What is the exact submission format required?
- **Resolved:** 20 JSON files named `<case_id>.json` placed in `cases/` matching the README schema (`case`, `evidence_requests`, `next_best_actions` with `initial` and `final`, `sar`, `stop_reason`, `tool_calls`, `tokens`, `latency_s`).

### 1.4 Policy Thresholds & SAR Criteria
- **Question:** What are the exact thresholds and approval routes?
- **Resolved:**
  - Fraud probability: R1 triggers verify if single signal and probability < 0.70; CREATE_CASE triggered if probability >= 0.30; stopping criteria at probability >= 0.85 or <= 0.15.
  - Exposure thresholds: L1 approval for `BLOCK_CARD` <= $2,500; L2 approval for `BLOCK_CARD` > $2,500; SAR (`FILE_REPORT`) always L2 and required if confirmed fraud and (exposure > $1,000 or shared device profile or R9 undocumented pattern).
  - `BLOCK_ALL_CARDS` requires >= 2 confirmed fraud cards or confirmed compromised credentials (R10) and is always L2.

### 1.5 Five Known Fraud Patterns
- **Resolved:**
  1. `card_testing`: >= 3 tiny online authorizations (often < $5) in 1 hour followed by larger purchase.
  2. `card_not_present_fraud`: Online purchases inconsistent with history, burst of 2-4 in 48h.
  3. `card_not_present_new_device`: CNP with identity record `id_15 == 'New'`, proxy usage.
  4. `out_of_region_use`: In-person purchases in unfamiliar billing region while home region activity continues.
  5. `account_takeover`: Mixed-channel anomalies, credential takeover indicators.
  6. `undocumented`: Multi-customer coordination not fitting the above.
  7. `none`: Cleared / false alarm cases.

### 1.6 TigerGraph Setup & Fallback
- **Question:** TigerGraph Savanna vs Community Edition vs local graph engine.
- **Resolved:**
  - We can connect to TigerGraph cloud Savanna or TigerGraph Community Edition if credentials/instance are supplied.
  - Furthermore, to ensure 100% uninterrupted local execution, testing, demoing, and backtesting without network timeouts or external server crashes, we will build a dual-mode graph client:
    - Mode A: Live TigerGraph REST/GSQL & MCP connection (using `pyTigerGraph` and TigerGraph MCP).
    - Mode B: High-performance local NetworkX / SQLite in-memory graph engine implementing the exact same GSQL query interfaces (Q1-Q12) with identical signatures and return types.
    This guarantees zero downtime and enables instantaneous automated testing and verification across all benchmark cases!
