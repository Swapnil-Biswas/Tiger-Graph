"""
Adaptive Graph Query Budgeter & Traversal Pruner (src/agent/budgeter.py)
Dynamically allocates tool call budgets and prunes unnecessary expensive multi-hop
graph traversals based on initial risk entropy and early evidence sufficiency.
"""

from typing import Dict, Any


class AdaptiveGraphBudgeter:
    """
    Allocates graph investigation budgets and prunes redundant queries.
    Prevents query sprawl and latency explosion on benign/low-risk accounts
    while granting deep multi-hop budgets for complex fraud syndicates.
    """

    @classmethod
    def determine_plan(
        cls,
        trigger_data: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculates optimal tool budget and active expansion flags.
        """
        trigger_type = trigger_data.get("trigger_type", "risk_score")
        risk_score = trigger_data.get("risk_score")

        # 1. High-Uncertainty / Ambiguous Range (0.40 <= risk <= 0.75) or Syndicate Indicators
        if risk_score is not None and (0.40 <= risk_score <= 0.75):
            return {
                "budget_tier": "exhaustive",
                "max_tool_calls": 12,
                "allow_deep_ring_scan": True,
                "allow_geo_dispersion_scan": True,
                "allow_undocumented_detector": True,
                "allow_community_detection": True,
                "allow_burst_cluster_scan": True,
                "prune_rationale": "High-uncertainty ambiguous signal requires comprehensive multi-hop graph expansion and anomaly detection.",
            }

        # 2. Confirmed Customer Direct Report
        if trigger_type == "customer_report":
            return {
                "budget_tier": "targeted_escalation",
                "max_tool_calls": 8,
                "allow_deep_ring_scan": True,
                "allow_geo_dispersion_scan": True,
                "allow_undocumented_detector": True,
                "allow_community_detection": True,
                "allow_burst_cluster_scan": True,
                "prune_rationale": "Direct customer report focuses on transaction context, device nexus, and immediate compromise confirmation.",
            }

        # 3. High-Confidence Risk Spike (> 0.85)
        if risk_score is not None and risk_score > 0.85:
            return {
                "budget_tier": "targeted_confirmation",
                "max_tool_calls": 9,
                "allow_deep_ring_scan": True,
                "allow_geo_dispersion_scan": True,
                "allow_undocumented_detector": True,
                "allow_community_detection": True,
                "allow_burst_cluster_scan": True,
                "prune_rationale": "Critical risk score triggers targeted syndication checks and ring perimeter defense.",
            }

        # 4. Low-Risk / Routine Activity (< 0.30) with established baseline
        if risk_score is not None and risk_score < 0.30 and profile.get("txn_count", 0) > 10:
            return {
                "budget_tier": "fast_path_clearing",
                "max_tool_calls": 5,
                "allow_deep_ring_scan": False,
                "allow_geo_dispersion_scan": False,
                "allow_undocumented_detector": False,
                "allow_community_detection": False,
                "allow_burst_cluster_scan": False,
                "prune_rationale": "Low-risk transaction on established account; pruned expensive multi-hop ring scans to accelerate turnaround.",
            }

        # Default Standard Balanced Tier
        return {
            "budget_tier": "standard_balanced",
            "max_tool_calls": 10,
            "allow_deep_ring_scan": True,
            "allow_geo_dispersion_scan": True,
            "allow_undocumented_detector": True,
            "allow_community_detection": True,
            "allow_burst_cluster_scan": True,
            "prune_rationale": "Standard balanced investigation plan with complete telemetry.",
        }
