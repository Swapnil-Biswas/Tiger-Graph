# Significant Architectural & Design Decisions

This document records architectural, algorithmic, and policy decisions made during the lifecycle of the TigerGraph Agentic Fraud Investigator project.

---

## 1. Derived Identity Resolution & Customer Keying
- **Decision:** Derived customer ID as `C<card1>` and tracked individual card instruments with suffixes `-K1`, `-K2` based on card sequence within each customer entity.
- **Why:** The raw dataset lacked an explicit `customer_id` column. Using `card1` as the root cluster anchor ensures deterministic clustering while preserving multi-card mapping without data leakage.

## 2. Dual Graph Client (Embedded In-Memory Index + Remote GSQL)
- **Decision:** Implemented a unified `GraphClient` supporting `GRAPH_MODE=embedded` and `GRAPH_MODE=tigergraph`. Embedded mode loads the 590,742 transactions, 13,770 cards, and 5,565 closed cases into memory in ~1.0s with indexed hash-maps.
- **Why:** Savanna cloud instances can experience latency or connection rate-limits. The embedded engine runs all 12 GSQL queries in sub-milliseconds locally, while remaining 100% compatible with remote TigerGraph endpoints.

## 3. Decoupled Cognitive Architecture: Reasoning vs Action Airbag
- **Decision:** Decoupled LLM reasoning from action authorization. LLM and GraphRAG propose assessments and explanations, but all actual actions (`BLOCK_CARD`, `FILE_REPORT`, etc.) and approval routing (`auto`, `L1`, `L2`) are strictly enforced by the deterministic Python `PolicyEngine` (Rules R1–R10).
- **Why:** Prevents catastrophic hallucinations, regulatory non-compliance, and unauthorized card portfolio blocks.

## 4. Leak-Free Episodic Memory (GraphRAG)
- **Decision:** GraphRAG memory search strictly queries historical closed cases from months 1–4, filtering dynamically on `as_of` timestamps to prevent forward-looking data leakage.
- **Why:** Guarantees empirical validity of backtesting and benchmark investigations.

## 5. Standardized 14 Actions & 3 Approval Routes
- **Decision:** Standardized on exactly 14 actions (`ALLOW_TRANSACTION`, `DECLINE_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `BLOCK_CARD`, `BLOCK_ALL_CARDS`, `GENERATE_REPORT`, `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD`) across `auto`, `L1` (team lead), and `L2` (fraud manager) routes.
- **Why:** Fully aligns with enterprise banking policy and auditability requirements.
