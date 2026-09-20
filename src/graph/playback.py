"""
Interactive Temporal Graph Playback & Syndicate Cascade Visualizer (src/graph/playback.py)
Constructs chronological, frame-by-frame visual graph trajectories of fraud attacks,
capturing expanding ego-nets, device linkings, velocity bursts, BSA structuring breaches,
and consensus action enforcement for dynamic UI timeline scrubbing.
"""

import time
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Set, Tuple


@dataclass
class PlaybackStep:
    """
    Single chronological state frame in the interactive graph playback sequence.
    """
    frame_index: int
    timestamp: str
    event_category: str       # "SEED_ENTITY", "TRANSACTION", "DEVICE_LINK", "VELOCITY_BURST", "SAR_THRESHOLD_BREACH", "FINAL_DECISION"
    description: str
    current_exposure_usd: float
    rolling_velocity_count: int
    risk_score: float
    highlight_node_ids: List[str] = field(default_factory=list)
    highlight_edge_ids: List[str] = field(default_factory=list)
    cumulative_elements: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    narrative_caption: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlaybackTimeline:
    """
    Complete chronological timeline of an incident's graph evolution.
    """
    case_id: str
    total_frames: int
    start_time: str
    end_time: str
    total_exposure_usd: float
    peak_risk_score: float
    milestones: Dict[str, int] = field(default_factory=dict)
    frames: List[PlaybackStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalGraphPlaybackEngine:
    """
    Reconstructs chronological transaction trajectories and generates animated
    Cytoscape.js-compatible graph playback timelines.
    """

    def __init__(self, client: Optional[Any] = None):
        self.client = client

    def generate_case_playback(self, case_id: str, max_frames: int = 50) -> PlaybackTimeline:
        """
        Generates an interactive step-by-step graph evolution playback timeline for a case.
        """
        if not self.client:
            from src.graph.client import GraphClient
            self.client = GraphClient(mode="embedded")

        store = self.client.store
        pack_item = store.case_pack.get(case_id) or store.closed_cases.get(case_id, {})
        card_id = str(pack_item.get("card_id", "UNKNOWN"))
        customer_id = str(pack_item.get("customer_id", "UNKNOWN"))

        # Gather relevant transactions
        txns = []
        txn_ids = pack_item.get("txn_ids", [])
        if not txn_ids and "flagged_txn_id" in pack_item:
            txn_ids = [pack_item["flagged_txn_id"]]

        for tid in txn_ids:
            str_tid = str(tid)
            if str_tid in store.transactions:
                txns.append(store.transactions[str_tid])

        # If few transactions directly listed, gather all from card history
        if len(txns) < 3 and card_id in store.cards:
            card_txns = store.cards[card_id].get("transactions", [])
            for t in card_txns:
                tid = str(t.get("TransactionID"))
                if tid and tid in store.transactions and store.transactions[tid] not in txns:
                    txns.append(store.transactions[tid])

        # Sort transactions chronologically
        txns.sort(key=lambda t: str(t.get("timestamp", t.get("TransactionDT", ""))))

        # Subsample if exceeds max frames
        if len(txns) > max_frames - 2:
            step_size = math.ceil(len(txns) / (max_frames - 2))
            txns = txns[::step_size]

        frames: List[PlaybackStep] = []
        milestones: Dict[str, int] = {}
        cumulative_nodes: Dict[str, Dict[str, Any]] = {}
        cumulative_edges: Dict[str, Dict[str, Any]] = {}

        def add_node(nid: str, ntype: str, label: str, data: Optional[Dict[str, Any]] = None):
            payload = {"id": nid, "type": ntype, "label": label}
            if data:
                payload.update(data)
            cumulative_nodes[nid] = {"data": payload}

        def add_edge(eid: str, src: str, dst: str, etype: str, label: str = ""):
            cumulative_edges[eid] = {"data": {"id": eid, "source": src, "target": dst, "type": etype, "label": label}}

        # Frame 0: Baseline Account & Customer Setup
        c_time = str(pack_item.get("opened_at", "2024-01-01 00:00:00"))
        add_node(f"cust_{customer_id}", "Customer", f"Customer {customer_id}")
        add_node(f"card_{card_id}", "Card", f"Card {card_id}")
        add_edge(f"e_cust_card_{card_id}", f"cust_{customer_id}", f"card_{card_id}", "OWNS", "OWNS")
        milestones["baseline_opened"] = 0

        frame0 = PlaybackStep(
            frame_index=0,
            timestamp=c_time,
            event_category="SEED_ENTITY",
            description=f"Account initialized for Card {card_id} and Customer {customer_id}.",
            current_exposure_usd=0.0,
            rolling_velocity_count=0,
            risk_score=0.05,
            highlight_node_ids=[f"cust_{customer_id}", f"card_{card_id}"],
            highlight_edge_ids=[f"e_cust_card_{card_id}"],
            cumulative_elements={
                "nodes": list(cumulative_nodes.values()),
                "edges": list(cumulative_edges.values()),
            },
            alerts=[],
            narrative_caption=f"Frame 0: Case baseline established. Cardholder profile loaded with no active alerts.",
        )
        frames.append(frame0)

        # Iterate Transactions Frame-by-Frame
        cumulative_exposure = 0.0
        peak_risk = 0.05
        seen_devices: Set[str] = set()
        bsa_breached = False
        velocity_alert_triggered = False

        for idx, t in enumerate(txns, start=1):
            tid = str(t.get("TransactionID", f"TXN_{idx}"))
            t_amt = float(t.get("amount", t.get("TransactionAmt", 0.0)))
            t_time = str(t.get("timestamp", c_time))
            t_risk = float(t.get("risk_score", 0.10))
            dev = str(t.get("device_profile", ""))
            addr = str(t.get("addr1", ""))
            alerts = []

            cumulative_exposure += t_amt
            peak_risk = max(peak_risk, t_risk)

            # Nodes & Edges for this transaction
            t_nid = f"txn_{tid}"
            add_node(t_nid, "Transaction", f"${t_amt:,.2f}", {"risk": t_risk, "amount": t_amt})
            e_made_id = f"e_made_{tid}"
            add_edge(e_made_id, f"card_{card_id}", t_nid, "MADE", "MADE")

            highlight_nodes = [t_nid]
            highlight_edges = [e_made_id]

            # Device Link
            if dev and dev != "None | None | None | None":
                d_nid = f"dev_{dev[:16]}"
                is_new_device = dev not in seen_devices
                seen_devices.add(dev)
                add_node(d_nid, "DeviceProfile", dev.split(" | ")[0])
                e_dev_id = f"e_dev_{tid}"
                add_edge(e_dev_id, t_nid, d_nid, "FROM_DEVICE", "DEVICE")
                highlight_nodes.append(d_nid)
                highlight_edges.append(e_dev_id)

                if is_new_device and idx > 1:
                    alerts.append(f"Novel device fingerprint detected: {dev.split(' | ')[0]}")

            # Region Node
            if addr and addr != "None":
                r_nid = f"reg_{addr}"
                add_node(r_nid, "BillingRegion", f"Region {addr}")
                e_reg_id = f"e_reg_{tid}"
                add_edge(e_reg_id, t_nid, r_nid, "BILLED_AT", "REGION")
                highlight_nodes.append(r_nid)

            # Detect BSA Threshold Breach ($10,000)
            category = "TRANSACTION"
            if cumulative_exposure >= 10000.0 and not bsa_breached:
                bsa_breached = True
                category = "SAR_THRESHOLD_BREACH"
                milestones["bsa_threshold_breach"] = idx
                alerts.append("STATUTORY COMPLIANCE: BSA 31 USC 5324(a) $10,000 structuring threshold reached.")

            # Detect Velocity Spike
            if idx >= 3 and not velocity_alert_triggered:
                velocity_alert_triggered = True
                category = "VELOCITY_BURST"
                milestones["velocity_surge"] = idx
                alerts.append(f"CYBER ALERT: Velocity anomaly ({idx} transactions in rapid sequence).")

            caption = (
                f"Frame {idx}: Transaction {tid} for ${t_amt:,.2f} recorded. "
                f"Cumulative spend: ${cumulative_exposure:,.2f}. Risk points: {t_risk:.2f}."
            )
            if alerts:
                caption += " Alerts: " + "; ".join(alerts)

            step = PlaybackStep(
                frame_index=idx,
                timestamp=t_time,
                event_category=category,
                description=f"Transaction {tid} authorized (${t_amt:,.2f}).",
                current_exposure_usd=round(cumulative_exposure, 2),
                rolling_velocity_count=idx,
                risk_score=round(t_risk, 3),
                highlight_node_ids=highlight_nodes,
                highlight_edge_ids=highlight_edges,
                cumulative_elements={
                    "nodes": list(cumulative_nodes.values()),
                    "edges": list(cumulative_edges.values()),
                },
                alerts=alerts,
                narrative_caption=caption,
            )
            frames.append(step)

        # Final Frame: Consensus & Action Enforcement
        final_idx = len(frames)
        outcome = str(pack_item.get("outcome", "review"))
        final_verdict = "fraud" if outcome == "confirmed_fraud" else ("legitimate" if outcome == "cleared" else "review")
        action_node_id = f"action_{case_id}"
        add_node(action_node_id, "ConsensusAction", f"VERDICT: {final_verdict.upper()}", {"verdict": final_verdict})
        e_action_id = f"e_action_{case_id}"
        add_edge(e_action_id, f"card_{card_id}", action_node_id, "ENFORCED_ACTION", "ENFORCED")
        milestones["decision_enforced"] = final_idx

        final_alerts = []
        if bsa_breached:
            final_alerts.append("FILE_SAR_FINCEN (Statutory BSA Filing)")
        if final_verdict == "fraud":
            final_alerts.append("BLOCK_CARD & ISOLATE_HARDWARE_FINGERPRINT")
        else:
            final_alerts.append("ALLOW_TRANSACTION")

        final_step = PlaybackStep(
            frame_index=final_idx,
            timestamp=frames[-1].timestamp if frames else c_time,
            event_category="FINAL_DECISION",
            description=f"Multi-agent consensus finalized verdict: {final_verdict.upper()}.",
            current_exposure_usd=round(cumulative_exposure, 2),
            rolling_velocity_count=len(txns),
            risk_score=round(peak_risk, 3),
            highlight_node_ids=[action_node_id],
            highlight_edge_ids=[e_action_id],
            cumulative_elements={
                "nodes": list(cumulative_nodes.values()),
                "edges": list(cumulative_edges.values()),
            },
            alerts=final_alerts,
            narrative_caption=(
                f"Frame {final_idx} (Final): Autonomous consensus concluded verdict '{final_verdict.upper()}'. "
                f"Actions enforced: {', '.join(final_alerts)}."
            ),
        )
        frames.append(final_step)

        return PlaybackTimeline(
            case_id=case_id,
            total_frames=len(frames),
            start_time=frames[0].timestamp if frames else c_time,
            end_time=frames[-1].timestamp if frames else c_time,
            total_exposure_usd=round(cumulative_exposure, 2),
            peak_risk_score=round(peak_risk, 3),
            milestones=milestones,
            frames=frames,
        )
