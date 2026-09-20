# Bank Fraud Policy Summary & Rules Matrix

**Version:** 1.0 (Bank Fraud Investigation Policy)

---

## 1. Action Catalog

| Action Identifier | Target / Scope | Approval Route | Preconditions / Rules | Customer Impact |
|---|---|---|---|---|
| `ALLOW_TRANSACTION` | Flagged authorization | `auto` | Assessed fraud probability low, or legitimate confirmation | None |
| `DECLINE_TRANSACTION` | Flagged authorization only | `L1` (team lead) | Card testing (R5), or unresolved after 24h (R4) | Low |
| `MONITOR_CARD` | Specific card | `auto` | Elevate monitoring sensitivity for 72 hours | None |
| `MONITOR_CONNECTED_CARDS` | Linked cards / cluster | `auto` | Cards sharing device profile, region cluster, or ring (R6) | None |
| `WARN_CUSTOMER` | Customer messaging | `auto` | Informational message / recurring charge tip (R7) | None |
| `VERIFY_WITH_CUSTOMER` | Customer outreach | `auto` | Weak signal / single signal / probability < 0.70 (R1, R7) | Low |
| `STEP_UP_AUTH` | Customer challenge | `auto` | Step-up auth challenge before block (R1, R5) | Low |
| `BLOCK_CARD` | Specific card | `L1` if exposure ≤ $2,500<br>`L2` if exposure > $2,500 | Confirmed unauthorized activity / customer denial (R2, R5) | High |
| `BLOCK_ALL_CARDS` | All cards of customer | `L2` (always) | ≥ 2 customer cards confirmed fraud OR credentials compromised (R10) | Very High |
| `GENERATE_REPORT` | Case file record | `auto` | Internal documentation without opening full case | None |
| `CREATE_CASE` | Internal graph case | `auto` | Fraud probability ≥ 0.30, or evidence requested, or disputed charge (3a) | None |
| `FILE_REPORT` | Regulatory SAR | `L2` (always) | Confirmed/strongly suspected fraud AND (exposure > $1,000 OR shared device/region cluster OR R9 undocumented pattern) (3a, R2, R6, R9) | None |
| `ESCALATE_TO_ANALYST` | Case review | `auto` | Uncertain verdict with exposure > $500, conflicting evidence, or limit reached (R8, R9) | None |
| `CLOSE_NO_FRAUD` | Alert resolution | `auto` | Customer confirms legitimate, or evidence confirms false alarm (R3) | None |

---

## 2. Policy Rules (R1 - R10)

- **R1 (Verify Before Block):** If the case rests on a single signal (including risk score alone) and fraud probability < 0.70, recommend `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` before any block. Blocking on a single signal is a policy violation.
- **R2 (Customer Denies):** Recommend `BLOCK_CARD` and `CREATE_CASE`. Recommend `FILE_REPORT` if exposure > $1,000 or connected to shared device/compromised cluster.
- **R3 (Customer Confirms):** Recommend `CLOSE_NO_FRAUD`. Note confirmation in case record.
- **R4 (No Reply in 24h):** Recommend `MONITOR_CARD` and `DECLINE_TRANSACTION`. Escalate to analyst if exposure > $500.
- **R5 (Card Testing):** ≥ 3 small online authorizations within 1 hour followed by a larger purchase: recommend `DECLINE_TRANSACTION` and `STEP_UP_AUTH`. If purchase > $100 has cleared, recommend `BLOCK_CARD`.
- **R6 (Shared Origin):** Several cards show fraud from the same device profile, billing region, or recipient email in one window: recommend `CREATE_CASE`, `FILE_REPORT`, and `MONITOR_CONNECTED_CARDS`.
- **R7 (Disputed but Recurring/Legitimate):** If customer disputes charge matching recurring pattern (same merchant, same amount, monthly): recommend `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER`. Do NOT block.
- **R8 (Escalate Uncertain & Exposed):** If verdict is `uncertain` and exposure > $500, or evidence conflicts: recommend `ESCALATE_TO_ANALYST`.
- **R9 (Undocumented Patterns):** Coordinated or repeated abuse across customers not fitting known 5 patterns: recommend `CREATE_CASE`, `FILE_REPORT`, and `ESCALATE_TO_ANALYST`, describing the pattern in natural language.
- **R10 (Block All Cards Restriction):** Never recommend `BLOCK_ALL_CARDS` unless ≥ 2 customer cards show confirmed fraud or customer credentials are confirmed compromised.

---

## 3. Case vs SAR Filing Criteria (Section 3a)

- **Case (`CREATE_CASE`):**
  - Triggered when: fraud probability ≥ 0.30, OR evidence is requested, OR customer disputes a transaction.
  - Lifecycle: `NEW` → `INVESTIGATING` → `AWAITING_EVIDENCE` → `PENDING_APPROVAL` → `ACTIONED` → `CLOSED_FRAUD` / `CLOSED_LEGITIMATE` / `ESCALATED`.
  - Persisted to TigerGraph as vertex `Case` with findings and evidence edges.
- **SAR (`FILE_REPORT`):**
  - Triggered when: Fraud confirmed or strongly suspected AND at least one of:
    1. Exposure > $1,000 USD
    2. Shared device profile / region cluster linking multiple cards
    3. Coordinated / undocumented pattern (R9)
  - Approval route: `L2` (Fraud Manager approval mandatory).
  - Standalone regulatory filing format detailing Who, What, When, Where, How, and Why.

---

## 4. Recommendation Evolution: Pre vs Post Evidence (Section 3b)
- `initial`: Next best actions before additional evidence is requested.
- `evidence_requests`: Simulated customer or analyst interaction with assumed response.
- `final`: Updated next best actions following the evidence response.
- `what_changed`: Summary explaining how new evidence shifted probability, actions, and approval routes.
