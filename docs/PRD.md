# PRD: Agentic Fraud Investigation & Next-Best-Action Agent (TigerGraph HHGOA)

**Version:** 1.0  |  **Target builder:** Antigravity (Gemini Flash, high reasoning)  |  **Status:** Ready to build

> **How to use this PRD with Antigravity:** Build phase by phase (Section 22). Do not start a phase until the previous phase's acceptance criteria pass. Read Section 23 (Agent Operating Rules) first. Anything marked **[VERIFY]** depends on the dataset README or TigerGraph version and must be checked against the real files, never guessed.

---

## 1. Product Summary

We are building an **AI fraud investigator** for a bank's fraud team. Given a trigger (a risk score, a customer report, or an analyst request), the agent opens a case, investigates using a **TigerGraph knowledge graph** plus **GraphRAG** over fraud policy documents, decides whether it has enough evidence, requests more evidence through controlled simulated actions if not, recommends or executes policy-permitted next actions, explains itself, and writes everything back to the graph as **case memory** so future investigations improve.

**One-line pitch:** *From an uncertain fraud signal to a defensible, explained, policy-compliant action, with a full case record and learning from past cases.*

**Core principle:** The graph does the analysis. The LLM does reasoning, tool selection, evidence synthesis, and explanation. The LLM never replaces graph analysis and never bypasses the policy engine.

## 2. Goals, Non-Goals, Success Criteria

### 2.1 Goals
1. Accurately classify fraud type and risk on the 20 benchmark cases (final two months of data).
2. Make good next-best-action decisions, including correctly choosing **"need more evidence"** on ambiguous cases, and **updating** the recommendation after evidence arrives.
3. Produce a complete, auditable case record per case, written to the graph and exported as one answer file per case.
4. Show real agentic behavior: tool use, a loop with a sufficiency check, memory retrieval, permissions and approvals.
5. Deliver a polished UI and a 3-5 minute demo that shows the whole flow end to end.

### 2.2 Non-Goals
- Training a production-grade fraud model. (The bank's risk score is given; we use it as one signal, not the answer.)
- Real integrations. All customer messaging, freezes, card blocks, refunds, CRM updates, and case closure are **mock APIs**.
- Real-time streaming infrastructure. Batch/on-demand investigation is enough.

### 2.3 Success Criteria mapped to judging weights

| Judging criterion (weight) | What we must demonstrate | Primary sections |
|---|---|---|
| Investigation accuracy (25%) | Correct fraud typology, entities, and evidence on benchmark cases; discover at least some undocumented patterns | 8, 9, 12 |
| Next best action (25%) | Correct action under uncertainty; evidence request before/after; recommendation updates | 12.5, 13, 16 |
| Case summary & explainability (10%) | Clear case, evidence citations, reasoning trace, uncertainty statement | 14, 17 |
| Agentic design & engineering (15%) | Orchestrated workflow, MCP tools, memory, permissions, controls | 6, 12, 13, 15 |
| Innovation (15%) | Graph-native evidence scoring, memory-based pattern learning, undocumented pattern discovery, GraphRAG grounding | 9, 10, 15 |
| Demo quality (10%) | Live end-to-end run with visible case progression | 19, 24 |

## 3. Users and Key Scenarios

**Personas**
- **Fraud Analyst (primary):** reviews agent output, approves gated actions, overrides decisions. Needs evidence and reasoning fast.
- **Fraud Team Lead:** cares about consistency, policy compliance, audit trail.
- **Customer (simulated):** answers validation and step-up requests (mock responder).

**Scenarios to support**
1. **Score trigger:** a transaction with a high risk score arrives; agent investigates.
2. **Customer report:** customer says "I don't recognize this transaction."
3. **Analyst request:** analyst asks "investigate this account / this device."
4. **Ambiguous case:** medium risk, conflicting signals; agent asks the account owner to validate, then revises.
5. **Ring case:** shared device/email/address across many customers; agent escalates and proposes monitoring of the connected cluster.
6. **SAR-required case:** policy threshold met; agent drafts a suspicious activity report and routes for approval.

## 4. Inputs, Assumptions, and Open Items

The brief describes the dataset ("HHGOA_IEEE") but the **dataset README was not available when this PRD was written.** The first task of the build is discovery.

**Known from the brief**
- IEEE-CIS Fraud Detection data (Vesta): ~590K card transactions, ~6 months, ~13,500 customers, plus device/connection identity records for online transactions. All original rows and columns retained.
- Each transaction has a **bank risk score**. There is **no `isFraud` flag**.
- **Closed investigations** from months 1-4 (confirmed fraud and cleared) are provided: use as memory and for backtesting.
- Provided: bank **fraud policy**, **five known fraud patterns**, **regulatory references**.
- **20 benchmark cases** from months 5-6, same for every team.
- **Not every pattern in the data is documented.**

**[VERIFY] items to resolve from the README (Phase 0)**
- Exact filenames, column names, join keys (customer -> card -> transaction -> identity).
- Case file format: trigger types, fields per case, ground-truth fields (hidden or not).
- **Required answer file format** (schema, naming, before/after evidence structure). Our output must match it exactly; build an adapter layer (Section 18) so internal models can change without breaking it.
- Policy: risk thresholds, SAR criteria, permitted actions per role, approval routes, evidence-request rules.
- The five fraud patterns' definitions and signatures.
- TigerGraph version (vector search and GraphRAG availability differ) and whether we use Savanna or Community Edition.

## 5. Constraints and Compliance Rules

- **Required:** TigerGraph (Savanna or Community), GSQL + graph algorithms, TigerGraph MCP, GraphRAG, a user interface.
- If using Savanna: **enable auto-stop and auto-start**.
- Actions may be simulated. Every action must go through the policy engine.
- Case must be **written to the graph**.
- **No data leakage:** memory and any calibration may only use months 1-4 closed cases. Benchmark outcomes must never be written into memory before evaluation. If the README exposes benchmark ground truth, never load it into the agent's reachable store.
- Do not hard-code answers for benchmark cases. Logic must generalize.

## 6. System Architecture

```
                    +------------------------------+
                    |  UI (React + Vite / Streamlit fallback)  |
                    |  Case board | Investigation view | Graph  |
                    |  Approvals | Timeline | Memory panel     |
                    +---------------+--------------+
                                    | REST + SSE (streamed agent steps)
                    +---------------v--------------+
                    |        FastAPI Backend        |
                    |  /investigate /cases /approve |
                    +---------------+--------------+
                                    |
        +---------------------------v---------------------------+
        |              Agent Orchestrator (LangGraph)            |
        |  Trigger > Investigate > Gather > Assess >             |
        |  (Need more? > Request Evidence > Reassess) >          |
        |  Decide Actions > Explain > Update Memory              |
        +----+-------------+--------------+-------------+-------+
             |             |              |             |
     +-------v----+  +-----v------+  +----v-----+  +----v---------+
     | Graph Tools|  | GraphRAG   |  | Policy & |  | Mock Action  |
     | (TigerGraph|  | Retriever  |  | Permission| | APIs (stubs) |
     |  MCP+GSQL) |  | (policy,   |  | Engine    |  | + Customer   |
     |            |  | typologies)|  | (determin.)| | Simulator    |
     +-------+----+  +-----+------+  +-----------+  +--------------+
             |             |
       +-----v-------------v------+
       |       TigerGraph         |
       |  Transaction graph       |
       |  Case graph + memory     |
       |  Vector index (policy,   |
       |  case summaries)         |
       +--------------------------+
        LLM (Gemini): reasoning, tool selection, synthesis, explanation
```

**Key design decisions**
1. **Deterministic guardrails around a probabilistic reasoner.** Risk scoring components, sufficiency thresholds, and permissions are computed in code. The LLM proposes; the policy engine disposes.
2. **Graph-first evidence.** Every evidence item is a graph-derived fact with an ID (vertex/edge IDs, query name) so explanations can cite it.
3. **Everything is a case event.** Each agent step appends a timestamped event to the case. The UI timeline and the answer file are both rendered from this event log.

## 7. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Graph DB | TigerGraph Savanna (preferred for demo) or Community | Enable auto-stop/start on Savanna |
| Graph access | `pyTigerGraph` + installed GSQL queries + **TigerGraph MCP** | Agent calls graph via MCP tools; bulk ingestion via pyTigerGraph/loading jobs |
| GraphRAG | TigerGraph GraphRAG (or custom GraphRAG on TigerGraph vectors) | **[VERIFY]** version support; fallback: vector attribute + GSQL traversal |
| Agent framework | LangGraph (Python) | Explicit state machine suits the 8-step flow and is easy to visualize |
| LLM | Gemini (Flash for tool loops, higher tier for final explanation if available) | Structured JSON outputs via schema; low temperature |
| Embeddings | Gemini embedding model or a local sentence-transformer | For policy chunks and case summaries |
| Backend | FastAPI, Pydantic v2 | SSE for streaming steps |
| Frontend | React + Vite + Tailwind + Cytoscape.js (graph view) | **Fallback: Streamlit + pyvis** if time is short |
| Data prep | pandas / polars | 590K rows is fine locally |
| Testing | pytest; a benchmark runner script | Section 21 |

Keep dependencies few. Pin versions in `requirements.txt` and `package.json`.

## 8. Data and Graph Model

### 8.1 Ingestion approach
1. **Profile first (Phase 0):** print every file's schema, row counts, null rates, join-key coverage. Save as `docs/data_profile.md`.
2. **Entity resolution:** decide identity keys. In IEEE-CIS there is no native customer ID; the dataset here provides ~13.5K customers **[VERIFY how customer is keyed]**. If a customer key is missing for some rows, derive a pseudo-identity from card attributes + address + email domain, and document the choice.
3. Load using TigerGraph loading jobs (bulk) rather than row-by-row upserts.

### 8.2 Proposed schema (adapt names to the real data)

**Vertices**
- `Customer(id, ...profile attrs)`
- `Card(id, card_brand, card_type, ...)`
- `Transaction(id, amount, ts, product_code, risk_score, channel, ...key engineered attrs)`
- `Device(id, device_type, device_info)`
- `Connection/IP-like(id)` for identity/network signals **[VERIFY]**
- `EmailDomain(id)`, `Address(id)` (billing/shipping region keys)
- `Merchant/ProductCode(id)` if applicable
- `FraudPattern(id, name, description, signature)` (the five documented patterns + discovered ones)
- `Case(id, status, risk_level, fraud_type, confidence, opened_ts, closed_ts, disposition, source: historical|benchmark|live)`
- `Finding(id, kind, statement, strength, ts)`
- `Evidence(id, source_query, payload_json, ts)`
- `Action(id, type, status, requires_approval, approver, ts, simulated)`
- `PolicyChunk(id, doc, section, text, embedding)`
- `CaseSummary(id, text, embedding)` (memory unit)

**Edges** (directed unless noted)
- `Customer -HAS_CARD-> Card`, `Card -MADE-> Transaction`
- `Transaction -USED_DEVICE-> Device`, `Transaction -FROM_ADDR-> Address`, `Transaction -EMAIL_DOMAIN-> EmailDomain`, `Transaction -VIA_CONN-> Connection`
- `Customer -USES_DEVICE-> Device` (derived, weighted by count)
- `Case -ABOUT-> Transaction | Card | Customer` (subject)
- `Case -HAS_FINDING-> Finding`, `Finding -SUPPORTED_BY-> Evidence`, `Evidence -REFERENCES-> (any vertex)`
- `Case -MATCHES_PATTERN-> FraudPattern` (with confidence)
- `Case -TOOK_ACTION-> Action`
- `Case -SIMILAR_TO-> Case` (memory link, with similarity score)
- `Finding -CITES_POLICY-> PolicyChunk`
- `Case -RESOLVED_AS-> ...` for historical outcomes

**Design notes**
- Store the **risk score as an attribute**, never as a label.
- Precompute derived attributes at load time where cheap (e.g., time since previous txn on the card, per-card rolling counts) but prefer GSQL for anything explainable, so evidence can cite the query.
- Time is central: all "as of" queries must respect the investigated transaction's timestamp so we don't use future information (important for fairness and realism).

## 9. Graph Analytics (GSQL Query Library)

Each query is installed, versioned in `gsql/`, exposed as an MCP tool or wrapped by the graph service, and returns **structured JSON with stable IDs** so results can be cited as evidence. Every query takes an `as_of` timestamp.

| # | Query | Purpose | Signals returned |
|---|---|---|---|
| Q1 | `entity_profile(customer/card)` | Baseline behavior | avg/median amount, typical hours, typical channel, typical devices, txn count |
| Q2 | `txn_context(txn_id, window)` | Neighborhood of a transaction | prior/next txns on card, gaps, amount deviation z-score |
| Q3 | `velocity(card, windows)` | Burst detection | txn counts/amount sums in 5m/1h/24h/7d vs baseline |
| Q4 | `device_sharing(device/txn)` | Device linkage | # distinct cards/customers on device, first-seen, other cases touching it |
| Q5 | `identity_link_expand(seed, k)` | K-hop expansion via shared device/email/address/connection | connected entities, hop paths |
| Q6 | `ring_detection(seed)` | Fraud ring candidates | component/community id, size, density, hub entities |
| Q7 | `new_entity_check(txn)` | Novelty | first-time device/address/email-domain/merchant for this customer |
| Q8 | `geo_impossible(card)` | Geographic anomaly | distance/time implausibility using address keys **[VERIFY]** |
| Q9 | `money_flow_trace(seed, hops)` | Trace movement across linked entities | ordered flow paths, amounts |
| Q10 | `similar_cases(seed_features)` | Structural memory retrieval | historical cases sharing entities or pattern signatures |
| Q11 | `pattern_match(txn/case, pattern_id)` | Test the 5 documented signatures | per-criterion pass/fail with evidence |
| Q12 | `case_history(entity)` | Prior cases touching the entity or its neighbors | outcomes (confirmed/cleared) |

**Graph algorithms to apply** (TigerGraph library, run offline and cached, results stored as vertex attributes with `algo_run_ts`):
- **Weakly connected components / Louvain** on the entity-link graph -> ring and community candidates.
- **PageRank or degree centrality** on device/address nodes -> identify hub entities used by many cards.
- **Jaccard/cosine similarity** between customers' device/address sets -> synthetic-identity and account-takeover linkage.
- **Shortest path / k-hop** between a case entity and known-confirmed-fraud entities from months 1-4 -> "guilt by association" evidence, weighted by hop distance.
- **Triangle counting / clustering coefficient** (optional) -> dense collusion structure.

**Undocumented pattern discovery (innovation hook):** run community detection + hub analysis over months 1-4, compare cluster stats against confirmed-fraud vs cleared cases, and record any cluster signature that strongly separates them as a new `FraudPattern` with `origin = "discovered"`. Report these in the blog and UI. Evaluate that discovered patterns are not overfit by testing on held-out closed cases (e.g., month 4).

## 10. GraphRAG Design

**Goal:** give the LLM *connected, relevant context*, not raw rows.

**Knowledge sources**
1. Policy documents, five fraud patterns, regulatory references (chunked by section; each chunk embedded and stored as `PolicyChunk`).
2. Case summaries from months 1-4 (memory).
3. Live graph neighborhoods (case-specific subgraph).

**Retrieval pipeline**
1. Build a **query context** from the case: trigger type, suspected pattern hypotheses, entity types involved, uncertainty type.
2. **Vector search** over `PolicyChunk` and `CaseSummary`.
3. **Graph expansion:** from the top hits, traverse to related chunks (same policy section, cross-references), related patterns, and linked historical cases.
4. **Context assembly:** produce a compact, structured brief:
   - Case facts (from graph queries, with evidence IDs)
   - Applicable policy clauses (with chunk IDs)
   - Matching pattern definitions and which criteria are met/unmet
   - Top-k similar past cases with outcomes and why they're similar
5. Pass the assembled brief to the LLM. **Cap the context size** and rank by relevance. Log what context was supplied (for explainability and debugging).

If TigerGraph's GraphRAG package is unavailable in our environment, implement the same pipeline using TigerGraph vector attributes plus GSQL expansion. Document which path was used.

## 11. TigerGraph MCP Tool Layer

Expose to the agent, through the TigerGraph MCP server plus a thin custom tool wrapper where MCP doesn't cover a need:

- **Read tools:** run installed query by name with params (Q1-Q12), get vertex/edge, run parameterized traversals.
- **Write tools:** create/update `Case`, `Finding`, `Evidence`, `Action`, `Case -SIMILAR_TO-> Case`, memory nodes.
- **Vector tools:** `search_policy(text, k)`, `search_cases(text, k)`.

**Rules**
- Read tools are always allowed. Write tools are limited to case/memory vertex types (the agent cannot modify transaction history).
- Each tool call is logged into the case event log (tool name, args, result summary, latency).
- Tool schemas are strict (Pydantic), with clear descriptions the LLM can select from. Keep the tool list small and semantically distinct so a Flash-tier model selects reliably.

## 12. Agent Design

### 12.1 State machine (LangGraph)

```
TRIGGER -> OPEN_CASE -> RETRIEVE_MEMORY -> INVESTIGATE (loop) -> ASSESS
   ASSESS --sufficient--> DECIDE_ACTIONS
   ASSESS --insufficient--> PLAN_EVIDENCE_REQUEST -> POLICY_CHECK -> REQUEST_EVIDENCE
                              -> AWAIT/RECEIVE -> INVESTIGATE (loop) -> ASSESS
   DECIDE_ACTIONS -> POLICY_CHECK -> EXECUTE_OR_QUEUE_APPROVAL -> EXPLAIN -> UPDATE_MEMORY -> END
```

Hard limits: max investigation loops (e.g., 3), max evidence requests (e.g., 2), max tool calls per loop; on exhaustion the agent must **escalate to an analyst** with what it knows (never loop forever, never guess).

### 12.2 Node responsibilities

1. **TRIGGER:** normalize input into a `Trigger` object (`type: score|customer_report|analyst_request`, subject IDs, payload, timestamp).
2. **OPEN_CASE:** create or reopen a `Case` in the graph (dedupe if an open case already covers the same entity). Log event.
3. **RETRIEVE_MEMORY:** Q10/Q12 + `search_cases`. Surface top-k similar past cases with outcomes. Record which memories influenced the run.
4. **INVESTIGATE:** LLM chooses tools (from the library), but a **deterministic core plan always runs first**: profile (Q1), context (Q2), velocity (Q3), device/identity (Q4, Q5, Q7), ring (Q6), pattern matches (Q11 for all five). The LLM may then add follow-ups (e.g., money flow trace, geo check) based on what it saw. Each result is stored as `Evidence`; the LLM writes `Finding`s that **must reference evidence IDs** (reject findings without them).
5. **ASSESS:** compute the structured assessment (12.4). LLM synthesizes fraud-type hypotheses and explains; numbers come from code.
6. **PLAN_EVIDENCE_REQUEST:** identify *what specific unknown* would most reduce uncertainty (e.g., "cardholder recognizes txn?" or "step-up auth passes?"). Choose the cheapest policy-permitted action that resolves it.
7. **DECIDE_ACTIONS:** propose one or more actions from the permitted catalog (12.6) with rationale and evidence references.
8. **POLICY_CHECK:** deterministic engine (Section 13) returns allow / requires-approval / deny for each action.
9. **EXPLAIN:** produce the structured explanation (Section 17).
10. **UPDATE_MEMORY:** write case summary + embedding, entity/pattern links, outcome (or "pending review" for benchmark cases).

### 12.3 Agent state (Pydantic)

`InvestigationState`: `trigger`, `case_id`, `evidence[]`, `findings[]`, `hypotheses[]` (fraud_type, probability, supporting_evidence_ids, contradicting_evidence_ids), `assessment` (12.4), `memory_hits[]`, `policy_hits[]`, `pending_requests[]`, `actions[]`, `events[]`, `loop_count`, `stop_reason`.

### 12.4 Uncertainty and sufficiency model (core to the 25% "next best action" score)

Compute in code, from graph evidence, not from LLM vibes:

- **Risk score `R` (0-100):** weighted combination of signal families: bank risk score, velocity anomaly, novelty (new device/address), device/identity sharing, ring/community proximity to confirmed fraud, geo anomaly, pattern-criteria match ratio, memory-based prior from similar cases. Keep the weights in `config/scoring.yaml` and tune them **only on months 1-4 data**.
- **Confidence `C` (0-1):** function of (a) evidence coverage (are the key signal families populated?), (b) agreement between families, (c) presence of contradicting evidence (e.g., consistent with customer's history), (d) strength of nearest confirmed/cleared precedents.
- **Ambiguity flag:** high `R` with low `C`, or conflicting families (e.g., device is new but amount/merchant fit habits perfectly).
- **Sufficiency rule:** the agent may act when `C >= C_act` **or** when the highest-risk action is low-regret (see 12.5). Otherwise it must gather more evidence, subject to loop limits.

**Stop criteria ("enough evidence to defend an action"):** (1) `C` above threshold, (2) the top hypothesis beats the runner-up by a margin, (3) no remaining permitted evidence action would plausibly change the recommendation, or (4) limits reached, in which case escalate.

### 12.5 Next-best-action logic

Decision is a function of `(R, C, fraud_type, policy, action cost/regret)`. Illustrative starting matrix (calibrate on months 1-4 and to the real policy **[VERIFY]**):

| Situation | Preferred action(s) |
|---|---|
| High R, high C, clear typology | Block transaction/card, open/escalate case; file SAR if policy criteria met; warn customer |
| High R, high C, ring evidence | Escalate to analyst, monitor/flag linked entities, recommend cluster review (needs approval) |
| Mid R, low C (ambiguous) | **Request evidence:** customer validation or step-up authentication; hold decision |
| Mid R, low C after evidence confirms legit | Allow, clear/close case (needs approval per policy), record as cleared |
| Mid R, low C after evidence denies | Block, escalate, warn customer |
| Low R, high C | Allow; monitor optional; no case or a closed-no-action case |
| Anything blocked by policy or at loop limit | Escalate to analyst with summary and open questions |

**Low-regret principle:** when evidence is uncertain and the harm of waiting is high, prefer reversible, permitted protective actions (temporary hold, step-up) over irreversible ones (permanent block, SAR filing) until confidence improves.

**Two mandatory recommendation snapshots** (required by the submission format):
- `pre_evidence`: the next best action and required approval route recorded **before** any additional evidence is requested.
- `post_evidence`: the updated recommendation and route **after** the evidence response arrives.
If no evidence was needed, record `post_evidence` as unchanged with an explicit "no additional evidence requested" note **[VERIFY exact expected format]**.

### 12.6 Action catalog (all simulated, all via mock APIs)

`allow_transaction`, `block_transaction`, `block_card`, `monitor_account`, `warn_customer`, `request_customer_validation`, `request_step_up_auth`, `request_analyst_info`, `create_case`, `update_case`, `escalate_to_analyst`, `file_sar`, `refund_customer`, `close_case`, `flag_linked_entities`.

Each action definition (in `config/actions.yaml`): required role, reversible?, approval requirement (none / analyst / senior analyst / compliance), preconditions (min `R`, min `C`, required evidence types), and the mock endpoint.

## 13. Policy and Permissions Engine

Deterministic module, **no LLM inside the decision**, but the LLM receives the policy text through GraphRAG to reason and cite.

**Responsibilities**
- Encode policy rules from the provided policy document into `config/policy.yaml` (thresholds, SAR triggers, allowed actions by role, approval routes, evidence-request restrictions). **[VERIFY]** by reading the policy carefully; where the policy is ambiguous, choose the conservative interpretation and document it in `docs/policy_interpretations.md`.
- `check(action, case_state, actor_role) -> {decision: allow|needs_approval|deny, approver, reasons[], policy_refs[]}`.
- Enforce: agent may **recommend** anything sensible but can **execute** only actions its role permits; gated actions go to an approval queue; denied actions are recorded with reason.
- Enforce evidence-request policy (who may be contacted, what may be asked, rate limits).
- Produce the "required approval route" recorded in the answer file.

**Approval flow:** queued action -> UI shows it under Approvals with evidence and rationale -> analyst approves/rejects/edits -> action executes via mock API -> event logged. For automated benchmark runs, a configurable `auto_approve_policy` (default: record route, do not execute gated actions).

## 14. Case Management

**Lifecycle:** `NEW -> INVESTIGATING -> AWAITING_EVIDENCE -> PENDING_APPROVAL -> ACTIONED -> RESOLVED/CLOSED` (plus `ESCALATED`). Status transitions are validated by code.

**Case record contains**
- Metadata: id, trigger, subjects, opened/updated timestamps, current status
- Assessment history: every `R`, `C`, hypothesis set, with timestamps (so uncertainty visibly changes)
- Evidence list (with source query and IDs), findings (with evidence refs)
- Pattern matches (with per-criterion detail)
- Memory used: which past cases and why
- Policy references applied
- Evidence requests: what, why, to whom, response
- Actions: proposed / approved / executed / denied, with approver and simulated flag
- Decision log (chronological event stream)
- SAR draft (if required)

All of the above is persisted to the graph (Section 8) and rendered in the UI from the same source.

**SAR generation:** when policy criteria are met, generate a structured suspicious activity report (subject, activity summary, timeline, amounts, entities involved, pattern, evidence references, basis for suspicion, regulatory reference cited from GraphRAG). Route through the approval path defined by policy. Include it in that case's answer file.

## 15. Case Memory

**Write path (UPDATE_MEMORY):**
- `CaseSummary` node: compact text (typology, key entities, signals, decision, outcome, analyst notes) + embedding.
- Edges: `Case -SIMILAR_TO-> Case`, `Case -MATCHES_PATTERN-> FraudPattern`, and entity-to-case links so "this device appeared in 3 confirmed fraud cases" is a one-hop query.
- Outcomes: confirmed / cleared / pending. Analyst overrides are stored with the reason.

**Read path (RETRIEVE_MEMORY):**
- **Semantic:** vector search over case summaries.
- **Structural:** cases sharing devices, addresses, email domains, or community IDs.
- Combine and rank; present top-k with "why similar."
- Feed a **memory prior** into `R`/`C` (e.g., strong precedent of confirmed fraud raises confidence; a precedent of a cleared case with the same signature raises doubt and may trigger a legitimate-explanation check).

**Bootstrapping:** load all closed months 1-4 cases as memory during ingestion. Compute per-pattern base rates and false-positive signatures from them.

**Learning-loop demo:** show a case where memory changes the outcome (e.g., a signature that looks fraudulent but historically cleared as travel/legit -> agent asks for validation instead of blocking). Also demonstrate updating memory when a benchmark case is resolved in the live demo, with the rule that benchmark evaluation runs use a **frozen** memory snapshot so results are reproducible and leak-free.

## 16. Evidence Request Simulation

- `CustomerSimulator`: deterministic mock responder with configurable scenarios (`recognizes`, `denies`, `no_response`, `step_up_pass`, `step_up_fail`). For benchmark runs, produce **both** the pre-evidence and post-evidence recommendation for each plausible response scenario if the format requires a single fixed response **[VERIFY]**, and record the chosen one explicitly.
- Policy gate checks every request before it is "sent."
- Response is stored as `Evidence` and triggers reassessment. The UI shows the request, the simulated reply, and the changed recommendation side by side.

## 17. Explainability

Every case ends with a structured explanation (JSON + rendered UI/markdown):

1. **Summary:** what happened, in 3-5 sentences.
2. **Determination:** fraud type (or "legitimate/unresolved"), risk, confidence.
3. **Evidence used:** each item with evidence ID, source query, and one-line meaning.
4. **Contradicting or missing evidence.**
5. **Uncertainty statement:** what remains unknown and how it affected the decision.
6. **Why more evidence was requested** (if so): which unknown, why this request, why permitted.
7. **Action rationale:** for each action, the evidence, the policy clause, and the approval route.
8. **Memory influence:** which prior cases mattered and how.
9. **What would change the decision.**

**Anti-hallucination controls:** the explainer may only cite evidence/policy IDs present in state; a validator strips or rejects any statement whose IDs don't exist. Numbers in the explanation come from state, not from the LLM.

## 18. Submission Output: Answer Files

For each of the 20 benchmark cases, generate exactly one answer file **in the format specified by the dataset README [VERIFY]**. Internally we keep a richer model; an `adapters/answer_format.py` serializer maps it to the required schema. Contents per file:

- The case: internal investigation record, evidence, findings, decisions, actions taken
- Confirmation the case was written to the graph (case vertex ID)
- SAR, if policy requires
- Next best action and required approval route: **before** evidence request and **after** evidence received

Include a `validate_answers.py` script that checks every file against the required schema and reports missing fields. Run it in CI and before submission.

## 19. User Interface

**Views**
1. **Case Board:** list/kanban of cases by status; benchmark cases pre-loaded; trigger button ("Investigate").
2. **Investigation View (hero screen):** live streaming of agent steps (timeline), evidence cards, findings, risk and confidence gauges that **update as evidence arrives**, hypotheses with probabilities, and the current recommendation with a visible "Recommendation changed" diff after new evidence.
3. **Graph Explorer:** Cytoscape subgraph of the case neighborhood (customer, cards, devices, addresses, linked confirmed-fraud cases), with rings/communities highlighted and edges labeled with evidence IDs.
4. **Approvals Queue:** pending actions with rationale and evidence, approve/reject/edit.
5. **Memory Panel:** similar past cases, outcomes, why similar; patterns discovered.
6. **Explanation & Case File:** rendered explanation, decision log, SAR draft, export answer file.
7. **Trigger console:** three entry modes: score-driven, customer report (free text), analyst request (natural language chat).

**UX requirements**
- Every claim in the UI links to its evidence card.
- Uncertainty is first-class: show `R`, `C`, "sufficient evidence? yes/no," and what is missing.
- Demo mode: one-click replay of a prepared ambiguous case, with deterministic timing.
- Responsive enough for screen recording at 1080p; clean, dark-or-light theme, readable fonts.

## 20. API Specification (FastAPI)

- `POST /investigate` `{trigger}` -> `{case_id}`; stream steps via `GET /cases/{id}/stream` (SSE)
- `GET /cases`, `GET /cases/{id}` (full record), `GET /cases/{id}/graph` (subgraph JSON)
- `POST /cases/{id}/evidence-response` `{scenario | payload}` (customer simulator/analyst reply)
- `GET /approvals`, `POST /approvals/{action_id}` `{decision, note}`
- `GET /memory/similar?case_id=`
- `POST /benchmark/run` (runs all 20, writes answer files), `GET /benchmark/status`
- `GET /export/{case_id}` (answer file)
- Mock action endpoints under `/mock/*` (block_card, freeze, message_customer, crm_update, refund, close_case), each logging and returning realistic payloads.

## 21. Evaluation and Testing

- **Backtest on months 1-4 closed cases:** run the agent in a leak-free mode (as-of timestamps, memory excluding the case under test and anything later). Report: fraud-type accuracy, confirm-vs-clear precision/recall, action agreement with historical dispositions, and how often the agent asked for evidence on truly ambiguous cases.
- **Calibration:** tune scoring weights and thresholds on months 1-3, validate on month 4. Never tune on the benchmark.
- **Ablations (great for the blog):** graph signals off, memory off, GraphRAG off, to show each component's contribution.
- **Unit tests:** each GSQL query on a small fixture graph; policy engine truth tables; state transitions; answer-file validator.
- **Agent tests:** tool-call schema validation, loop-limit enforcement, "finding without evidence is rejected," "unauthorized action is blocked."
- **Consistency:** run each benchmark case 3 times; report variance in recommendation; pin temperature low and use structured outputs.
- **Performance:** target < 60-90 s per case end to end; cache algorithm results and embeddings.

## 22. Phased Build Plan (with acceptance criteria)

**Phase 0: Discovery (do first, no code beyond profiling)**
- Read README, policy, patterns, regulatory refs, case formats, answer format. Produce `docs/data_profile.md`, `docs/policy_summary.md`, `docs/answer_format.md`, and resolve all **[VERIFY]** items.
- *Accept:* every [VERIFY] item has a documented answer or an explicit assumption.

**Phase 1: Graph foundation**
- Provision TigerGraph, define schema, load data, load historical cases, install baseline queries Q1-Q4.
- *Accept:* row counts match source; sample entity profile and device-sharing queries return correct results for 5 hand-checked entities.

**Phase 2: Analytics and pattern library**
- Q5-Q12, algorithm runs, five documented pattern matchers, discovery experiment.
- *Accept:* pattern matchers separate confirmed-fraud from cleared historical cases better than the raw risk score alone (report the numbers); at least one discovered pattern documented (or an honest negative result).

**Phase 3: GraphRAG + memory**
- Chunk/embed policy and patterns, embed case summaries, retrieval pipeline, context assembler.
- *Accept:* for 10 sample queries, retrieved policy clauses and similar cases are demonstrably relevant; context brief stays within size budget.

**Phase 4: Agent core**
- MCP tools, LangGraph flow, deterministic investigation plan, assessment (`R`, `C`), sufficiency loop, policy engine, mock APIs, customer simulator.
- *Accept:* one full run of an ambiguous case produces pre_evidence and post_evidence recommendations that differ appropriately; loop limits enforced; unauthorized actions blocked.

**Phase 5: Case, explanation, memory writes**
- Case persistence to graph, event log, explanation generator with validator, SAR generator, memory update.
- *Accept:* case reconstructable from graph alone; explanation validator rejects fabricated IDs.

**Phase 6: UI + API**
- Views in Section 19, SSE streaming, approvals.
- *Accept:* full flow demonstrable in the browser with no console access.

**Phase 7: Benchmark run, evaluation, polish**
- Run 20 cases, validate answer files, backtest, ablations, fix top failure modes.
- *Accept:* `validate_answers.py` passes on all 20; evaluation report generated.

**Phase 8: Deliverables**
- Demo video, blog, social post, README, cleanup (Section 25).

**Suggested priority if time runs short (cut from the bottom):** Phases 0-5 are mandatory. In Phase 6, Streamlit is acceptable. Drop in this order: ablations, discovered-pattern experiment polish, graph explorer animation, chat-style analyst mode.

## 23. Agent Operating Rules (for Antigravity)

1. **Read before writing.** Complete Phase 0 and get the real file/column names. Do not invent column names, file names, or policy thresholds. If something is unknown, write it to `docs/open_questions.md` and choose the most conservative assumption.
2. **Small, verifiable steps.** After each module, run its tests and show output before moving on. Prefer many small files over large ones.
3. **Deterministic first.** Anything that can be computed in code (scores, thresholds, permissions, IDs, validation) must be in code, not in a prompt.
4. **Structured outputs only** between LLM and code: JSON validated by Pydantic; retry once with the validation error, then fail safe (escalate).
5. **Never fabricate evidence.** Findings and explanations must cite existing evidence/policy IDs. Enforce with the validator.
6. **No leakage.** Benchmark cases must never contribute to memory or calibration before scoring. All graph queries take `as_of`.
7. **Secrets:** all keys in `.env`, never committed; provide `.env.example`.
8. **Idempotency:** ingestion, benchmark runs, and case creation must be re-runnable without duplicating data.
9. **Log everything** to the case event log with timestamps.
10. **Keep the demo path green.** Maintain a scripted demo scenario that always works; run it after every phase.
11. If a TigerGraph feature (vector search, GraphRAG package, MCP tool) behaves differently from expectation, fall back per Sections 7/10, document it, and continue. Do not stall.

## 24. Demo Script (3-5 minutes)

1. **(0:00-0:30)** Problem framing and architecture in one slide.
2. **(0:30-1:30)** Score-triggered clear-cut case: live steps, graph evidence, ring or device-sharing visual, pattern match, block + escalate, approval, explanation.
3. **(1:30-3:00)** **Ambiguous case:** medium risk, conflicting signals. Show uncertainty gauges, agent chooses to request customer validation, simulated reply arrives, recommendation visibly changes, action executes or queues for approval.
4. **(3:00-3:40)** Memory: similar past cases and how they shifted the decision; SAR draft on a qualifying case.
5. **(3:40-4:20)** Policy controls: unauthorized action blocked, approval flow.
6. **(4:20-5:00)** Benchmark results summary, answer file, what's next.

## 25. Deliverables Checklist

- [ ] Working agent (backend + UI), runnable via documented commands
- [ ] GitHub repo with README (setup, architecture, how to run benchmark), `.env.example`, pinned deps
- [ ] 20 answer files, validated
- [ ] Cases written to the graph (verifiable by query)
- [ ] 3-5 min demo video
- [ ] Technical blog: what we built, architecture, TigerGraph usage, agentic capabilities, learnings, future improvements (include ablation and backtest numbers)
- [ ] X/LinkedIn post tagging @TigerGraphDB with link to blog/demo
- [ ] Savanna auto-stop/auto-start confirmed (if used)

## 26. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Dataset README differs from assumptions | Rework | Phase 0 discovery; adapter layer for answer format |
| No customer key or messy entity resolution | Poor graph quality | Documented derived identity; test with hand-checked entities |
| Flash-tier LLM mis-selects tools or drifts | Wrong investigations | Deterministic core plan; small tool set; structured outputs; validators |
| LLM overconfidence | Bad actions | Code-computed `R`/`C`; policy engine; low-regret rule; escalation on limits |
| Data leakage inflates our metrics | Credibility loss | `as_of` queries; frozen memory; no tuning on benchmark |
| TigerGraph vector/GraphRAG version gaps | Blocked | Fallback to vector attributes + GSQL expansion |
| Slow queries on 590K rows | Bad demo | Precompute algorithms; index; cache; limit hop depth |
| Scope creep | Missed deadline | Phase gates; cut list in Section 22 |
| Ambiguous policy | Wrong routing | Conservative interpretation, documented in `docs/policy_interpretations.md` |

## 27. Repository Structure

```
/
  README.md
  .env.example
  docs/                 data_profile.md, policy_summary.md, answer_format.md,
                        open_questions.md, policy_interpretations.md, architecture.md
  config/               scoring.yaml, policy.yaml, actions.yaml, agent.yaml
  data/                 (gitignored raw) + loaders
  gsql/                 schema.gsql, load_jobs/, queries/, algorithms/
  src/
    graph/              client.py, ingest.py, entity_resolution.py, tools_mcp.py
    rag/                chunk.py, embed.py, retrieve.py, assemble.py
    agent/              state.py, graph.py (LangGraph), nodes/, prompts/, assess.py, decide.py
    policy/             engine.py, rules.py
    cases/              manager.py, sar.py, memory.py, events.py
    mock/               actions_api.py, customer_sim.py
    api/                main.py, routes/, sse.py
    adapters/           answer_format.py
  ui/                   (React app or streamlit_app.py)
  eval/                 backtest.py, ablation.py, benchmark_run.py, validate_answers.py
  tests/
  outputs/answers/      20 answer files
```

## 28. Appendix

### A. Core Pydantic models (sketch)

```python
class Evidence(BaseModel):
    id: str; source_query: str; entities: list[str]; payload: dict; ts: datetime

class Finding(BaseModel):
    id: str; kind: str; statement: str; strength: Literal["weak","moderate","strong"]
    evidence_ids: list[str]  # required, non-empty
    policy_chunk_ids: list[str] = []

class Hypothesis(BaseModel):
    fraud_type: str; probability: float
    supporting: list[str]; contradicting: list[str]

class Assessment(BaseModel):
    risk: float; confidence: float; sufficient: bool
    missing_evidence: list[str]; hypotheses: list[Hypothesis]; ts: datetime

class ProposedAction(BaseModel):
    type: str; target: str; rationale: str; evidence_ids: list[str]
    policy_decision: Literal["allow","needs_approval","deny"] | None
    approver: str | None; simulated: bool = True
```

### B. System prompt skeleton for the investigator LLM

```
ROLE: You are a bank fraud investigator assistant. You reason over graph evidence
provided by tools. You do not compute risk numbers, decide permissions, or invent facts.
RULES:
- Use tools to obtain facts. Cite evidence IDs for every finding.
- Prefer the fewest additional tool calls that resolve the key uncertainty.
- If evidence is insufficient, name the single most valuable missing fact and the
  cheapest policy-permitted way to obtain it.
- Never recommend actions outside the action catalog. The policy engine decides execution.
- Output valid JSON matching the provided schema only.
CONTEXT BRIEF: {assembled GraphRAG brief}
CURRENT STATE: {evidence, assessment, memory hits}
```

### C. Per-case answer file skeleton (map to README format [VERIFY])

```json
{
  "case_id": "...",
  "graph_case_vertex_id": "...",
  "trigger": {},
  "investigation_record": {"evidence": [], "findings": [], "hypotheses": [], "decision_log": []},
  "pre_evidence": {"assessment": {}, "next_best_action": [], "approval_route": "..."},
  "evidence_requested": {"request": {}, "reason": "...", "response": {}},
  "post_evidence": {"assessment": {}, "next_best_action": [], "approval_route": "..."},
  "actions_taken": [],
  "sar": null,
  "explanation": {}
}
```

### D. Config-driven thresholds (starting values, to be calibrated on months 1-4)

- `C_act = 0.75`, `R_high = 70`, `R_low = 30`, `max_investigation_loops = 3`, `max_evidence_requests = 2`, hypothesis margin `>= 0.20`.
- Treat these as placeholders. Replace with values justified by the policy text and the backtest.
