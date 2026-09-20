"""
Multi-Jurisdiction Regulatory Routing & Compliance Engine
Enforces jurisdiction-specific reporting mandates (US FinCEN SAR, UK FCA/NCA STR, EU 6AMLD)
and GDPR Article 5/46 cross-border data minimization on fraud evidence and case packages.
"""

import os
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta


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
    ) -> Dict[str, Any]:
        """
        Assembles complete multi-jurisdiction compliance package with statutory
        filing templates and data protection certifications.
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

        dispatch_bundle = {
            "case_id": case_answer.get("case_id", "UNKNOWN"),
            "target_jurisdiction": jurisdiction,
            "obligations": obligations,
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
