"""
Automated FinCEN Form 111 XML/ASCII Electronic Filing Validator & Regulatory Transmission Packager
(src/cases/sar_exporter.py)

Conforms to FinCEN BSA Electronic Filing Requirements (XML Schema 2.0)
for Depository Institutions Suspicious Activity Reports (SAR - FinCEN Form 111).
Validates mandatory statutory fields, formats 5-part narratives, and compiles transmission digests.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import hashlib
import re


@dataclass
class FinCENValidationIssue:
    field: str
    severity: str  # "CRITICAL", "WARNING"
    message: str


@dataclass
class FinCENValidationReport:
    is_valid: bool
    total_issues: int
    critical_errors: List[FinCENValidationIssue]
    warnings: List[FinCENValidationIssue]
    bsa_identifier: str
    submission_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_issues": self.total_issues,
            "critical_errors": [{"field": i.field, "severity": i.severity, "message": i.message} for i in self.critical_errors],
            "warnings": [{"field": i.field, "severity": i.severity, "message": i.message} for i in self.warnings],
            "bsa_identifier": self.bsa_identifier,
            "submission_timestamp": self.submission_timestamp,
        }


class FinCENSARXMLPackager:
    """
    Constructs and validates FinCEN BSA E-Filing XML 2.0 documents for suspicious activity reports.
    """

    XML_NAMESPACE = "http://www.fincen.gov/base"
    SCHEMA_VERSION = "2.0"
    INSTITUTION_NAME = "Apex Federal Savings Bank"
    INSTITUTION_TIN = "12-3456789"
    INSTITUTION_RSSD = "987654"
    PRIMARY_REGULATOR = "OCC"

    def __init__(self):
        pass

    def generate_sar_xml(self, case_bundle: Dict[str, Any]) -> str:
        """
        Converts an agent investigation bundle into a valid FinCEN XML 2.0 document.
        """
        case_id = case_bundle.get("case_id", "UNKNOWN")
        c_data = case_bundle.get("case", {})
        sar_data = case_bundle.get("sar", {})
        exposure_usd = float(c_data.get("exposure_usd", 0.0))
        pattern = c_data.get("pattern", "card_fraud")
        summary = c_data.get("summary", "")

        now_utc = datetime.now(timezone.utc)
        timestamp_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        date_str = now_utc.strftime("%Y%m%d")

        # Deterministic BSA Document Identifier
        bsa_raw = f"BSA-{case_id}-{date_str}"
        bsa_id = hashlib.sha256(bsa_raw.encode("utf-8")).hexdigest()[:14].upper()

        # Build XML Hierarchy
        root = ET.Element("fc2:SuspiciousActivityReport", {
            "xmlns:fc2": self.XML_NAMESPACE,
            "version": self.SCHEMA_VERSION,
            "DocumentIdentifier": f"BSA_{bsa_id}",
        })

        # Activity Header
        activity = ET.SubElement(root, "fc2:Activity")
        ET.SubElement(activity, "fc2:EFilingPriorDocumentNumber").text = "00000000000000"
        ET.SubElement(activity, "fc2:FilingDateText").text = date_str
        ET.SubElement(activity, "fc2:ActivityType").text = "SAR"

        # Part I: Subject Information (ActivityParty)
        customer_id = str(c_data.get("customer_id") or "UNKNOWN")
        card_id = str(c_data.get("card_id") or "UNKNOWN")

        subj_party = ET.SubElement(activity, "fc2:ActivityParty", {"PartyType": "Subject"})
        ET.SubElement(subj_party, "fc2:IndividualEntityIdentifier").text = customer_id
        ET.SubElement(subj_party, "fc2:PartyName").text = f"Subject Associated with {card_id}"
        ET.SubElement(subj_party, "fc2:AccountNumber").text = card_id
        ET.SubElement(subj_party, "fc2:PartyRole").text = "Suspect"

        # Part II: Suspicious Activity Information
        susp_act = ET.SubElement(activity, "fc2:SuspiciousActivity")
        ET.SubElement(susp_act, "fc2:SuspiciousActivityAmountText").text = f"{int(round(exposure_usd))}"
        ET.SubElement(susp_act, "fc2:SuspiciousActivityFromDateText").text = date_str
        ET.SubElement(susp_act, "fc2:SuspiciousActivityToDateText").text = date_str

        # Suspicious Categories / Violation Checkboxes
        cat_elem = ET.SubElement(susp_act, "fc2:SuspiciousActivityCategory")
        if "structuring" in pattern.lower():
            ET.SubElement(cat_elem, "fc2:CategoryCode").text = "STRUCTURING"
            ET.SubElement(cat_elem, "fc2:CategoryDescription").text = "31 CFR 1010.314 - Structuring to Evade Reporting"
        elif "ring" in pattern.lower() or "syndicate" in pattern.lower() or "device" in pattern.lower():
            ET.SubElement(cat_elem, "fc2:CategoryCode").text = "ORGANIZED_CRIME_SYNDICATE"
            ET.SubElement(cat_elem, "fc2:CategoryDescription").text = "Multi-Card Coordinated Fraud Ring"
        elif "test" in pattern.lower() or "burst" in pattern.lower():
            ET.SubElement(cat_elem, "fc2:CategoryCode").text = "CARD_TESTING_BOT"
            ET.SubElement(cat_elem, "fc2:CategoryDescription").text = "High-Velocity Automated Card Testing"
        else:
            ET.SubElement(cat_elem, "fc2:CategoryCode").text = "CREDIT_DEBIT_FRAUD"
            ET.SubElement(cat_elem, "fc2:CategoryDescription").text = "Unauthorized Payment Card Transactions"

        # Part III: Filing Institution Information
        inst_party = ET.SubElement(activity, "fc2:ActivityParty", {"PartyType": "FilingInstitution"})
        ET.SubElement(inst_party, "fc2:PartyName").text = self.INSTITUTION_NAME
        ET.SubElement(inst_party, "fc2:PartyTIN").text = self.INSTITUTION_TIN
        ET.SubElement(inst_party, "fc2:PartyRSSD").text = self.INSTITUTION_RSSD
        ET.SubElement(inst_party, "fc2:FederalRegulatorCode").text = self.PRIMARY_REGULATOR

        # Part V: Narrative Information (Five-Part Narrative strictly <= 17,000 chars)
        narrative_elem = ET.SubElement(activity, "fc2:NarrativeInformation")
        narrative_text = sar_data.get("narrative") or self._build_default_narrative(case_bundle)
        # FinCEN limit is 17,000 characters
        ET.SubElement(narrative_elem, "fc2:NarrativeText").text = narrative_text[:17000]

        # Pretty-print XML
        raw_xml = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(raw_xml)
        return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    def _build_default_narrative(self, case_bundle: Dict[str, Any]) -> str:
        """Constructs statutory 5-part narrative: Who, What, When, Where, Why/How."""
        case_id = case_bundle.get("case_id", "UNKNOWN")
        c_data = case_bundle.get("case", {})
        summary = c_data.get("summary", "")
        exposure = c_data.get("exposure_usd", 0.0)
        pattern = c_data.get("pattern", "Unknown")

        lines = [
            f"SUSPICIOUS ACTIVITY REPORT - CASE {case_id}",
            "PART V - NARRATIVE SUMMARY",
            "",
            "1. WHO IS CONDUCTING THE ACTIVITY:",
            f"Primary customer/card identifier: {c_data.get('card_id', 'UNKNOWN')} / Customer {c_data.get('customer_id', 'UNKNOWN')}.",
            f"Connected cards in syndicate ring: {', '.join(c_data.get('connected_card_ids', [])) or 'None'}.",
            "",
            "2. WHAT TRANSACTIONS OCCURRED:",
            f"Total suspicious exposure amount: ${exposure:,.2f} USD.",
            f"Primary fraud typology detected: {pattern.upper()}.",
            f"First flagged transaction: {c_data.get('first_suspicious_txn_id', 'N/A')}.",
            "",
            "3. WHEN DID THE ACTIVITY TAKE PLACE:",
            f"Investigation concluded: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            "",
            "4. WHERE DID THE ACTIVITY OCCUR:",
            f"Reported by {self.INSTITUTION_NAME} (RSSD: {self.INSTITUTION_RSSD}).",
            f"Device hardware profiles: {', '.join(c_data.get('connected_device_profiles', [])) or 'Standard E-Commerce Gateway'}.",
            "",
            "5. WHY AND HOW THE ACTIVITY IS SUSPICIOUS:",
            summary or "Transaction flow pattern deviates significantly from baseline consumer profile and exhibits syndicate contagion.",
            "Statutory Grounding: 31 CFR 1020.320, 18 U.S.C. § 1956.",
        ]
        return "\n".join(lines)

    def validate_sar_xml(self, xml_content: str) -> FinCENValidationReport:
        """
        Validates FinCEN XML document against 12 mandatory BSA E-Filing criteria.
        """
        critical_errors: List[FinCENValidationIssue] = []
        warnings: List[FinCENValidationIssue] = []
        bsa_id = "UNKNOWN"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            critical_errors.append(FinCENValidationIssue(
                field="XML_STRUCTURE",
                severity="CRITICAL",
                message=f"XML Parsing Error: {str(e)}",
            ))
            return FinCENValidationReport(
                is_valid=False,
                total_issues=1,
                critical_errors=critical_errors,
                warnings=warnings,
                bsa_identifier="MALFORMED_XML",
                submission_timestamp=now_str,
            )

        # 1. Check Root Element & Namespace
        if not root.tag.endswith("SuspiciousActivityReport"):
            critical_errors.append(FinCENValidationIssue(
                field="ROOT_ELEMENT",
                severity="CRITICAL",
                message=f"Root element must be 'SuspiciousActivityReport', found '{root.tag}'",
            ))

        bsa_id = root.attrib.get("DocumentIdentifier", "MISSING_DOC_ID")
        if bsa_id == "MISSING_DOC_ID":
            critical_errors.append(FinCENValidationIssue(
                field="DocumentIdentifier",
                severity="CRITICAL",
                message="Missing mandatory DocumentIdentifier attribute in root tag.",
            ))

        # 2. Activity Element
        activity = None
        for child in root:
            if child.tag.endswith("Activity"):
                activity = child
                break

        if activity is None:
            critical_errors.append(FinCENValidationIssue(
                field="Activity",
                severity="CRITICAL",
                message="Missing mandatory <fc2:Activity> container element.",
            ))
            return FinCENValidationReport(
                is_valid=False,
                total_issues=len(critical_errors),
                critical_errors=critical_errors,
                warnings=warnings,
                bsa_identifier=bsa_id,
                submission_timestamp=now_str,
            )

        # 3. Filing Date Text
        filing_date = None
        for elem in activity:
            if elem.tag.endswith("FilingDateText"):
                filing_date = elem.text
                break
        if not filing_date or len(filing_date) != 8 or not filing_date.isdigit():
            critical_errors.append(FinCENValidationIssue(
                field="FilingDateText",
                severity="CRITICAL",
                message=f"FilingDateText must be YYYYMMDD format (8 digits), found '{filing_date}'",
            ))

        # 4. Subject Party
        subj_found = False
        inst_found = False
        for elem in activity:
            if elem.tag.endswith("ActivityParty"):
                ptype = elem.attrib.get("PartyType")
                if ptype == "Subject":
                    subj_found = True
                    # Validate subject account / name
                    has_acc = any(c.tag.endswith("AccountNumber") and c.text for c in elem)
                    if not has_acc:
                        warnings.append(FinCENValidationIssue(
                            field="Subject.AccountNumber",
                            severity="WARNING",
                            message="Subject ActivityParty does not specify an AccountNumber.",
                        ))
                elif ptype == "FilingInstitution":
                    inst_found = True
                    has_tin = any(c.tag.endswith("PartyTIN") and c.text for c in elem)
                    if not has_tin:
                        critical_errors.append(FinCENValidationIssue(
                            field="FilingInstitution.PartyTIN",
                            severity="CRITICAL",
                            message="FilingInstitution must specify a valid PartyTIN (EIN).",
                        ))

        if not subj_found:
            critical_errors.append(FinCENValidationIssue(
                field="ActivityParty(Subject)",
                severity="CRITICAL",
                message="Missing mandatory Subject ActivityParty in Part I.",
            ))
        if not inst_found:
            critical_errors.append(FinCENValidationIssue(
                field="ActivityParty(FilingInstitution)",
                severity="CRITICAL",
                message="Missing mandatory FilingInstitution ActivityParty in Part III.",
            ))

        # 5. Suspicious Activity Amount & Category
        susp_found = False
        for elem in activity:
            if elem.tag.endswith("SuspiciousActivity"):
                susp_found = True
                amt = None
                for c in elem:
                    if c.tag.endswith("SuspiciousActivityAmountText"):
                        amt = c.text
                if not amt or not amt.isdigit() or int(amt) < 0:
                    critical_errors.append(FinCENValidationIssue(
                        field="SuspiciousActivityAmountText",
                        severity="CRITICAL",
                        message=f"SuspiciousActivityAmountText must be a non-negative whole dollar integer, found '{amt}'",
                    ))

        if not susp_found:
            critical_errors.append(FinCENValidationIssue(
                field="SuspiciousActivity",
                severity="CRITICAL",
                message="Missing mandatory <fc2:SuspiciousActivity> section.",
            ))

        # 6. Narrative Information
        narrative_found = False
        for elem in activity:
            if elem.tag.endswith("NarrativeInformation"):
                for c in elem:
                    if c.tag.endswith("NarrativeText"):
                        narrative_found = True
                        ntext = c.text or ""
                        if len(ntext.strip()) < 50:
                            critical_errors.append(FinCENValidationIssue(
                                field="NarrativeText",
                                severity="CRITICAL",
                                message="NarrativeText must contain at least 50 characters of explanatory detail.",
                            ))
                        if len(ntext) > 17000:
                            critical_errors.append(FinCENValidationIssue(
                                field="NarrativeText",
                                severity="CRITICAL",
                                message=f"NarrativeText exceeds FinCEN 17,000 character limit (length: {len(ntext)}).",
                            ))

        if not narrative_found:
            critical_errors.append(FinCENValidationIssue(
                field="NarrativeInformation",
                severity="CRITICAL",
                message="Missing mandatory Part V <fc2:NarrativeInformation>.",
            ))

        total_issues = len(critical_errors) + len(warnings)
        is_valid = len(critical_errors) == 0

        return FinCENValidationReport(
            is_valid=is_valid,
            total_issues=total_issues,
            critical_errors=critical_errors,
            warnings=warnings,
            bsa_identifier=bsa_id,
            submission_timestamp=now_str,
        )
