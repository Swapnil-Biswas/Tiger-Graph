# Answer File Format Specification

Every benchmark case evaluation produces a JSON answer file named `<case_id>.json` (e.g. `HHG-001.json` to `HHG-020.json`) placed in `cases/` or `outputs/answers/`.

---

## 1. Top-Level Schema

```json
{
  "case_id": "string (from case_pack.csv)",
  "case": { ... },
  "evidence_requests": [ ... ],
  "next_best_actions": { ... },
  "sar": { ... },
  "stop_reason": "string",
  "tool_calls": 0,
  "tokens": 0,
  "latency_s": 0.0
}
```

---

## 2. Part 1: `case` Object

| Field | Type | Description |
|---|---|---|
| `status` | string | `"open"` \| `"closed_fraud"` \| `"closed_legitimate"` \| `"escalated"` |
| `verdict` | string | `"fraud"` \| `"legitimate"` \| `"uncertain"` |
| `fraud_probability` | float (0.0 to 1.0) | Assessed probability of fraud |
| `pattern` | enum string | `"card_testing"` \| `"card_not_present_fraud"` \| `"card_not_present_new_device"` \| `"out_of_region_use"` \| `"account_takeover"` \| `"undocumented"` \| `"none"` |
| `pattern_description` | string | Required if `pattern == "undocumented"`; otherwise `""` |
| `affected_txn_ids` | list[string] | Transaction IDs belonging to this fraud episode. Empty `[]` if legitimate |
| `first_suspicious_txn_id` | string | Root transaction ID where fraud began, or `""` if legitimate |
| `connected_card_ids` | list[string] | Other cards caught in compromise, ring, or device |
| `connected_device_profiles` | list[string] | Device profile strings connecting this case to other cards |
| `exposure_usd` | float | Sum of absolute dollar amounts of `affected_txn_ids`. `0.0` if legitimate |
| `evidence` | list[object] | Each item: `{"claim": "...", "source": "graph"|"document"|"customer"|"external", "ref": "...", "entity_ids": [...]}` |
| `similar_prior_cases` | list[string] | Closed case IDs retrieved from memory (e.g. `["CC-0141"]`) |
| `summary` | string | 2-6 sentence summary for analyst review |
| `written_to_graph` | boolean | True if written to TigerGraph case vertex |
| `graph_case_id` | string | Vertex ID created in graph, or `""` |

---

## 3. Part 2: `sar` (Suspicious Activity Report) Object

| Field | Type | Description |
|---|---|---|
| `file` | boolean | Whether SAR must be filed (must match presence of `FILE_REPORT` in actions) |
| `reason` | string | Policy citation justifying filing (or why not filed) |
| `narrative` | string | 6-12 sentences covering Who, What, When, Where, How, and Why. Required if `file == true`; `""` if `file == false` |
| `subjects` | list[string] | Entities named (customer IDs, card IDs, devices). Empty if not filed |
| `total_amount_usd` | float | Sum of suspicious activity amounts. `0.0` if not filed |
| `activity_dates` | list[string] | `["YYYY-MM-DD", "YYYY-MM-DD"]` date range. Empty if not filed |

---

## 4. Part 3: `next_best_actions` Object

| Field | Type | Description |
|---|---|---|
| `initial` | list[object] | Recommended actions **before** additional evidence response: `[{"action": "...", "route": "auto"|"L1"|"L2", "reason": "..."}]` |
| `final` | list[object] | Recommended actions **after** evidence response. Same structure as `initial` |
| `what_changed` | string | Explanation of why `final` differs from `initial`, or `"nothing"` |

---

## 5. `evidence_requests` Array

Each item in the list represents a simulated inquiry:
```json
{
  "type": "customer_validation" | "step_up_auth" | "analyst_info",
  "asked_after_step": 4,
  "assumed_response": "Customer states they did not make these purchases and still has the card"
}
```
If no additional evidence was requested, this array is `[]`.
