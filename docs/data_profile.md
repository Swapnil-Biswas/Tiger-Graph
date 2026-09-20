# Data Profile: TigerGraph HHGOA IEEE-CIS Fraud Investigation Dataset

## 1. Overview
The dataset is built upon the IEEE-CIS Fraud Detection dataset (Vesta Corporation) with original columns retained, supplemented with synthetic banking investigation overlays created by TigerGraph:
- **Time range:** 2016-07-02 00:02:21 to 2016-12-31 23:58:54 (6 months)
- **Total transactions:** 590,742
- **Online identity records:** 144,432 (joined on `TransactionID`)
- **Closed historical cases:** 5,565 (Months 1-4: July to October 2016)
- **Exam / Benchmark cases:** 20 cases (Months 5-6: November to December 2016)
- **Customers:** ~13,500 distinct customer IDs (`C00001` .. `C13500+`)

---

## 2. File Profiles

### 2.1 `transactions.csv`
- **File size:** ~708 MB (675.14 MB uncompressed)
- **Row count:** 590,742 rows
- **Column count:** 397 columns
- **Key added fields:**
  - `customer_id`: e.g. `C06075` (index 393)
  - `ts`: `YYYY-MM-DD HH:MM:SS` (index 394)
  - `channel`: `in_person` or `online` (index 395)
  - `risk_score`: 0.0 to 1.0 floating point score from bank model (index 396)
- **Core transaction fields:**
  - `TransactionID`: unique integer string (e.g. `3000001` to `3590742`)
  - `TransactionDT`: seconds offset from dataset start
  - `TransactionAmt`: USD amount (floating point)
  - `ProductCD`: `W` (in-person, no identity record), `C`, `H`, `R`, `S` (online)
  - `card1` to `card6`: Card issuer codes, card network (`visa`, `mastercard`, `american express`, `discover`), card type (`credit`, `debit`)
  - `addr1`, `addr2`: Billing region and country codes (e.g. `87` = home country)
  - `dist1`, `dist2`: Physical distances
  - `P_emaildomain`, `R_emaildomain`: Purchaser and recipient email domains
  - `C1` to `C14`: Quantitative count signals
  - `D1` to `D15`: Timedeltas in days
  - `M1` to `M9`: Match status flags
  - `V1` to `V339`: Engineered relationship and score features

### 2.2 `identity.csv`
- **File size:** ~26.7 MB
- **Row count:** 144,432 rows
- **Columns:** 41 columns (`TransactionID`, `id_01` to `id_38`, `DeviceType`, `DeviceInfo`)
- **Key attributes:**
  - `id_15`: `New` / `Found`
  - `id_23`: Proxy status (`transparent`, `anonymous`, `hidden`)
  - `id_30`: Operating System (e.g. `Android 7.0`, `iOS 11.1.2`, `Windows 10`)
  - `id_31`: Browser (e.g. `samsung browser 6.2`, `chrome 62.0 for android`, `mobile safari 11.0`)
  - `id_32`: Screen depth
  - `id_33`: Screen resolution (e.g. `2220x1080`, `1920x1080`)
  - `id_34`: Match status
  - `DeviceType`: `mobile` or `desktop`
  - `DeviceInfo`: Device model string (e.g. `SAMSUNG SM-G892A Build/NRD90M`, `iOS Device`, `Windows`)

### 2.3 `closed_cases_history.csv`
- **File size:** ~2.7 MB
- **Row count:** 5,565 rows
- **Period:** July 2 to October 31, 2016 (Months 1-4)
- **Columns:**
  - `case_id`: e.g. `CC-0001`
  - `customer_id`: e.g. `C00259`
  - `card_id`: e.g. `C00259-K1`
  - `opened_at`, `closed_at`: Timestamps
  - `outcome`: `confirmed_fraud` (4,665) | `cleared` (900)
  - `pattern`:
    - `card_not_present_fraud`: 1,404
    - `account_takeover`: 1,205
    - `card_not_present_new_device`: 1,076
    - `out_of_region_use`: 955
    - `none`: 900 (all `cleared` cases)
    - `card_testing`: 16
    - `undocumented`: 9
  - `first_fraud_txn_id`: Root fraudulent transaction ID
  - `txn_ids`: Pipe-separated list of transaction IDs involved
  - `n_txns`: Number of affected transactions
  - `exposure_usd`: Financial loss / exposure amount
  - `connected_card_ids`: Additional connected cards
  - `actions_taken`: Pipe-separated historical actions (e.g. `CREATE_CASE|BLOCK_CARD`)
  - `report_filed`: `Yes` (397) | `No` (5,168)
  - `analyst_notes`: Natural language rationale and investigation notes

### 2.4 `case_pack.csv`
- **Row count:** 20 rows (HHG-001 to HHG-020)
- **Period:** November to December 2016 (Months 5-6)
- **Triggers:**
  - `risk_score`: 11 cases (scores ranging 0.52 to 0.90)
  - `customer_report`: 8 cases (customer disputes charge amounts from $30.02 to $482.12)
  - `analyst_request`: 1 case (HHG-014, shared device investigation across cards)
- **Columns:** `case_id`, `opened_at`, `trigger_type`, `trigger_text`, `flagged_txn_id`, `card_id`, `customer_id`, `risk_score`

---

## 3. Entity Resolution & Graph Model

### Entity Identifiers:
1. **Customer**: `customer_id` (e.g. `C12382`).
2. **Card**: `card_id` (e.g. `C12382-K1`, `C08623-K2`).
   - Suffixes in historical data and benchmark: `K1` (53%), `K2` (46%), `K3` (<1%).
   - Mapping rule: transactions for a customer are assigned to cards by matching `card1`..`card6` signatures.
3. **Transaction**: `TransactionID` (e.g. `3514030`).
4. **DeviceProfile**: Composite string `DeviceInfo | OS | browser | screen` from `identity.csv` (e.g. `SAMSUNG SM-G892A Build/NRD90M | Android 7.0 | samsung browser 6.2 | 2220x1080`).
5. **BillingRegion**: `addr1` code (e.g. `444.0`, `264.0`).
6. **EmailDomain**: `P_emaildomain` / `R_emaildomain`.
7. **ClosedCase**: `case_id` (e.g. `CC-0001`).

### Graph Traversal Integrity:
- **No data leakage:** All historical lookups, baseline profiles, and graph traversals for a case opened at `T_open` must filter `ts <= T_open`.
- Benchmark evaluation cases from months 5-6 must never be written into the memory graph prior to backtesting or evaluation.
