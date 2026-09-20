# TigerGraph Agentic Fraud Investigator: 3-5 Minute Demo Script

**Target Audience:** Judges, Fraud Risk Executives, and AI Engineers  
**Live UI URL:** `http://127.0.0.1:8000/`  
**Duration:** 4 minutes 30 seconds  

---

## Act 1: Problem Framing & Architecture (0:00 – 0:30)

### Speaker Narration:
> "Hello everyone. Today, financial fraud costs the global economy over $40 billion annually. Banks rely on machine learning models that generate transaction risk scores. But here's the problem: an isolated score tells you *nothing* about rings, device sharing, or customer context. Analysts spend an average of **3.1 days** manually investigating alerts, while fraud syndicates drain funds in minutes.
> 
> We built the **TigerGraph Autonomous Agentic Fraud Investigator**—a sub-second, end-to-end cognitive defense system that combines **TigerGraph native graph analytics**, **GraphRAG episodic memory**, and **deterministic banking policy guardrails**."

### Visual Action:
- Open Web UI showing the dark-mode dashboard with Live System Stats (`Graph: 590,742 Txns | 13,770 Cards`, `Policy Engine: 10 Rules Active`).
- Briefly highlight the architecture diagram in the presentation slide.

---

## Act 2: Clear-Cut Fraud Investigation (`HHG-004`) (0:30 – 1:30)

### Speaker Narration:
> "Let's investigate case **HHG-004**. Notice our trigger: an authorization alert on card `C12158-K1`.
> 
> Watch what happens when I click **'Investigate Live'**."

### Visual Action:
1. In the Case Ingestion Queue, select **HHG-004**.
2. Click **"Run Full Investigation"**.
3. Point out the live Server-Sent Events (SSE) streaming in the **Live Investigation Stream**:
   - Step 1: Ingesting trigger.
   - Step 2: Running GSQL Queries Q1–Q12.
   - Step 3: GraphRAG memory search over 5,565 closed cases.
   - Step 4: Topological entity sharing analysis.
4. Point to the **Interactive Graph Explorer**:
   - Show the red central card node connected to the flagged transaction, surrounded by orange shared device nodes and linked cards.
5. Point to the **Verdict Badge**:
   - `VERDICT: FRAUD` | `Pattern: card_not_present_new_device` | `Exposure: $128.33`.
6. Show the **Action Recommendation**:
   - `BLOCK_CARD` (Route: `L1`), `CREATE_CASE` (Route: `auto`), `MONITOR_CONNECTED_CARDS` (Route: `auto`), `FILE_REPORT` (Route: `L2`).

### Speaker Narration:
> "In just 30 milliseconds, the agent queried the graph, discovered that this transaction originated from an unrecognized device that links to two other cards, matched the historical pattern, drafted actions, and queued a card block for L1 approval."

---

## Act 3: Ambiguous Case & Recommendation Evolution (`HHG-001`) (1:30 – 3:00)

### Speaker Narration:
> "Now let's examine what makes this truly agentic: **ambiguous cases with recommendation evolution**.
> 
> Look at case **HHG-001**. The machine learning score fired at `0.61`—a medium-risk alert. If a generic system blocked the card right now, that would violate **Banking Rule R1: Verify Before Block**. Let's see how our agent handles it."

### Visual Action:
1. Select **HHG-001** in the Case Queue.
2. Click **"Run Full Investigation"**.
3. Point to the **Pre-Evidence vs Post-Evidence Comparison Box**:
   - **Initial Actions:** `VERIFY_WITH_CUSTOMER` (auto), `CREATE_CASE` (auto).
   - **Simulated Customer Outreach:** Customer confirms: *"Customer confirms this transaction was authorized and made by them."*
   - **Recommendation Evolution (What Changed):** *"Cardholder confirmed transaction legitimacy; risk reduced to 0.05. Replaced customer verification with ALLOW_TRANSACTION and CLOSE_NO_FRAUD."*
   - **Final Actions:** `ALLOW_TRANSACTION` (auto), `CLOSE_NO_FRAUD` (auto).
4. Point to the **Audit Explainer**:
   - Shows the auditable evidence trail citing graph query refs: `query:get_txn(3514030)`, `query:entity_profile(C12382-K1)`.

### Speaker Narration:
> "Notice how the agent recognized uncertainty, simulated cardholder verification, and upon confirmation safely evolved its recommendation to allow the transaction and clear the alert—preventing customer churn without human intervention."

---

## Act 4: GraphRAG Memory & FinCEN SAR Filing (3:00 – 3:40)

### Speaker Narration:
> "Next, let's look at regulatory compliance and episodic memory. For qualifying fraud cases, regulatory agencies require a Suspicious Activity Report (SAR).
> 
> Let's look at the generated SAR tab for **HHG-004**."

### Visual Action:
1. Click on the **"SAR Regulatory Filing"** tab.
2. Scroll through the generated FinCEN filing:
   - **Subject Entities:** Customer IDs, Card IDs, and Device Fingerprints.
   - **Exposure USD:** Total accumulated suspicious volume.
   - **Narrative:** Complete, legally grounded 6-W narrative covering Who, What, When, Where, How, and Why.
3. Switch to the **"GraphRAG Memory"** tab:
   - Show the top-3 most topologically similar closed cases retrieved from the 5,565 historical database.

### Speaker Narration:
> "The agent automatically crafts an auditable, legally binding narrative adhering to FinCEN guidelines, citing every connected card and transaction ID. No manual document preparation required."

---

## Act 5: Deterministic Policy Airbags & Approval Queue (3:40 – 4:20)

### Speaker Narration:
> "How do we prevent rogue AI actions? Through our **Deterministic Policy Engine**.
> 
> Actions are classified into three strict tiers: `auto`, `L1` (Team Lead), and `L2` (Fraud Manager). Even if the LLM attempted to execute `BLOCK_ALL_CARDS`, Rule R10 would intercept and reject it unless at least two cards are proven compromised."

### Visual Action:
1. Navigate to the **"Approval Queue"** panel.
2. Show the pending `L1` card block and `L2` SAR filing for **HHG-004**.
3. Enter analyst notes: *"Graph evidence verified. Device ring confirmed."*
4. Click **"Approve Action"**.
5. Show the live toast notification: *"Action BLOCK_CARD executed via Mock Actions API. Card status updated to BLOCKED in TigerGraph."*

---

## Act 6: Benchmark Results & Closing (4:20 – 5:00)

### Speaker Narration:
> "To prove reliability, we ran our agent against all 20 benchmark cases and backtested across 5,565 historical investigations:
> - **20/20 Benchmark Cases Passed:** 100% strict schema validation with zero missing fields.
> - **100% Precision in Historical Backtesting:** Zero false alarms on cleared accounts.
> - **Turnaround Time Slashed by >99.99%:** From **3.09 days** down to **19 milliseconds per case**.
> - **71.1% Auto-Routed:** Safely automating three out of four decisions under strict policy guardrails.
> 
> This is the future of autonomous financial defense: graph-native intelligence, grounded in memory, secured by deterministic policy. Thank you!"

### Visual Action:
- Open `eval/benchmark_run.py` terminal output showing the 20/20 green benchmark results table.
- Display GitHub repository URL: `https://github.com/Swapnil-Biswas/Tiger-Graph`.
