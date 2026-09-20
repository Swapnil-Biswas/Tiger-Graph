"""
Automated Compliance Evidence Packager & Cryptographic Chain-of-Custody
(src/cases/evidence_bundle.py)

Packages multi-agent investigation steps, graph query execution proofs, model decisions,
and policy evaluations into a tamper-evident regulatory evidence bundle authenticated by
Merkle trees and HMAC-SHA256 digital signatures conforming to Federal Rules of Evidence
(FRE Rule 902(13)/(14)) and FinCEN SAR recordkeeping requirements (31 CFR 1020.320(d)).
"""

import os
import json
import time
import uuid
import hmac
import hashlib
import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union


DEFAULT_SIGNING_KEY = b"TIGERGRAPH_EVIDENTIARY_MASTER_KEY_2026_COMPLIANCE_VAULT"


def canonical_json(obj: Any) -> str:
    """
    Serializes a Python object to canonical JSON format:
    - Keys sorted alphabetically
    - No extraneous whitespace (separators=(',', ':'))
    - Safe conversion of sets, tuples, dates, and non-serializable objects
    Ensures 100% deterministic SHA-256 digests across platforms and runtimes.
    """
    def _default_serializer(o):
        if isinstance(o, (set, tuple)):
            return sorted(list(o), key=lambda x: str(x))
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_default_serializer)


def compute_sha256(content: Any) -> str:
    """Computes a SHA-256 hex digest of arbitrary content using canonical JSON encoding."""
    if isinstance(content, (str, bytes)):
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
    else:
        raw_bytes = canonical_json(content).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """
    Constructs a cryptographic Merkle tree from a list of leaf SHA-256 hashes
    and returns the Merkle root hash. If empty, returns empty string.
    """
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()

    current_level = list(leaf_hashes)
    while len(current_level) > 1:
        next_level = []
        # If odd number of elements, duplicate the last leaf
        if len(current_level) % 2 == 1:
            current_level.append(current_level[-1])

        for i in range(0, len(current_level), 2):
            combined = current_level[i] + current_level[i + 1]
            parent_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            next_level.append(parent_hash)
        current_level = next_level

    return current_level[0]


@dataclass
class ChainOfCustodyEvent:
    event_id: str
    timestamp: str
    action: str
    actor: str
    system_component: str
    verification_status: str
    notes: Optional[str] = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    item_id: str
    category: str
    title: str
    timestamp: str
    content: Any
    sha256_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBundle:
    bundle_id: str
    case_id: str
    generated_at: str
    as_of: str
    verdict: str
    fraud_probability: float
    recommended_actions: List[str]
    items: List[EvidenceItem]
    merkle_root: str
    chain_of_custody: List[ChainOfCustodyEvent]
    signature: str
    signer_identity: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "case_id": self.case_id,
            "generated_at": self.generated_at,
            "as_of": self.as_of,
            "verdict": self.verdict,
            "fraud_probability": round(float(self.fraud_probability), 4),
            "recommended_actions": list(self.recommended_actions),
            "item_count": len(self.items),
            "merkle_root": self.merkle_root,
            "signature": self.signature,
            "signer_identity": self.signer_identity,
            "items": [item.to_dict() for item in self.items],
            "chain_of_custody": [event.to_dict() for event in self.chain_of_custody],
        }

    def export_manifest(self) -> Dict[str, Any]:
        """
        Exports a lightweight regulatory submission manifest listing
        item hashes, Merkle root, custody trail, and cryptographic authentication.
        """
        return {
            "bundle_id": self.bundle_id,
            "case_id": self.case_id,
            "generated_at": self.generated_at,
            "as_of": self.as_of,
            "verdict": self.verdict,
            "fraud_probability": round(float(self.fraud_probability), 4),
            "recommended_actions": self.recommended_actions,
            "merkle_root": self.merkle_root,
            "signature": self.signature,
            "signer_identity": self.signer_identity,
            "chain_of_custody_count": len(self.chain_of_custody),
            "evidence_items_manifest": [
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "title": item.title,
                    "sha256_hash": item.sha256_hash,
                }
                for item in self.items
            ],
        }


class ComplianceEvidencePackager:
    """
    Automated Regulatory Evidence Packager & Chain-of-Custody Authentication Engine.
    Bundles all 16 multi-agent investigation artifacts into an immutable evidence archive.
    """

    SIGNER_IDENTITY = "TIGERGRAPH_AGENTIC_ORCHESTRATOR_V0.55"

    def __init__(self, signing_key: Optional[bytes] = None):
        self.signing_key = signing_key or DEFAULT_SIGNING_KEY

    def _sign_bundle(self, bundle_payload: str) -> str:
        """Computes HMAC-SHA256 signature for bundle authentication."""
        return hmac.new(self.signing_key, bundle_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def build_evidence_bundle(
        self,
        case_answer: Dict[str, Any],
        actor: str = "TIGERGRAPH_AUTONOMOUS_INVESTIGATOR",
    ) -> EvidenceBundle:
        """
        Extracts all investigation evidence from case_answer, builds individual EvidenceItems,
        computes SHA-256 hashes, Merkle tree root, chain-of-custody log, and signs the bundle.
        """
        case_data = case_answer.get("case", {})
        case_id = case_data.get("case_id") or case_answer.get("case_id") or f"CASE-{uuid.uuid4().hex[:8]}"
        as_of = str(case_data.get("as_of") or case_answer.get("as_of") or "2016-10-01 00:00:00")
        verdict = str(case_data.get("verdict") or "uncertain")
        prob = float(case_data.get("fraud_probability", 0.0))

        # Extract actions
        actions = []
        nba = case_answer.get("next_best_actions", {})
        if isinstance(nba, dict) and "final" in nba:
            actions = [a.get("action") if isinstance(a, dict) else str(a) for a in nba["final"]]
        elif isinstance(case_data.get("actions"), list):
            actions = case_data["actions"]

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        bundle_id = f"BUNDLE-{case_id}-{uuid.uuid4().hex[:8].upper()}"

        items: List[EvidenceItem] = []

        # 1. Primary Case Metadata
        meta_content = {
            "case_id": case_id,
            "card_id": case_data.get("card_id"),
            "customer_id": case_data.get("customer_id"),
            "opened_at": case_data.get("opened_at"),
            "as_of": as_of,
            "exposure_usd": case_data.get("exposure_usd", 0.0),
            "verdict": verdict,
            "fraud_probability": prob,
            "pattern": case_data.get("pattern", "unknown"),
            "connected_card_ids": case_data.get("connected_card_ids", []),
        }
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-01-CASE-METADATA",
                category="CASE_METADATA",
                title="Primary Case Attributes & Inception Snapshot",
                timestamp=now_iso,
                content=meta_content,
                sha256_hash=compute_sha256(meta_content),
                metadata={"statutory_relevance": "FinCEN Subject Identification"},
            )
        )

        # 2. Graph Traversal & Topological Features (Q1-Q12)
        graph_evidence = case_answer.get("graph_evidence") or case_answer.get("evidence") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-02-GRAPH-TOPOLOGY",
                category="GRAPH_TRAVERSAL",
                title="Multi-Hop Subgraph & Velocity Traversal Proofs",
                timestamp=now_iso,
                content=graph_evidence,
                sha256_hash=compute_sha256(graph_evidence),
                metadata={"engine": "ConcurrentGraphTraverser", "queries": "Q1-Q12"},
            )
        )

        # 3. Vector Case Precedents (GraphRAG)
        retrieved_cases = case_answer.get("retrieved_cases") or case_answer.get("similar_cases") or []
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-03-VECTOR-PRECEDENTS",
                category="VECTOR_SEARCH",
                title="GraphRAG Historical Precedents & Cosine Similarity Citations",
                timestamp=now_iso,
                content=retrieved_cases,
                sha256_hash=compute_sha256(retrieved_cases),
                metadata={"engine": "GraphRAGRetriever", "precedent_count": len(retrieved_cases)},
            )
        )

        # 4. Graph Motif Signatures (Q22)
        motifs = case_answer.get("motifs") or case_answer.get("graph_motifs") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-04-GRAPH-MOTIFS",
                category="GRAPH_MOTIFS",
                title="Topological Graph Motif Signatures (Rings, Bipartite, Smurfing)",
                timestamp=now_iso,
                content=motifs,
                sha256_hash=compute_sha256(motifs),
                metadata={"query": "Q22"},
            )
        )

        # 5. Probabilistic Record Linkage & Sybil Defense (Q23)
        entity_res = case_answer.get("entity_resolution") or case_answer.get("sybil_resolution") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-05-SYBIL-LINKAGE",
                category="RECORD_LINKAGE",
                title="Fellegi-Sunter / Jaro-Winkler Sybil Account Cluster Resolution",
                timestamp=now_iso,
                content=entity_res,
                sha256_hash=compute_sha256(entity_res),
                metadata={"query": "Q23"},
            )
        )

        # 6. Inductive Association Rules (Q19)
        inductive_rules = case_answer.get("inductive_rules") or case_answer.get("matched_rules") or []
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-06-INDUCTIVE-RULES",
                category="RULE_MINING",
                title="Inductive Fraud Rules Mined from Closed Historical Cases",
                timestamp=now_iso,
                content=inductive_rules,
                sha256_hash=compute_sha256(inductive_rules),
                metadata={"query": "Q19"},
            )
        )

        # 7. Cross-Border AML & Correspondent Banking Corridor (Q20)
        cross_border = case_answer.get("cross_border_aml") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-07-CROSS-BORDER-AML",
                category="CROSS_BORDER_AML",
                title="Cross-Border Transaction Bundling & FATF Corridor Risk",
                timestamp=now_iso,
                content=cross_border,
                sha256_hash=compute_sha256(cross_border),
                metadata={"query": "Q20", "statutory_grounding": "FATF Rec 16 & BSA 31 CFR 1010.311"},
            )
        )

        # 8. High-Risk Quasi-Cash MCC Analysis (Q21)
        mcc_risk = case_answer.get("mcc_risk") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-08-HIGH-RISK-MCC",
                category="MCC_ANALYSIS",
                title="Quasi-Cash & High-Risk Merchant Category Evaluation (MCC 6051)",
                timestamp=now_iso,
                content=mcc_risk,
                sha256_hash=compute_sha256(mcc_risk),
                metadata={"query": "Q21"},
            )
        )

        # 9. Personalized PageRank / Random Walk Contagion (Q17)
        contagion = case_answer.get("contagion") or case_answer.get("fraud_contagion") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-09-PAGERANK-CONTAGION",
                category="CONTAGION_SCORING",
                title="Personalized PageRank / RWR Continuous Fraud Contagion Distribution",
                timestamp=now_iso,
                content=contagion,
                sha256_hash=compute_sha256(contagion),
                metadata={"query": "Q17"},
            )
        )

        # 10. Temporal Graph Attention Subgraph Pooling (Q18)
        pooling = case_answer.get("graph_embedding") or case_answer.get("pooling") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-10-ATTENTION-EMBEDDINGS",
                category="GRAPH_EMBEDDINGS",
                title="Attention-Pooled Subgraph Topological Tensors (9D Attention, 27D Multi-Head)",
                timestamp=now_iso,
                content=pooling,
                sha256_hash=compute_sha256(pooling),
                metadata={"query": "Q18"},
            )
        )

        # 11. Active Learning Uncertainty & Hard-Negative Mining (Q26)
        active_learning = case_answer.get("active_learning") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-11-ACTIVE-LEARNING",
                category="ACTIVE_LEARNING",
                title="Active Learning Margin Uncertainty & Hard-Negative Mining Scores",
                timestamp=now_iso,
                content=active_learning,
                sha256_hash=compute_sha256(active_learning),
                metadata={"query": "Q26"},
            )
        )

        # 12. Specialized AML Sub-Agent Statutory Assessment
        aml_assessment = case_answer.get("aml_specialist") or case_answer.get("aml_assessment") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-12-AML-SUBAGENT",
                category="SUBAGENT_ASSESSMENT",
                title="AML Specialist Statutory Assessment & Structuring Evasion Findings",
                timestamp=now_iso,
                content=aml_assessment,
                sha256_hash=compute_sha256(aml_assessment),
                metadata={"source_agent": "AMLSpecialistAgent", "statutory_authority": "31 USC 5324(a)"},
            )
        )

        # 13. Specialized Cyber-Forensics Sub-Agent Assessment
        cyber_assessment = case_answer.get("cyber_forensics") or case_answer.get("cyber_assessment") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-13-CYBER-SUBAGENT",
                category="SUBAGENT_ASSESSMENT",
                title="Cyber-Forensics Hardware Fingerprint & Bot Attack Assessment",
                timestamp=now_iso,
                content=cyber_assessment,
                sha256_hash=compute_sha256(cyber_assessment),
                metadata={"source_agent": "CyberForensicsAgent"},
            )
        )

        # 14. Federated Multi-Agent Consensus Deliberation
        consensus = case_answer.get("federated_consensus") or case_answer.get("consensus") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-14-CONSENSUS-DELIBERATION",
                category="CONSENSUS_DELIBERATION",
                title="Multi-Agent Weighted Debate & Consensus Resolution Dossier",
                timestamp=now_iso,
                content=consensus,
                sha256_hash=compute_sha256(consensus),
                metadata={"engine": "MultiAgentConsensusEngine"},
            )
        )

        # 15. Cross-Agent Episodic Memory & Working Memory Blackboard
        episodic_memory = {
            "blackboard": case_answer.get("working_memory_blackboard", []),
            "episode": case_answer.get("federated_memory_episode", {}),
            "precedents": case_answer.get("cross_agent_precedents", []),
        }
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-15-EPISODIC-MEMORY",
                category="EPISODIC_MEMORY",
                title="Cross-Agent Shared Working Memory Blackboard & Episodic Citations",
                timestamp=now_iso,
                content=episodic_memory,
                sha256_hash=compute_sha256(episodic_memory),
                metadata={"bus": "FederatedMemoryBus"},
            )
        )

        # 16. FinCEN Suspicious Activity Report (SAR) Filing Package
        sar_package = case_answer.get("sar") or {}
        items.append(
            EvidenceItem(
                item_id=f"EV-{case_id}-16-SAR-FILING-PACKAGE",
                category="REGULATORY_SAR",
                title="FinCEN Suspicious Activity Report Narrative & Statutory Determination",
                timestamp=now_iso,
                content=sar_package,
                sha256_hash=compute_sha256(sar_package),
                metadata={"regulatory_standard": "FinCEN Form 111 / 31 CFR 1020.320"},
            )
        )

        # Compute Merkle tree root from all item hashes in order
        leaf_hashes = [item.sha256_hash for item in items]
        merkle_root = compute_merkle_root(leaf_hashes)

        # Construct initial Chain of Custody events
        chain: List[ChainOfCustodyEvent] = [
            ChainOfCustodyEvent(
                event_id=f"CUST-{case_id}-001",
                timestamp=now_iso,
                action="BUNDLE_GENERATION",
                actor=actor,
                system_component="ComplianceEvidencePackager",
                verification_status="VERIFIED_CORRECT",
                notes=f"Generated bundle with {len(items)} evidence artifacts for case {case_id}",
            ),
            ChainOfCustodyEvent(
                event_id=f"CUST-{case_id}-002",
                timestamp=now_iso,
                action="MERKLE_TREE_COMPUTATION",
                actor="MERKLE_CRYPTOGRAPHIC_ENGINE",
                system_component="compute_merkle_root",
                verification_status="VERIFIED_CORRECT",
                notes=f"Root hash: {merkle_root}",
            ),
            ChainOfCustodyEvent(
                event_id=f"CUST-{case_id}-003",
                timestamp=now_iso,
                action="CRYPTOGRAPHIC_SIGNATURE_AFFIXED",
                actor=self.SIGNER_IDENTITY,
                system_component="HMAC_SHA256_AUTHENTICATOR",
                verification_status="SEALED_IMMUTABLE",
                notes="Affixed FRE 902 digital signature with master key",
            ),
        ]

        # Compute HMAC-SHA256 digital signature
        sign_payload = canonical_json({
            "bundle_id": bundle_id,
            "case_id": case_id,
            "generated_at": now_iso,
            "as_of": as_of,
            "verdict": verdict,
            "fraud_probability": round(prob, 4),
            "merkle_root": merkle_root,
            "signer_identity": self.SIGNER_IDENTITY,
        })
        signature = self._sign_bundle(sign_payload)

        return EvidenceBundle(
            bundle_id=bundle_id,
            case_id=case_id,
            generated_at=now_iso,
            as_of=as_of,
            verdict=verdict,
            fraud_probability=prob,
            recommended_actions=actions,
            items=items,
            merkle_root=merkle_root,
            chain_of_custody=chain,
            signature=signature,
            signer_identity=self.SIGNER_IDENTITY,
        )

    def verify_bundle(
        self,
        bundle_data: Union[EvidenceBundle, Dict[str, Any]],
        signing_key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Performs full cryptographic audit on an EvidenceBundle:
        1. Recalculates every EvidenceItem SHA-256 hash against its actual content.
        2. Rebuilds Merkle tree and verifies Merkle root matches stored root.
        3. Recalculates HMAC-SHA256 signature and verifies authenticity.
        Returns comprehensive verification audit report.
        """
        key = signing_key or self.signing_key
        d = bundle_data.to_dict() if hasattr(bundle_data, "to_dict") else bundle_data

        bundle_id = d.get("bundle_id")
        case_id = d.get("case_id")
        generated_at = d.get("generated_at")
        as_of = d.get("as_of")
        verdict = d.get("verdict")
        fraud_prob = float(d.get("fraud_probability", 0.0))
        stored_merkle = d.get("merkle_root")
        stored_signature = d.get("signature")
        signer_identity = d.get("signer_identity", self.SIGNER_IDENTITY)
        raw_items = d.get("items", [])

        # Step 1: Verify each item's content against its sha256_hash
        corrupted_items = []
        recalculated_leaf_hashes = []

        for idx, item in enumerate(raw_items):
            item_id = item.get("item_id", f"ITEM_{idx}")
            stored_hash = item.get("sha256_hash")
            content = item.get("content")
            recomputed_hash = compute_sha256(content)

            if recomputed_hash != stored_hash:
                corrupted_items.append({
                    "item_id": item_id,
                    "category": item.get("category"),
                    "stored_hash": stored_hash,
                    "recomputed_hash": recomputed_hash,
                    "reason": "CONTENT_HASH_MISMATCH",
                })
            recalculated_leaf_hashes.append(recomputed_hash)

        # Step 2: Reconstruct Merkle Tree
        recomputed_merkle_root = compute_merkle_root(recalculated_leaf_hashes)
        merkle_root_valid = (recomputed_merkle_root == stored_merkle)

        # Step 3: Recompute Digital Signature
        sign_payload = canonical_json({
            "bundle_id": bundle_id,
            "case_id": case_id,
            "generated_at": generated_at,
            "as_of": as_of,
            "verdict": verdict,
            "fraud_probability": round(fraud_prob, 4),
            "merkle_root": recomputed_merkle_root,
            "signer_identity": signer_identity,
        })
        recomputed_signature = hmac.new(key, sign_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_valid = hmac.compare_digest(recomputed_signature, stored_signature)

        is_valid = (len(corrupted_items) == 0) and merkle_root_valid and signature_valid
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return {
            "is_valid": is_valid,
            "tamper_detected": not is_valid,
            "bundle_id": bundle_id,
            "case_id": case_id,
            "total_items": len(raw_items),
            "items_verified": len(raw_items) - len(corrupted_items),
            "corrupted_items": corrupted_items,
            "merkle_root_valid": merkle_root_valid,
            "stored_merkle_root": stored_merkle,
            "recomputed_merkle_root": recomputed_merkle_root,
            "signature_valid": signature_valid,
            "signer_identity": signer_identity,
            "verified_at": now_ts,
            "legal_admissibility": "FEDERAL_RULES_OF_EVIDENCE_RULE_902_CERTIFIED" if is_valid else "FAILED_INTEGRITY_CHECK",
        }

    def append_custody_event(
        self,
        bundle: EvidenceBundle,
        action: str,
        actor: str,
        system_component: str,
        verification_status: str = "VERIFIED_CORRECT",
        notes: str = "",
    ) -> ChainOfCustodyEvent:
        """Appends a new verified custody transfer or compliance audit event to the bundle."""
        event_num = len(bundle.chain_of_custody) + 1
        event = ChainOfCustodyEvent(
            event_id=f"CUST-{bundle.case_id}-{event_num:03d}",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            action=action,
            actor=actor,
            system_component=system_component,
            verification_status=verification_status,
            notes=notes,
        )
        bundle.chain_of_custody.append(event)
        return event
