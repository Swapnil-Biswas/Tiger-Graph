"""
Cross-Agent Distributed Episodic & Semantic Memory Bus (src/cases/federated_memory.py)
Provides a unified multi-agent episodic memory store and real-time blackboard working
memory for Fraud, AML, and Cyber sub-agents. Enables cross-domain precedent retrieval,
recency-decayed semantic vector similarity search, and multi-domain empirical priors
with strict temporal isolation.
"""

import time
import math
import uuid
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple


@dataclass
class AgentObservation:
    """
    Structured interim observation published to the case working memory blackboard.
    """
    observation_id: str
    source_agent: str       # "fraud_investigator", "aml_specialist", "cyber_forensics", "consensus_engine"
    observation_type: str   # "STRUCTURING_SIGNAL", "DEVICE_BURST", "ACCOUNT_TAKEOVER", "UNUSUAL_VELOCITY", etc.
    severity: str           # "INFO", "WARNING", "CRITICAL"
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FederatedEpisode:
    """
    Immutable multi-agent case investigation record capturing unified findings across
    Fraud, AML, and Cyber domains along with consensus verdicts and feature embeddings.
    """
    episode_id: str
    case_id: str
    timestamp: str          # Temporal ISO timestamp (e.g. "2024-03-15 10:30:00")
    card_id: Optional[str] = None
    customer_id: Optional[str] = None
    device_profile: Optional[str] = None
    ip_address: Optional[str] = None
    exposure_usd: float = 0.0
    fraud_verdict: str = "review"
    fraud_probability: float = 0.50
    aml_risk_level: str = "LOW"
    aml_score: float = 0.0
    mandatory_sar: bool = False
    cyber_threat_tier: str = "LOW"
    cyber_risk_score: float = 0.0
    consensus_verdict: str = "review"
    consensus_probability: float = 0.50
    consensus_confidence: float = 0.85
    unified_actions: List[str] = field(default_factory=list)
    detected_typologies: List[str] = field(default_factory=list)
    feature_vector: List[float] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two numeric vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


def _parse_timestamp(ts_str: Optional[str]) -> Optional[float]:
    """Attempts to parse standard datetime string into unix timestamp epoch."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts_str.split(".")[0], fmt).timestamp()
        except Exception:
            continue
    return None


class FederatedMemoryBus:
    """
    Central distributed memory bus coordinating multi-agent episodic memory,
    precedent search, working blackboard observations, and cross-domain priors.
    """

    def __init__(self, client: Optional[Any] = None):
        self.client = client
        self._lock = threading.RLock()
        self._episodes: Dict[str, FederatedEpisode] = {}           # episode_id -> FederatedEpisode
        self._case_to_episode: Dict[str, str] = {}                 # case_id -> episode_id
        self._blackboards: Dict[str, List[AgentObservation]] = {}  # case_id -> list of observations

        # Bootstrap memory from closed cases if available
        if self.client and hasattr(self.client, "store") and hasattr(self.client.store, "closed_cases"):
            self._bootstrap_closed_cases(self.client.store.closed_cases)

    def _bootstrap_closed_cases(self, closed_cases: Dict[str, Any]):
        """Bootstraps the episodic memory bus from historical closed cases."""
        for cid, c in closed_cases.items():
            opened_at = str(c.get("opened_at", "2024-01-01 00:00:00"))
            outcome = str(c.get("outcome", "review"))
            exposure = float(c.get("exposure_usd", 0.0))
            pattern = str(c.get("pattern", "UNKNOWN"))
            is_fraud = outcome == "confirmed_fraud"
            fraud_prob = 0.92 if is_fraud else 0.08

            # Infer AML & Cyber characteristics based on historical pattern & exposure
            is_structuring = "structuring" in pattern.lower() or exposure >= 10000.0
            aml_score = 0.85 if is_structuring else (0.40 if exposure > 3000 else 0.05)
            aml_risk = "HIGH" if aml_score > 0.70 else ("MEDIUM" if aml_score > 0.30 else "LOW")
            mandatory_sar = is_structuring or c.get("report_filed", False)

            is_bot = "burst" in pattern.lower() or "bot" in pattern.lower()
            cyber_score = 0.80 if is_bot else (0.35 if is_fraud else 0.05)
            cyber_tier = "CRITICAL" if cyber_score > 0.75 else ("ELEVATED" if cyber_score > 0.30 else "LOW")

            typologies = []
            if is_structuring:
                typologies.append("STRUCTURING_BSA_THRESHOLD")
            if is_bot:
                typologies.append("BOT_VELOCITY_BURST")
            if pattern != "UNKNOWN":
                typologies.append(pattern.upper())

            conn_cards_raw = c.get("connected_card_ids")
            card_count = len(conn_cards_raw) if isinstance(conn_cards_raw, (list, set, tuple)) else 1

            feature_vec = self.build_feature_vector(
                fraud_prob=fraud_prob,
                exposure_usd=exposure,
                aml_score=aml_score,
                cyber_score=cyber_score,
                mandatory_sar=mandatory_sar,
                connected_card_count=card_count,
                has_structuring=is_structuring,
                has_bot_burst=is_bot,
            )

            actions_raw = c.get("actions_taken")
            actions_list = list(actions_raw) if isinstance(actions_raw, (list, set, tuple)) else []
            notes_raw = c.get("analyst_notes")
            summary_str = str(notes_raw) if notes_raw and not (isinstance(notes_raw, float) and math.isnan(notes_raw)) else f"Historical closed case {cid}"

            ep = FederatedEpisode(
                episode_id=f"EP-{cid}",
                case_id=cid,
                timestamp=opened_at,
                card_id=c.get("card_id"),
                customer_id=c.get("customer_id"),
                exposure_usd=exposure,
                fraud_verdict="fraud" if is_fraud else "legitimate",
                fraud_probability=fraud_prob,
                aml_risk_level=aml_risk,
                aml_score=aml_score,
                mandatory_sar=mandatory_sar,
                cyber_threat_tier=cyber_tier,
                cyber_risk_score=cyber_score,
                consensus_verdict="fraud" if is_fraud else "legitimate",
                consensus_probability=fraud_prob,
                consensus_confidence=0.90,
                unified_actions=actions_list,
                detected_typologies=typologies,
                feature_vector=feature_vec,
                summary=summary_str,
            )
            self._episodes[ep.episode_id] = ep
            self._case_to_episode[cid] = ep.episode_id

    @staticmethod
    def build_feature_vector(
        fraud_prob: float,
        exposure_usd: float,
        aml_score: float,
        cyber_score: float,
        mandatory_sar: bool,
        connected_card_count: int = 1,
        has_structuring: bool = False,
        has_bot_burst: bool = False,
    ) -> List[float]:
        """Constructs an 8-dimensional normalized embedding vector representing the multi-agent incident."""
        return [
            round(float(fraud_prob), 4),
            round(min(1.0, float(exposure_usd) / 10000.0), 4),
            round(float(aml_score), 4),
            round(float(cyber_score), 4),
            1.0 if mandatory_sar else 0.0,
            round(min(1.0, float(connected_card_count) / 5.0), 4),
            1.0 if has_structuring else 0.0,
            1.0 if has_bot_burst else 0.0,
        ]

    # -------------------------------------------------------------------------
    # Blackboard Working Memory
    # -------------------------------------------------------------------------

    def publish_observation(
        self,
        case_id: str,
        source_agent: str,
        observation_type: str,
        severity: str,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> AgentObservation:
        """Publishes an interim domain observation to the shared working blackboard."""
        with self._lock:
            obs = AgentObservation(
                observation_id=f"obs_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}",
                source_agent=source_agent,
                observation_type=observation_type,
                severity=severity.upper(),
                summary=summary,
                data=data or {},
                timestamp=time.time(),
            )
            if case_id not in self._blackboards:
                self._blackboards[case_id] = []
            self._blackboards[case_id].append(obs)
            return obs

    def get_blackboard(self, case_id: str) -> List[AgentObservation]:
        """Retrieves all working observations for an active case."""
        with self._lock:
            return list(self._blackboards.get(case_id, []))

    def clear_blackboard(self, case_id: str):
        """Clears blackboard observations for a closed or completed case."""
        with self._lock:
            self._blackboards.pop(case_id, None)

    # -------------------------------------------------------------------------
    # Episodic Memory Ingestion & Query
    # -------------------------------------------------------------------------

    def commit_episode(self, answer: Dict[str, Any]) -> FederatedEpisode:
        """
        Commits a completed multi-agent investigation into the episodic memory store.
        """
        case_dict = answer.get("case", {})
        case_id = str(case_dict.get("case_id", answer.get("case_id", "UNKNOWN")))
        card_id = case_dict.get("card_id")
        customer_id = case_dict.get("customer_id")
        opened_at = str(case_dict.get("opened_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        exposure = float(case_dict.get("exposure_usd", 0.0))

        fraud_verdict = str(case_dict.get("verdict", "review"))
        fraud_prob = float(case_dict.get("fraud_probability", 0.50))

        aml_data = answer.get("aml_specialist", {})
        aml_risk = aml_data.get("risk_level", "LOW")
        aml_score = float(aml_data.get("aml_score", 0.0))
        mandatory_sar = bool(aml_data.get("mandatory_sar", False) or answer.get("sar", {}).get("file", False))

        cyber_data = answer.get("cyber_forensics", {})
        cyber_tier = cyber_data.get("threat_tier", "LOW")
        cyber_score = float(cyber_data.get("cyber_risk_score", 0.0))

        consensus_data = answer.get("federated_consensus", {})
        consensus_verdict = consensus_data.get("consensus_verdict", fraud_verdict)
        consensus_prob = float(consensus_data.get("consensus_probability", fraud_prob))
        consensus_conf = float(consensus_data.get("consensus_confidence", 0.85))

        unified_actions = [
            a.get("action", a) if isinstance(a, dict) else a
            for a in answer.get("next_best_actions", {}).get("final", [])
        ]
        typologies = list(set(
            aml_data.get("detected_typologies", []) +
            cyber_data.get("detected_anomalies", []) +
            ([case_dict.get("pattern")] if case_dict.get("pattern") else [])
        ))

        has_struct = any("STRUCTURING" in t for t in typologies)
        has_burst = any("BURST" in t or "BOT" in t for t in typologies)
        conn_cards_raw = case_dict.get("connected_card_ids")
        if isinstance(conn_cards_raw, (list, set, tuple)):
            conn_cards = len(conn_cards_raw)
        else:
            conn_cards = 1 if card_id else 0

        feature_vec = self.build_feature_vector(
            fraud_prob=consensus_prob,
            exposure_usd=exposure,
            aml_score=aml_score,
            cyber_score=cyber_score,
            mandatory_sar=mandatory_sar,
            connected_card_count=conn_cards,
            has_structuring=has_struct,
            has_bot_burst=has_burst,
        )

        with self._lock:
            episode_id = f"EP-{case_id}"
            ep = FederatedEpisode(
                episode_id=episode_id,
                case_id=case_id,
                timestamp=opened_at,
                card_id=card_id,
                customer_id=customer_id,
                device_profile=case_dict.get("device_profile"),
                ip_address=case_dict.get("ip_address"),
                exposure_usd=exposure,
                fraud_verdict=fraud_verdict,
                fraud_probability=fraud_prob,
                aml_risk_level=aml_risk,
                aml_score=aml_score,
                mandatory_sar=mandatory_sar,
                cyber_threat_tier=cyber_tier,
                cyber_risk_score=cyber_score,
                consensus_verdict=consensus_verdict,
                consensus_probability=consensus_prob,
                consensus_confidence=consensus_conf,
                unified_actions=unified_actions,
                detected_typologies=typologies,
                feature_vector=feature_vec,
                summary=case_dict.get("summary", ""),
            )
            self._episodes[episode_id] = ep
            self._case_to_episode[case_id] = episode_id
            return ep

    def get_episode(self, case_id: str) -> Optional[FederatedEpisode]:
        """Retrieves a committed episode by case_id."""
        with self._lock:
            ep_id = self._case_to_episode.get(case_id)
            return self._episodes.get(ep_id) if ep_id else None

    # -------------------------------------------------------------------------
    # Precedent Search & Similarity Ranking
    # -------------------------------------------------------------------------

    def query_cross_agent_precedents(
        self,
        query_vector: Optional[List[float]] = None,
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        device_profile: Optional[str] = None,
        domain_filter: str = "ALL",  # "ALL", "FRAUD", "AML", "CYBER"
        as_of: Optional[str] = None,
        top_k: int = 5,
        half_life_days: float = 120.0,
    ) -> List[Dict[str, Any]]:
        """
        Searches cross-agent episodic memory for similar precedents with strict temporal isolation,
        vector cosine similarity, entity matching bonuses, and exponential recency decay.
        """
        as_of_epoch = _parse_timestamp(as_of) if as_of else None
        results = []

        with self._lock:
            for ep in self._episodes.values():
                # Strict temporal isolation check
                if as_of:
                    ep_epoch = _parse_timestamp(ep.timestamp)
                    if ep_epoch and as_of_epoch and ep_epoch >= as_of_epoch:
                        continue
                    elif str(ep.timestamp) >= str(as_of):
                        continue

                # Domain filtering
                domain_upper = domain_filter.upper()
                if domain_upper == "AML" and ep.aml_risk_level == "LOW" and not ep.mandatory_sar:
                    continue
                elif domain_upper == "CYBER" and ep.cyber_threat_tier == "LOW":
                    continue
                elif domain_upper == "FRAUD" and ep.fraud_verdict != "fraud":
                    continue

                # Calculate base vector similarity
                if query_vector and ep.feature_vector:
                    sim_cos = _compute_cosine_similarity(query_vector, ep.feature_vector)
                else:
                    sim_cos = 0.50

                # Recency decay calculation
                recency_weight = 1.0
                if as_of_epoch and ep.timestamp:
                    ep_epoch = _parse_timestamp(ep.timestamp)
                    if ep_epoch and ep_epoch < as_of_epoch:
                        delta_days = (as_of_epoch - ep_epoch) / 86400.0
                        recency_weight = math.exp(-math.log(2) * delta_days / max(1.0, half_life_days))

                # Entity linkage bonus
                match_reasons = []
                entity_bonus = 0.0
                if card_id and ep.card_id == card_id:
                    entity_bonus += 0.30
                    match_reasons.append(f"Direct card match: {card_id}")
                if customer_id and ep.customer_id == customer_id:
                    entity_bonus += 0.25
                    match_reasons.append(f"Direct customer match: {customer_id}")
                if device_profile and ep.device_profile and ep.device_profile == device_profile:
                    entity_bonus += 0.20
                    match_reasons.append("Shared device profile match")

                # Cross-domain flags for explainability
                domain_citations = []
                if ep.mandatory_sar:
                    domain_citations.append("AML Mandatory FinCEN SAR Filed")
                if ep.cyber_threat_tier in ["ELEVATED", "CRITICAL"]:
                    domain_citations.append(f"Cyber Forensics {ep.cyber_threat_tier} Hardware Threat")
                if ep.fraud_verdict == "fraud":
                    domain_citations.append("Confirmed Fraud Incident")

                composite_score = round(min(1.0, 0.60 * sim_cos + 0.20 * recency_weight + entity_bonus), 4)

                results.append({
                    "episode_id": ep.episode_id,
                    "case_id": ep.case_id,
                    "timestamp": ep.timestamp,
                    "similarity_score": composite_score,
                    "consensus_verdict": ep.consensus_verdict,
                    "consensus_probability": ep.consensus_probability,
                    "aml_risk_level": ep.aml_risk_level,
                    "cyber_threat_tier": ep.cyber_threat_tier,
                    "mandatory_sar": ep.mandatory_sar,
                    "unified_actions": ep.unified_actions,
                    "match_reasons": match_reasons or ["Topological feature proximity"],
                    "domain_citations": domain_citations,
                })

        # Sort descending by similarity score
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    # -------------------------------------------------------------------------
    # Multi-Domain Empirical Prior Calculation
    # -------------------------------------------------------------------------

    def get_cross_domain_prior(
        self,
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        device_profile: Optional[str] = None,
        as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes a unified multi-domain empirical risk prior combining historical
        precedents across Fraud, AML, and Cyber sub-agent domains.
        """
        matching_episodes = []
        with self._lock:
            for ep in self._episodes.values():
                if as_of and str(ep.timestamp) >= str(as_of):
                    continue
                match = (
                    (card_id and ep.card_id == card_id) or
                    (customer_id and ep.customer_id == customer_id) or
                    (device_profile and ep.device_profile == device_profile)
                )
                if match:
                    matching_episodes.append(ep)

        total_matches = len(matching_episodes)
        fraud_cases = sum(1 for e in matching_episodes if e.consensus_verdict == "fraud")
        aml_sars = sum(1 for e in matching_episodes if e.mandatory_sar)
        cyber_threats = sum(1 for e in matching_episodes if e.cyber_threat_tier in ["ELEVATED", "CRITICAL"])

        # Prior risk adjustment delta (-10.0 to +15.0)
        risk_delta = 0.0
        if total_matches > 0:
            risk_delta += (fraud_cases / total_matches) * 10.0
            if aml_sars > 0:
                risk_delta += 4.0
            if cyber_threats > 0:
                risk_delta += 3.0
        risk_delta = round(max(-10.0, min(15.0, risk_delta)), 1)

        return {
            "has_federated_history": total_matches > 0,
            "total_matched_episodes": total_matches,
            "fraud_incidents_count": fraud_cases,
            "aml_sar_count": aml_sars,
            "cyber_threat_count": cyber_threats,
            "composite_prior_risk_delta": risk_delta,
            "cited_episode_ids": [e.episode_id for e in matching_episodes[:4]],
        }

    # -------------------------------------------------------------------------
    # State Serialization
    # -------------------------------------------------------------------------

    def export_memory(self) -> Dict[str, Any]:
        """Exports all episodic records for persistence or auditing."""
        with self._lock:
            return {
                "total_episodes": len(self._episodes),
                "episodes": [ep.to_dict() for ep in self._episodes.values()],
            }

    def import_memory(self, data: Dict[str, Any]):
        """Imports episodic records into the memory bus."""
        with self._lock:
            for ed in data.get("episodes", []):
                ep = FederatedEpisode(**ed)
                self._episodes[ep.episode_id] = ep
                self._case_to_episode[ep.case_id] = ep.episode_id
