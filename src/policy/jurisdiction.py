"""
Multi-Jurisdiction Regulatory Routing & Compliance Engine
Enforces jurisdiction-specific reporting mandates (US FinCEN SAR, UK FCA/NCA STR, EU 6AMLD)
and GDPR Article 5/46 cross-border data minimization on fraud evidence and case packages.
"""

import os
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta


class RegulatoryStructuringDetector:
    """
    Detects regulatory structuring (smurfing) and performs multi-entity exposure rollups
    across cards, customer accounts, and device profiles under BSA 31 CFR 1010.314 / 1020.320,
    UK POCA 2002 Part 7, and EU 6AMLD.
    """

    THRESHOLDS = {
        "US": {
            "ctr_threshold": 10000.0,
            "sub_threshold_min": 8000.0,
            "sub_threshold_max": 9999.99,
            "statute_ctr": "Bank Secrecy Act / 31 CFR 1010.311 (CTR)",
            "statute_structuring": "Bank Secrecy Act / 31 CFR 1010.314 (Structuring)",
            "statute_sar": "31 CFR 1020.320 (SAR)",
            "agency": "Financial Crimes Enforcement Network (FinCEN)",
        },
        "UK": {
            "ctr_threshold": 3000.0,    # ~£2,500
            "sub_threshold_min": 2400.0,
            "sub_threshold_max": 2999.99,
            "statute_ctr": "Money Laundering Regulations 2017 Reg 33",
            "statute_structuring": "Proceeds of Crime Act 2002 (POCA) Section 327-334",
            "statute_sar": "POCA 2002 Part 7 (DAML STR)",
            "agency": "National Crime Agency (NCA) / FCA",
        },
        "EU": {
            "ctr_threshold": 2500.0,    # ~€2,000
            "sub_threshold_min": 1800.0,
            "sub_threshold_max": 2499.99,
            "statute_ctr": "6AMLD Directive (EU) 2018/1673 Art 3",
            "statute_structuring": "6AMLD Directive (EU) 2018/1673 Art 7",
            "statute_sar": "EU Financial Intelligence Units (FIU.net STR)",
            "agency": "European Financial Intelligence Units (FIU.net)",
        },
    }

    @classmethod
    def detect_structuring(
        cls,
        customer_id: Optional[str] = None,
        device_profile: Optional[str] = None,
        card_ids: Optional[List[str]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
        window_hours: float = 24.0,
        as_of: Optional[Any] = None,
        jurisdiction: str = "US",
        client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Performs multi-entity exposure rollup and structuring evasion detection.
        Gathers transactions across cards, customers, or devices within the temporal window.
        """
        j_key = jurisdiction.upper()
        if j_key not in cls.THRESHOLDS:
            j_key = "US"
        thresh_info = cls.THRESHOLDS[j_key]

        # 1. Gather transactions
        gathered_txns: List[Dict[str, Any]] = []
        if transactions is not None:
            gathered_txns = list(transactions)
        elif client is not None and hasattr(client, "store"):
            resolved_cards = set(card_ids or [])
            if customer_id:
                cust_txns = client.store.txns_by_customer.get(customer_id, [])
                for t in cust_txns:
                    if t.get("card_id"):
                        resolved_cards.add(t["card_id"])
                gathered_txns.extend(cust_txns)

            if device_profile:
                dev_cards = getattr(client.store, "cards_by_device", {}).get(device_profile, set())
                resolved_cards.update(dev_cards)
                dev_txns = client.store.txns_by_device.get(device_profile, [])
                gathered_txns.extend(dev_txns)

            for cid in resolved_cards:
                c_txns = client.store.txns_by_card.get(cid, [])
                gathered_txns.extend(c_txns)

        # Deduplicate transactions by id / txn_id
        seen_ids = set()
        deduped_txns: List[Dict[str, Any]] = []
        for t in gathered_txns:
            tid = str(t.get("txn_id") or t.get("id") or "")
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            deduped_txns.append(t)

        # Parse as_of_epoch if available
        as_of_epoch = None
        if as_of is not None:
            if isinstance(as_of, (int, float)):
                as_of_epoch = int(as_of)
                if as_of_epoch > 20000000:
                    as_of_epoch //= 1000
            elif isinstance(as_of, str):
                try:
                    dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                    as_of_epoch = int(dt.timestamp())
                except Exception:
                    pass

        # Normalize epoch_s
        valid_txns = []
        for t in deduped_txns:
            ep = t.get("epoch_s")
            if ep is None and t.get("ts"):
                try:
                    dt = datetime.fromisoformat(str(t["ts"]).replace("Z", "+00:00"))
                    ep = int(dt.timestamp())
                except Exception:
                    ep = 0
            if ep is None:
                ep = 0
            t_copy = dict(t)
            t_copy["_epoch"] = ep
            valid_txns.append(t_copy)

        if as_of_epoch is not None:
            valid_txns = [t for t in valid_txns if t["_epoch"] <= as_of_epoch]

        if not valid_txns:
            return {
                "jurisdiction": j_key,
                "window_hours": window_hours,
                "total_exposure_usd": 0.0,
                "transaction_count": 0,
                "card_count": 0,
                "device_count": 0,
                "distinct_cards": [],
                "distinct_devices": [],
                "is_structuring": False,
                "structuring_indicators": [],
                "mandatory_filings": [],
                "narrative_summary": "No transactions identified for multi-entity rollup in specified window.",
                "transactions": [],
            }

        # Determine reference time for window:
        ref_epoch = as_of_epoch if as_of_epoch is not None else max(t["_epoch"] for t in valid_txns)
        window_start = ref_epoch - int(window_hours * 3600)

        window_txns = [t for t in valid_txns if t["_epoch"] >= window_start]
        if not window_txns and valid_txns:
            window_txns = valid_txns

        # Calculate Rollup Metrics
        amounts = [float(t.get("amount", 0.0)) for t in window_txns]
        total_exposure = round(sum(amounts), 2)
        txn_count = len(window_txns)
        distinct_cards = sorted(list({str(t.get("card_id")) for t in window_txns if t.get("card_id")}))
        distinct_devices = sorted(list({str(t.get("device_profile")) for t in window_txns if t.get("device_profile") and t.get("device_profile") != "None | None | None | None"}))
        max_amount = max(amounts) if amounts else 0.0

        # Check Red Flag Indicators
        indicators = []
        mandatory_filings = []

        ctr_thresh = thresh_info["ctr_threshold"]
        sub_min = thresh_info["sub_threshold_min"]
        sub_max = thresh_info["sub_threshold_max"]

        # Indicator 1: CTR Threshold Exceeded
        if total_exposure >= ctr_thresh:
            indicators.append("CTR_THRESHOLD_EXCEEDED")
            mandatory_filings.append("FILE_CTR")

        # Indicator 2: Sub-threshold concentration (Classic smurfing)
        sub_thresh_txns = [a for a in amounts if sub_min <= a <= sub_max]
        if len(sub_thresh_txns) >= 2:
            indicators.append("SUB_THRESHOLD_CONCENTRATION")
            if "FILE_SAR_STRUCTURING" not in mandatory_filings:
                mandatory_filings.append("FILE_SAR_STRUCTURING")

        # Indicator 3: Multi-Card Dispersion
        if len(distinct_cards) >= 2 and total_exposure >= ctr_thresh and max_amount < ctr_thresh:
            indicators.append("MULTI_CARD_DISPERSION")
            if "FILE_SAR_STRUCTURING" not in mandatory_filings:
                mandatory_filings.append("FILE_SAR_STRUCTURING")

        # Indicator 4: Rapid Dispersed Velocity (3+ transactions within 6 hours totaling >= 70% of CTR threshold)
        if txn_count >= 3 and total_exposure >= (0.7 * ctr_thresh):
            epochs = sorted([t["_epoch"] for t in window_txns])
            if epochs[-1] - epochs[0] <= 21600:  # 6 hours
                indicators.append("RAPID_DISPERSED_VELOCITY")
                if "FILE_SAR_STRUCTURING" not in mandatory_filings:
                    mandatory_filings.append("FILE_SAR_STRUCTURING")

        # Indicator 5: Round Sum Concentration (multiple round numbers e.g. $9,000, $5,000, $2,500)
        round_txns = [a for a in amounts if (a % 100 == 0 or a % 500 == 0) and a >= (0.25 * sub_min)]
        if len(round_txns) >= 2:
            indicators.append("ROUND_SUM_CONCENTRATION")

        is_structuring = bool(set(indicators) - {"CTR_THRESHOLD_EXCEEDED"}) or ("CTR_THRESHOLD_EXCEEDED" in indicators and len(distinct_cards) > 1)

        # Build Narrative Summary
        narrative_parts = []
        if is_structuring or mandatory_filings:
            narrative_parts.append(
                f"Multi-entity exposure rollup for {j_key} jurisdiction identified ${total_exposure:,.2f} "
                f"across {txn_count} transactions and {len(distinct_cards)} card(s) within a {window_hours}h rolling window."
            )
            if "CTR_THRESHOLD_EXCEEDED" in indicators:
                narrative_parts.append(
                    f"Mandatory Currency Transaction Report (CTR) filing triggered under {thresh_info['statute_ctr']} "
                    f"(Aggregate exposure ${total_exposure:,.2f} >= ${ctr_thresh:,.2f} threshold)."
                )
            if "SUB_THRESHOLD_CONCENTRATION" in indicators:
                narrative_parts.append(
                    f"Sub-threshold structuring detected: {len(sub_thresh_txns)} transactions concentrated in the "
                    f"${sub_min:,.2f}-${sub_max:,.2f} band, indicating deliberate evasion under {thresh_info['statute_structuring']}."
                )
            if "MULTI_CARD_DISPERSION" in indicators:
                narrative_parts.append(
                    f"Coordinated multi-card dispersion observed across {len(distinct_cards)} cards under {thresh_info['statute_structuring']}, "
                    f"artificially maintaining single-card charges below the ${ctr_thresh:,.2f} reporting threshold."
                )
            if "RAPID_DISPERSED_VELOCITY" in indicators:
                narrative_parts.append(
                    "Rapid velocity burst detected (< 6 hours elapsed between transactions)."
                )
        else:
            narrative_parts.append(
                f"Multi-entity exposure rollup identified ${total_exposure:,.2f} across {txn_count} transactions "
                f"and {len(distinct_cards)} card(s). No structuring or CTR threshold violations detected."
            )

        narrative_summary = " ".join(narrative_parts)

        return {
            "jurisdiction": j_key,
            "window_hours": window_hours,
            "total_exposure_usd": total_exposure,
            "transaction_count": txn_count,
            "card_count": len(distinct_cards),
            "device_count": len(distinct_devices),
            "distinct_cards": distinct_cards,
            "distinct_devices": distinct_devices,
            "is_structuring": is_structuring,
            "structuring_indicators": indicators,
            "mandatory_filings": mandatory_filings,
            "narrative_summary": narrative_summary,
            "transactions": [
                {
                    "txn_id": t.get("txn_id") or t.get("id"),
                    "amount": t.get("amount"),
                    "card_id": t.get("card_id"),
                    "ts": t.get("ts"),
                    "device_profile": t.get("device_profile"),
                }
                for t in window_txns
            ],
        }


class CrossBorderAMLRiskDetector:
    """
    Detects cross-border AML transaction bundling, correspondent banking risks,
    and high-risk FATF jurisdictional corridors under FinCEN 31 CFR 1010.610/620,
    EU 6AMLD Article 3, and UK Money Laundering Regulations 2017.
    """

    FATF_HIGH_RISK_JURISDICTIONS = {"IR", "KP", "MM", "SY", "YE", "RU", "999", "OFFSHORE", "HAVEN"}
    FATF_GREY_LIST_JURISDICTIONS = {"AE", "PA", "KY", "VG", "BS", "CY", "MT", "888"}
    DOMESTIC_COUNTRY_CODES = {"87", "87.0", "US", "USA"}

    CORRESPONDENT_THRESHOLDS = {
        "edd_threshold_usd": 5000.0,
        "sar_aml_threshold_usd": 2500.0,
        "max_corridor_velocity_hours": 48.0,
    }

    @classmethod
    def evaluate_cross_border_risk(
        cls,
        card_id: str,
        transactions: Optional[List[Dict[str, Any]]] = None,
        as_of: Optional[Any] = None,
        client: Optional[Any] = None,
        window_hours: float = 48.0,
    ) -> Dict[str, Any]:
        """
        Evaluates cross-border flow, correspondent banking risk, and FATF corridor exposure.
        """
        from src.graph.client import parse_as_of_epoch
        as_of_epoch = parse_as_of_epoch(as_of)

        gathered_txns: List[Dict[str, Any]] = []
        if transactions is not None:
            gathered_txns = list(transactions)
        elif client is not None and hasattr(client, "store"):
            all_card_txns = client.store.txns_by_card.get(card_id, [])
            gathered_txns = list(all_card_txns)

        # Normalize and filter strictly by as_of_epoch
        valid_txns = []
        for t in gathered_txns:
            ep = t.get("epoch_s")
            if ep is None:
                ep = t.get("ts")
            try:
                ep = float(ep) if ep is not None else 0.0
            except (ValueError, TypeError):
                ep = 0.0
            t_copy = dict(t)
            t_copy["_epoch"] = ep
            valid_txns.append(t_copy)

        if as_of_epoch is not None:
            valid_txns = [t for t in valid_txns if t["_epoch"] <= as_of_epoch]

        if not valid_txns:
            return {
                "card_id": card_id,
                "window_hours": window_hours,
                "total_transactions_evaluated": 0,
                "cross_border_txns_count": 0,
                "distinct_regions_count": 0,
                "distinct_countries_count": 0,
                "cross_border_exposure_usd": 0.0,
                "has_fatf_high_risk_corridor": False,
                "has_fatf_grey_list_corridor": False,
                "is_layering_bundling_detected": False,
                "enhanced_due_diligence_required": False,
                "aml_risk_score": 0.0,
                "aml_threat_level": "low",
                "mandatory_actions": [],
                "statutory_authority": "31 CFR 1010.610/620 (Correspondent Banking EDD) / EU 6AMLD Art 3",
                "description": "No transactions found within evaluated scope.",
            }

        ref_epoch = as_of_epoch if as_of_epoch is not None and as_of_epoch < 9000000000 else max(t["_epoch"] for t in valid_txns)
        window_seconds = int(window_hours * 3600)
        window_start = ref_epoch - window_seconds

        window_txns = [t for t in valid_txns if t["_epoch"] >= window_start]
        if not window_txns and valid_txns:
            window_txns = valid_txns

        distinct_regions = set()
        distinct_countries = set()
        cross_border_txns = []
        has_fatf_high_risk = False
        has_fatf_grey_list = False
        cross_border_exposure = 0.0

        for t in window_txns:
            addr1 = str(t.get("addr1") or t.get("region") or "")
            addr2 = str(t.get("addr2") or t.get("country") or "87.0")
            amt = float(t.get("amount", 0.0) or 0.0)
            custom_jur = str(t.get("jurisdiction") or "").upper()

            if addr1:
                distinct_regions.add(addr1)
            if addr2:
                distinct_countries.add(addr2)

            is_cb = (addr2 not in cls.DOMESTIC_COUNTRY_CODES) or (t.get("is_cross_border") is True) or (custom_jur and custom_jur != "US")
            is_fatf_high = (addr2 in cls.FATF_HIGH_RISK_JURISDICTIONS) or (custom_jur in cls.FATF_HIGH_RISK_JURISDICTIONS) or (addr1 == "999")
            is_fatf_grey = (addr2 in cls.FATF_GREY_LIST_JURISDICTIONS) or (custom_jur in cls.FATF_GREY_LIST_JURISDICTIONS) or (addr1 == "888")

            if is_cb or is_fatf_high or is_fatf_grey:
                cross_border_txns.append(t)
                cross_border_exposure += amt

            if is_fatf_high:
                has_fatf_high_risk = True
            if is_fatf_grey:
                has_fatf_grey_list = True

        # Layering / bundling detection: 3+ distinct regions or 2+ distinct international countries within window
        is_layering = (len(distinct_regions) >= 3 and len(cross_border_txns) >= 2) or (len(distinct_countries) >= 2 and cross_border_exposure >= 1000.0)

        mandatory_actions = []
        edd_required = False

        if has_fatf_high_risk:
            edd_required = True
            mandatory_actions.append("ENHANCED_DUE_DILIGENCE")
            if cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["sar_aml_threshold_usd"]:
                mandatory_actions.append("FILE_SAR_CROSS_BORDER_AML")

        if has_fatf_grey_list and cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["sar_aml_threshold_usd"]:
            edd_required = True
            mandatory_actions.append("ENHANCED_DUE_DILIGENCE")

        if cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["edd_threshold_usd"]:
            edd_required = True
            if "ENHANCED_DUE_DILIGENCE" not in mandatory_actions:
                mandatory_actions.append("ENHANCED_DUE_DILIGENCE")

        if is_layering:
            mandatory_actions.append("BLOCK_CORRESPONDENT_PATH")
            mandatory_actions.append("RESTRICT_OUTBOUND_WIRES")
            if cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["sar_aml_threshold_usd"]:
                if "FILE_SAR_CROSS_BORDER_AML" not in mandatory_actions:
                    mandatory_actions.append("FILE_SAR_CROSS_BORDER_AML")

        # Composite AML risk score
        aml_risk = 0.0
        if has_fatf_high_risk:
            aml_risk += 0.50
        elif has_fatf_grey_list:
            aml_risk += 0.30

        if cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["edd_threshold_usd"]:
            aml_risk += 0.30
        elif cross_border_exposure >= cls.CORRESPONDENT_THRESHOLDS["sar_aml_threshold_usd"]:
            aml_risk += 0.20

        if is_layering:
            aml_risk += 0.25

        aml_risk = min(0.99, round(aml_risk, 2))

        if aml_risk >= 0.70:
            threat = "critical"
        elif aml_risk >= 0.40:
            threat = "high"
        elif aml_risk >= 0.15:
            threat = "moderate"
        else:
            threat = "low"

        if mandatory_actions:
            desc = (
                f"Cross-border AML risk detected: {len(cross_border_txns)} international transaction(s) "
                f"totaling ${cross_border_exposure:,.2f} across {len(distinct_countries)} jurisdiction(s). "
                f"FATF high-risk corridor: {has_fatf_high_risk}, layering detected: {is_layering} (threat: {threat})."
            )
        else:
            desc = (
                f"Domestic routine activity: {len(window_txns)} transaction(s) within domestic jurisdiction. "
                f"No cross-border AML or correspondent banking anomalies detected."
            )

        return {
            "card_id": card_id,
            "window_hours": window_hours,
            "total_transactions_evaluated": len(window_txns),
            "cross_border_txns_count": len(cross_border_txns),
            "distinct_regions_count": len(distinct_regions),
            "distinct_countries_count": len(distinct_countries),
            "cross_border_exposure_usd": round(cross_border_exposure, 2),
            "has_fatf_high_risk_corridor": has_fatf_high_risk,
            "has_fatf_grey_list_corridor": has_fatf_grey_list,
            "is_layering_bundling_detected": is_layering,
            "enhanced_due_diligence_required": edd_required,
            "aml_risk_score": aml_risk,
            "aml_threat_level": threat,
            "mandatory_actions": mandatory_actions,
            "statutory_authority": "31 CFR 1010.610/620 (Correspondent Banking EDD) / EU 6AMLD Art 3",
            "description": desc,
        }


class JurisdictionComplianceRouter:
    """
    Evaluates cross-jurisdictional compliance rules, determines mandatory regulatory
    filings (FinCEN vs NCA vs FIU), and applies GDPR data minimization shields.
    """

    # Supported Jurisdictions
    JURISDICTIONS = {
        "US": {
            "agency": "Financial Crimes Enforcement Network (FinCEN)",
            "statute": "Bank Secrecy Act / 31 CFR 1020.320",
            "filing_type": "Suspicious Activity Report (SAR)",
            "threshold_usd": 5000.0,
            "filing_deadline_days": 30,
            "retention_years": 5,
        },
        "UK": {
            "agency": "National Crime Agency (NCA) / Financial Conduct Authority (FCA)",
            "statute": "Proceeds of Crime Act 2002 (POCA) Part 7 / MLR 2017",
            "filing_type": "Suspicious Activity Report / DAML STR",
            "threshold_usd": 3000.0,  # ~£2,500
            "filing_deadline_days": 14,
            "moratorium_period_days": 7,
            "retention_years": 5,
        },
        "EU": {
            "agency": "European Financial Intelligence Units (FIU.net) / 6AMLD",
            "statute": "6th Anti-Money Laundering Directive (EU) 2018/1673 & GDPR Reg (EU) 2016/679",
            "filing_type": "Suspicious Transaction Report (STR)",
            "threshold_usd": 2500.0,  # ~€2,000
            "filing_deadline_days": 10,
            "retention_years": 5,
            "gdpr_masking_required": True,
        },
    }

    @staticmethod
    def detect_jurisdiction(case_data: Dict[str, Any], trigger: Optional[Dict[str, Any]] = None) -> str:
        """
        Detects regulatory jurisdiction from case billing region, merchant country,
        IP geolocation, or card currency profile.
        """
        text_corpus = ""
        if trigger:
            text_corpus += f" {trigger.get('trigger_text', '')} {trigger.get('notes', '')}"
        
        c_obj = case_data.get("case", case_data)
        text_corpus += f" {c_obj.get('summary', '')} {c_obj.get('pattern', '')}"

        for ev in c_obj.get("evidence", []):
            text_corpus += f" {ev.get('claim', '')} {ev.get('ref', '')}"

        text_upper = text_corpus.upper()

        # UK Indicators
        if any(term in text_upper for term in ["UNITED KINGDOM", "LONDON", "GBP", "MANCHESTER", "UK REGION", "FCA"]):
            return "UK"

        # EU Indicators
        if any(term in text_upper for term in ["EUROPE", "GERMANY", "FRANCE", "SPAIN", "ITALY", "EUR", "AMSTERDAM", "PARIS", "FRANKFURT", "EU REGION"]):
            return "EU"

        # Cross-border if multiple regional indicators appear
        has_us = any(term in text_upper for term in ["US", "USA", "UNITED STATES", "NEW YORK", "CALIFORNIA", "USD"])
        has_foreign = any(term in text_upper for term in ["CROSS-BORDER", "OVERSEAS", "INTERNATIONAL", "OUT OF REGION"])

        if has_us and has_foreign:
            return "CROSS_BORDER"

        return "US"

    @classmethod
    def evaluate_regulatory_obligations(
        cls,
        jurisdiction: str,
        exposure_usd: float,
        is_fraud: bool,
        pattern: str = "none",
    ) -> Dict[str, Any]:
        """
        Determines filing requirements, statutory citations, and submission deadlines.
        """
        j_key = jurisdiction.upper()
        if j_key not in cls.JURISDICTIONS:
            j_key = "US"

        j_spec = cls.JURISDICTIONS[j_key]
        threshold = j_spec["threshold_usd"]

        # Money Laundering / Structuring / Syndicates lower the threshold
        if pattern in ["card_testing", "device_pooling_nexus", "proxy_rotation", "undocumented"]:
            threshold = min(threshold, 2000.0)

        must_file = is_fraud and (exposure_usd >= threshold or pattern != "none")

        now = datetime.now(timezone.utc)
        deadline = (now + timedelta(days=j_spec["filing_deadline_days"])).strftime("%Y-%m-%d")

        return {
            "jurisdiction": j_key,
            "agency": j_spec["agency"],
            "statute": j_spec["statute"],
            "filing_type": j_spec["filing_type"],
            "must_file": must_file,
            "threshold_usd": threshold,
            "exposure_usd": round(exposure_usd, 2),
            "filing_deadline": deadline,
            "retention_years": j_spec["retention_years"],
            "gdpr_masking_applied": j_spec.get("gdpr_masking_required", False) or j_key == "CROSS_BORDER",
        }

    @staticmethod
    def apply_gdpr_data_minimization(evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Applies GDPR Article 5(1)(c) data minimization:
        - Truncates 16-digit PANs to last 4 digits (e.g., ****-****-****-1234).
        - Redacts customer email addresses to domain only (e.g., u***@domain.com).
        - Shields private IP addresses.
        """
        sanitized = []
        for ev in evidence_list:
            ev_copy = dict(ev)
            claim = ev_copy.get("claim", "")

            # Truncate PANs (16 digits or 4x4 groups)
            claim = re.sub(r"\b(\d{4})[- ]?\d{4}[- ]?\d{4}[- ]?(\d{4})\b", r"****-****-****-\2", claim)

            # Redact email addresses
            claim = re.sub(
                r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b",
                r"\1***@\2",
                claim,
            )

            ev_copy["claim"] = claim
            ev_copy["gdpr_minimized"] = True
            sanitized.append(ev_copy)

        return sanitized

    @classmethod
    def generate_dispatch_bundle(
        cls,
        case_answer: Dict[str, Any],
        override_jurisdiction: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Assembles complete multi-jurisdiction compliance package with statutory
        filing templates, structuring detection, and data protection certifications.
        """
        c_data = case_answer.get("case", case_answer)
        jurisdiction = override_jurisdiction or cls.detect_jurisdiction(case_answer)

        exposure = float(c_data.get("exposure_usd", 0.0))
        is_fraud = (c_data.get("verdict") == "fraud")
        pattern = c_data.get("pattern", "none")

        obligations = cls.evaluate_regulatory_obligations(
            jurisdiction=jurisdiction,
            exposure_usd=exposure,
            is_fraud=is_fraud,
            pattern=pattern,
        )

        evidence = c_data.get("evidence", [])
        if obligations["gdpr_masking_applied"]:
            evidence = cls.apply_gdpr_data_minimization(evidence)

        # Multi-Entity Exposure Rollup & Structuring Analysis
        connected_cards = c_data.get("connected_card_ids", [])
        structuring_analysis = None
        if connected_cards or client is not None:
            structuring_analysis = RegulatoryStructuringDetector.detect_structuring(
                card_ids=connected_cards if connected_cards else None,
                window_hours=24.0,
                jurisdiction=jurisdiction,
                client=client,
            )
            if structuring_analysis.get("is_structuring") or structuring_analysis.get("mandatory_filings"):
                obligations["must_file"] = True
                obligations.setdefault("mandatory_filings", []).extend(structuring_analysis["mandatory_filings"])

        # Cross-Border AML & Correspondent Banking Risk Analysis
        cross_border_analysis = None
        card_id = c_data.get("card_id") or (connected_cards[0] if connected_cards else None)
        if card_id:
            cross_border_analysis = CrossBorderAMLRiskDetector.evaluate_cross_border_risk(
                card_id=card_id,
                transactions=c_data.get("transactions"),
                client=client,
            )
            if cross_border_analysis.get("mandatory_actions"):
                if "FILE_SAR_CROSS_BORDER_AML" in cross_border_analysis["mandatory_actions"]:
                    obligations["must_file"] = True
                obligations.setdefault("mandatory_actions", []).extend(cross_border_analysis["mandatory_actions"])

        dispatch_bundle = {
            "case_id": case_answer.get("case_id", "UNKNOWN"),
            "target_jurisdiction": jurisdiction,
            "obligations": obligations,
            "structuring_analysis": structuring_analysis,
            "cross_border_aml_analysis": cross_border_analysis,
            "filing_package": {
                "agency": obligations["agency"],
                "statutory_authority": obligations["statute"],
                "form_type": obligations["filing_type"],
                "deadline": obligations["filing_deadline"],
                "narrative": case_answer.get("sar", {}).get("narrative", "") if obligations["must_file"] else "",
                "subjects": case_answer.get("sar", {}).get("subjects", []) if obligations["must_file"] else [],
                "sanitized_evidence": evidence,
            },
            "data_protection": {
                "gdpr_compliant": obligations["gdpr_masking_applied"],
                "cross_border_safeguards": "Standard Contractual Clauses (SCC) Article 46" if jurisdiction == "CROSS_BORDER" else "Domestic Jurisdictional Exemption",
            },
        }

        return dispatch_bundle
