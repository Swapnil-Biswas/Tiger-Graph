# Discovered Fraud Pattern Documentation (Phase 2)

## 1. Discovered Pattern 6: Multi-Card Proxy Rotation & Credential Stuffing

### 1.1 Overview
- **Pattern Name:** `multi_card_proxy_rotation` (origin: `discovered`)
- **Category:** Undocumented / Coordinated Multi-Account Attack
- **Identified in Closed Cases:** `CC-2649`, `CC-2971`, `CC-2985` (and 6 other cases from Months 1–4)

### 1.2 Signature & Graph Characteristics
1. **Device Fingerprint Re-use:** Online transactions across distinct, unrelated customer accounts originate from the exact same hardware/browser build:
   - Device: `SAMSUNG SM-G935F Build/NRD90M`
   - OS: `Android 7.0`
   - Browser: `chrome 62.0 for android`
   - Screen: `1920x1080`
2. **Proxy Anonymization:** `id_23` is consistently flagged as `anonymous` or `hidden` proxy.
3. **Novelty to Account:** For every affected customer, the device is flagged as `New` (`id_15 == "New"`), having zero prior appearance in the customer's transaction history.
4. **Multi-Customer Cluster:** Within a short temporal window (e.g. within the same 14–30 days), 3 or more independent cards share this exact device profile.
5. **Burst Sequence:** 2–3 rapid online purchases ranging from $50 to $200 each per card, totaling $100–$400 in exposure per compromised cardholder.

### 1.3 Policy & Next-Best-Action Response
Under Bank Fraud Policy Rule **R6** and **R9**:
1. Recommend `CREATE_CASE` and `FILE_REPORT` (SAR required due to cross-customer coordination).
2. Recommend `BLOCK_CARD` for the affected cardholder.
3. Recommend `MONITOR_CONNECTED_CARDS` for every card linked to this device profile.
4. Recommend `ESCALATE_TO_ANALYST` with cluster summary.
