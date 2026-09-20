"""
Policy & Regulatory Chunking Module (GraphRAG)
Chunks bank fraud policy, regulatory guidelines (FinCEN, FATF), and fraud typology signatures
into structured knowledge units with stable chunk IDs for grounding and citations.
"""

from typing import List, Dict, Any


class PolicyChunker:
    @staticmethod
    def get_policy_chunks() -> List[Dict[str, Any]]:
        chunks = [
            {
                "id": "POLICY-R1",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R1: Verify Before Block on Weak Signal",
                "text": "If the case rests on a single signal (including a risk score alone) and assessed fraud probability is below 0.70, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate customer on one signal is a policy breach.",
                "keywords": ["verify", "single signal", "risk score alone", "weak signal", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH", "below 0.70"],
            },
            {
                "id": "POLICY-R2",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R2: Customer Denies Transaction",
                "text": "When customer denies the transaction, recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud.",
                "keywords": ["customer denies", "unauthorized", "BLOCK_CARD", "CREATE_CASE", "FILE_REPORT", "exposure over 1000", "shared device"],
            },
            {
                "id": "POLICY-R3",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R3: Customer Confirms Transaction",
                "text": "When customer confirms the transaction, recommend CLOSE_NO_FRAUD. Note the confirmation in the case file.",
                "keywords": ["customer confirms", "CLOSE_NO_FRAUD", "legitimate", "false alarm", "confirmed by customer"],
            },
            {
                "id": "POLICY-R4",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R4: No Customer Reply within 24 Hours",
                "text": "If no reply within 24 hours to customer verification, recommend MONITOR_CARD and DECLINE_TRANSACTION for pending authorizations. Escalate to analyst if exposure exceeds $500.",
                "keywords": ["no reply", "24 hours", "MONITOR_CARD", "DECLINE_TRANSACTION", "escalate over 500"],
            },
            {
                "id": "POLICY-R5",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R5: Card Testing Sequence",
                "text": "Three or more small online authorizations on one card within an hour, followed by a larger purchase: recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a purchase over $100 has already cleared, recommend BLOCK_CARD.",
                "keywords": ["card testing", "small authorizations", "sub-$5", "rapid sequence", "DECLINE_TRANSACTION", "STEP_UP_AUTH", "BLOCK_CARD", "over $100 cleared"],
            },
            {
                "id": "POLICY-R6",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R6: Shared Origin & Connected Ring",
                "text": "When several cards show fraud from the same device profile, the same billing region, or the same recipient email in one window, name the shared element, recommend CREATE_CASE and FILE_REPORT, and MONITOR_CONNECTED_CARDS for every card that shares it.",
                "keywords": ["shared origin", "shared device", "same billing region", "CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS", "fraud ring"],
            },
            {
                "id": "POLICY-R7",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R7: Disputed but Recurring / Legitimate",
                "text": "When the customer disputes a charge that matches their own recurring pattern (same merchant, same amount, monthly), recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, and WARN_CUSTOMER. Do not block.",
                "keywords": ["disputed recurring", "subscription", "monthly charge", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "do not block"],
            },
            {
                "id": "POLICY-R8",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R8: Escalate When Uncertain and Exposed",
                "text": "If the verdict is uncertain and exposure exceeds $500, or the evidence conflicts, recommend ESCALATE_TO_ANALYST.",
                "keywords": ["uncertain", "conflicting evidence", "exposure over 500", "ESCALATE_TO_ANALYST"],
            },
            {
                "id": "POLICY-R9",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R9: Undocumented Coordinated Patterns",
                "text": "When activity fits none of the known patterns but the evidence shows coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST, and describe the pattern in your own words. Do not force it into a known category.",
                "keywords": ["undocumented pattern", "coordinated abuse", "multi-customer", "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST"],
            },
            {
                "id": "POLICY-R10",
                "doc": "FraudPolicy",
                "section": "Rules",
                "title": "Rule R10: Restrictions on BLOCK_ALL_CARDS",
                "text": "Never recommend BLOCK_ALL_CARDS unless at least two of the customer's cards show confirmed fraud or the customer's credentials are confirmed compromised. Approval route is always L2.",
                "keywords": ["BLOCK_ALL_CARDS", "two cards confirmed", "credentials compromised", "L2 route"],
            },
            {
                "id": "POLICY-3A-SAR",
                "doc": "FraudPolicy",
                "section": "SAR Filing Criteria",
                "title": "Section 3a: Suspicious Activity Report (SAR) Criteria",
                "text": "A SAR (FILE_REPORT) is a regulatory filing sent outside the bank. File one when fraud is confirmed or strongly suspected AND at least one of these holds: exposure exceeds $1,000; activity connects to a shared device profile or region cluster; or the pattern is coordinated/undocumented (R9). Route is always L2.",
                "keywords": ["SAR", "FILE_REPORT", "exposure exceeds 1000", "shared device profile", "regulatory filing", "L2"],
            },
            {
                "id": "POLICY-APPROVALS",
                "doc": "FraudPolicy",
                "section": "Approval Routing",
                "title": "Section 2: Approval Routes (auto, L1, L2)",
                "text": "auto: ALLOW_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER, VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, CREATE_CASE, ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD. L1 (Team Lead): DECLINE_TRANSACTION, BLOCK_CARD when exposure <= $2,500. L2 (Fraud Manager): BLOCK_CARD when exposure > $2,500, BLOCK_ALL_CARDS always, FILE_REPORT always.",
                "keywords": ["approval route", "auto", "L1", "L2", "team lead", "fraud manager", "threshold 2500"],
            },
            {
                "id": "REG-FINCEN-SAR",
                "doc": "FinCEN Guidance",
                "section": "SAR Narrative",
                "title": "FinCEN SAR Narrative Standard (Who, What, When, Where, How, Why)",
                "text": "A complete SAR narrative must stand on its own and clearly articulate the five essential elements: Who conducted or was affected by the activity (customers, cards, devices); What transactions occurred; When the activity took place (dates/times); Where it happened (billing regions, online vs in-person channels); How it was executed; and Why it is suspicious based on bank policies.",
                "keywords": ["FinCEN", "SAR Narrative", "Who What When Where How Why", "regulatory compliance", "suspicious activity"],
            },
            {
                "id": "TYP-CARD-TESTING",
                "doc": "FraudTypologies",
                "section": "Typologies",
                "title": "Pattern 1: Card Testing Signature",
                "text": "A stolen card number is checked before use: three or more tiny online authorizations, often under $5, then a larger purchase. Confirmed by the sequence itself. Governed by Policy R5.",
                "keywords": ["card_testing", "tiny auths", "under $5", "testing stolen card", "Policy R5"],
            },
            {
                "id": "TYP-CNP-NEW-DEV",
                "doc": "FraudTypologies",
                "section": "Typologies",
                "title": "Pattern 3: Card-Not-Present New Device",
                "text": "Online transactions with identity record marking the device as New for this account, sometimes behind an anonymous proxy. Inconsistent with cardholder habit. Stronger than general CNP.",
                "keywords": ["card_not_present_new_device", "new device", "anonymous proxy", "id_15 New", "proxy flag"],
            },
            {
                "id": "TYP-OUT-OF-REGION",
                "doc": "FraudTypologies",
                "section": "Typologies",
                "title": "Pattern 4: Out of Region Use",
                "text": "Card-present purchases in a billing region the cardholder has no history in, while normal activity continues at home. Several days in one new region indicates travel; isolated distant purchases indicate clone. Policy R2, R3.",
                "keywords": ["out_of_region_use", "billing region", "addr1", "card-present", "travel", "cloned card"],
            },
            {
                "id": "TYP-ACCOUNT-TAKEOVER",
                "doc": "FraudTypologies",
                "section": "Typologies",
                "title": "Pattern 5: Account Takeover",
                "text": "Mixed-channel activity inconsistent with the cardholder, with device and match-flag anomalies, pointing to stolen credentials rather than a stolen card number alone.",
                "keywords": ["account_takeover", "ATO", "credential theft", "mixed-channel", "match flag anomaly"],
            },
            {
                "id": "TYP-DISCOVERED-PROXY-ROT",
                "doc": "DiscoveredTypologies",
                "section": "Discovered",
                "title": "Pattern 6: Discovered Coordinated Proxy Rotation",
                "text": "Multiple distinct cards compromised from the identical device build behind rotating anonymous proxies within a 30-day window. Fits Rule R6 and R9 for cross-customer coordination.",
                "keywords": ["multi_card_proxy_rotation", "undocumented", "discovered", "cross-customer coordination", "proxy rotation"],
            },
            {
                "id": "TYP-DISCOVERED-DEVICE-POOL",
                "doc": "DiscoveredTypologies",
                "section": "Discovered",
                "title": "Pattern 7: Discovered Device Pooling Nexus",
                "text": "Hardware fingerprint or device profile linked to multiple independent card accounts across three or more cardholders. Indicates device pooling nexus used by fraud operations for testing and liquidation. Governed by Policy R6 and R9.",
                "keywords": ["device_pooling_nexus", "device pooling", "device nexus", "multiple cards", "unrelated cards", "hardware fingerprint", "shared device pool"],
            },
            {
                "id": "TYP-RAPID-DISPERSION",
                "doc": "DiscoveredTypologies",
                "section": "Discovered",
                "title": "Pattern 8: Discovered Rapid Geographical Dispersion",
                "text": "Rapid multi-regional dispersion with impossible travel velocity hops across non-contiguous billing regions within tight time windows, indicating distributed counterfeit card relay or skimming ring. Governed by Policy R2, R6, and R9.",
                "keywords": ["rapid_geo_dispersion", "rapid geographical dispersion", "impossible travel velocity", "geo dispersion", "multi regional hops", "counterfeit relay"],
            },
        ]
        return chunks
