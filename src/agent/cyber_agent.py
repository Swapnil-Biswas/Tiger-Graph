"""
Cyber-Forensics & Device Fingerprint Specialist Agent (src/agent/cyber_agent.py)
Autonomous specialized domain agent for cybercrime, credential stuffing,
hardware spoofing, bot periodicity, and sybil device nexus forensics.
Coordinates Q4 (device_sharing_nexus), Q15 (detect_burst_cluster), and Q23 (resolve_cardholder_sybils)
into an immutable forensics assessment with automated cyber defense recommendations.
"""

from typing import Dict, List, Set, Any, Optional, Union
from dataclasses import dataclass, field, asdict

from src.graph.client import GraphClient, parse_as_of_epoch


@dataclass
class CyberForensicsAssessment:
    """
    Structured cyber-forensics assessment and defense strategy output.
    """
    case_id: str
    is_cyber_compromise_flagged: bool
    threat_tier: str                          # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    cyber_risk_score: float                   # 0.00 to 1.00
    detected_anomalies: List[str] = field(default_factory=list)
    device_nexus_summary: Dict[str, Any] = field(default_factory=dict)
    bot_burst_summary: Dict[str, Any] = field(default_factory=dict)
    sybil_analysis: Dict[str, Any] = field(default_factory=dict)
    compromised_devices: List[str] = field(default_factory=list)
    connected_sybil_cards: List[str] = field(default_factory=list)
    recommended_cyber_defenses: List[str] = field(default_factory=list)
    forensics_narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CyberForensicsAgent:
    """
    Specialized cyber forensics agent analyzing hardware fingerprint anomalies,
    device sharing rings, sybil accounts, and bot attack periodicity.
    """

    def __init__(self, client: Optional[GraphClient] = None):
        self.client = client or GraphClient(mode="embedded")

    def assess_case(
        self,
        case_id: str,
        as_of: Optional[Union[str, int]] = None,
    ) -> CyberForensicsAssessment:
        """
        Performs in-depth cyber-forensics and device fingerprint investigation for a case incident.
        """
        as_of_epoch = parse_as_of_epoch(as_of)

        # 1. Resolve case metadata
        pack = getattr(self.client.store, "case_pack", {})
        closed = getattr(self.client.store, "closed_cases", {})
        case_obj = pack.get(case_id) or closed.get(case_id) or {}

        card_id = str(case_obj.get("card_id", ""))
        flagged_txn = str(case_obj.get("flagged_transaction_id", ""))

        if not card_id and flagged_txn:
            txn_meta = self.client.store.transactions.get(flagged_txn, {})
            card_id = str(txn_meta.get("card_id", ""))

        # 2. Extract Associated Devices
        devices_set: Set[str] = set()
        if card_id:
            devs = self.client.store.devices_by_card.get(card_id, set())
            devices_set.update(devs)

        if flagged_txn:
            txn_meta = self.client.store.transactions.get(flagged_txn, {})
            dev = txn_meta.get("device_profile")
            if dev and dev != "None | None | None | None":
                devices_set.add(dev)

        clean_devices = [d for d in devices_set if not str(d).startswith("UnknownDevice") and str(d) != "None | None | None | None"]

        # 3. Analyze Device Sharing Nexus (Q4)
        nexus_summary: Dict[str, Any] = {}
        high_sharing_devices: List[str] = []
        max_device_card_count = 1

        for dev_id in clean_devices:
            try:
                nexus = self.client.device_sharing_nexus(dev_id, as_of=as_of_epoch)
                cards_on_dev = nexus.get("cards_count", 0)
                if cards_on_dev > max_device_card_count:
                    max_device_card_count = cards_on_dev
                if cards_on_dev > 1:
                    high_sharing_devices.append(dev_id)
                nexus_summary[dev_id[:30]] = {
                    "cards_count": cards_on_dev,
                    "cases_count": nexus.get("cases_count", 0),
                    "threat": nexus.get("threat_level", "low"),
                }
            except Exception:
                pass

        # 4. Analyze Bot / Velocity Burst Periodicities (Q15)
        burst_res = {}
        is_bot_attack = False
        if flagged_txn:
            try:
                burst_res = self.client.detect_burst_cluster(flagged_txn, as_of=as_of_epoch)
                is_bot_attack = burst_res.get("is_bot_periodicity", False) or burst_res.get("burst_intensity_ratio", 1.0) >= 3.0
            except Exception:
                burst_res = {}

        # 5. Analyze Probabilistic Sybil Accounts (Q23)
        sybil_res = {}
        sybil_cards: List[str] = []
        if card_id:
            try:
                sybil_res = self.client.resolve_cardholder_sybils(card_id, as_of=as_of_epoch)
                sybil_cards = [str(s.get("sybil_card_id", "")) for s in sybil_res.get("probable_sybils", [])]
            except Exception:
                sybil_res = {}

        # 6. Synthesize Cyber Anomalies & Threat Score
        anomalies: List[str] = []
        defenses: List[str] = []
        score = 0.0

        if high_sharing_devices:
            anomalies.append(f"DEVICE_POOLING_NEXUS (Max {max_device_card_count} cards on hardware)")
            defenses.append("BLACKLIST_DEVICE_HARDWARE")
            defenses.append("STEP_UP_DEVICE_BIOMETRICS")
            score += 0.40

        if is_bot_attack:
            anomalies.append("BOT_SCRIPTED_TESTING_BURST")
            defenses.append("RATE_LIMIT_DEVICE_IP")
            defenses.append("REQUIRE_CAPTCHA_CHALLENGE")
            score += 0.35

        if sybil_cards:
            anomalies.append(f"SYBIL_ACCOUNT_NETWORK ({len(sybil_cards)} linked card identities)")
            defenses.append("MERGE_DEVICE_ENTITY_CLUSTER")
            defenses.append("STEP_UP_AUTH_AND_EDD")
            score += 0.35

        score = round(min(1.0, score), 4)

        if score >= 0.70:
            threat_tier = "CRITICAL"
        elif score >= 0.40:
            threat_tier = "HIGH"
        elif score >= 0.15:
            threat_tier = "MEDIUM"
        else:
            threat_tier = "LOW"

        is_flagged = (score >= 0.15 or len(anomalies) > 0)

        if not defenses:
            defenses.append("MAINTAIN_STANDARD_TELEMETRY")

        # 7. Generate Forensics Narrative
        narrative_parts = [
            f"=== CYBER-FORENSICS & HARDWARE INTEGRITY REPORT (CASE: {case_id}) ===",
            f"Threat Tier: {threat_tier} (Cyber Risk Score: {score:.2f}) | Evaluated Devices: {len(clean_devices)}",
        ]
        if anomalies:
            narrative_parts.append(f"Detected Cyber Compromise Indicators: {'; '.join(anomalies)}")
        if high_sharing_devices:
            narrative_parts.append(f"High-Risk Hardware Profiles: {len(high_sharing_devices)} device(s) exhibiting multi-card pooling.")
        if sybil_cards:
            narrative_parts.append(f"Probabilistic Sybil Clusters: {len(sybil_cards)} linked account(s) ({', '.join(sybil_cards[:5])}).")
        narrative_parts.append(f"Recommended Defensive Controls: {', '.join(defenses)}")

        forensics_narrative = "\n".join(narrative_parts)

        return CyberForensicsAssessment(
            case_id=case_id,
            is_cyber_compromise_flagged=is_flagged,
            threat_tier=threat_tier,
            cyber_risk_score=score,
            detected_anomalies=anomalies,
            device_nexus_summary=nexus_summary,
            bot_burst_summary=burst_res,
            sybil_analysis=sybil_res,
            compromised_devices=high_sharing_devices,
            connected_sybil_cards=sybil_cards,
            recommended_cyber_defenses=defenses,
            forensics_narrative=forensics_narrative,
        )
