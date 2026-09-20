"""
Answer Schema Validator
Strictly validates all 20 benchmark case output JSON files in cases/ against
the specification defined in docs/answer_format.md.
"""

import os
import sys
import json
import re
from typing import Dict, Any, List

ALLOWED_VERDICTS = {"fraud", "legitimate", "uncertain"}
ALLOWED_STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
ALLOWED_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
}
ALLOWED_SOURCES = {"graph", "document", "customer", "external"}
ALLOWED_ROUTES = {"auto", "L1", "L2"}
ALLOWED_ACTIONS = {
    "ALLOW_TRANSACTION",
    "DECLINE_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
}


def validate_single_answer(data: Dict[str, Any], case_id: str) -> List[str]:
    errors = []

    # 1. Top-Level Keys
    top_keys = ["case_id", "case", "evidence_requests", "next_best_actions", "sar", "stop_reason", "tool_calls", "tokens", "latency_s"]
    for k in top_keys:
        if k not in data:
            errors.append(f"Missing top-level key: '{k}'")

    if errors:
        return errors

    if data["case_id"] != case_id:
        errors.append(f"Mismatch case_id: expected '{case_id}', got '{data['case_id']}'")

    if not isinstance(data["tool_calls"], int) or data["tool_calls"] < 0:
        errors.append(f"Invalid tool_calls count: {data['tool_calls']}")
    if not isinstance(data["tokens"], int) or data["tokens"] <= 0:
        errors.append(f"Invalid tokens count: {data['tokens']}")
    if not isinstance(data["latency_s"], (int, float)) or data["latency_s"] < 0:
        errors.append(f"Invalid latency_s: {data['latency_s']}")
    if not isinstance(data["stop_reason"], str) or not data["stop_reason"].strip():
        errors.append("stop_reason must be a non-empty string")

    # 2. Case Object
    c = data["case"]
    case_keys = [
        "status", "verdict", "fraud_probability", "pattern", "pattern_description",
        "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
        "connected_device_profiles", "exposure_usd", "evidence", "similar_prior_cases",
        "summary", "written_to_graph", "graph_case_id"
    ]
    for k in case_keys:
        if k not in c:
            errors.append(f"Missing case key: '{k}'")

    if c.get("verdict") not in ALLOWED_VERDICTS:
        errors.append(f"Invalid case verdict: '{c.get('verdict')}'")

    if c.get("status") not in ALLOWED_STATUSES:
        errors.append(f"Invalid case status: '{c.get('status')}'")

    prob = c.get("fraud_probability")
    if not isinstance(prob, (int, float)) or not (0.0 <= prob <= 1.0):
        errors.append(f"fraud_probability must be a float between 0.0 and 1.0, got: {prob}")

    pat = c.get("pattern")
    if pat not in ALLOWED_PATTERNS:
        errors.append(f"Invalid pattern: '{pat}'")
    if pat == "undocumented" and not c.get("pattern_description"):
        errors.append("pattern_description is required when pattern is 'undocumented'")

    if not isinstance(c.get("affected_txn_ids"), list):
        errors.append("affected_txn_ids must be a list")
    if not isinstance(c.get("connected_card_ids"), list):
        errors.append("connected_card_ids must be a list")
    if not isinstance(c.get("connected_device_profiles"), list):
        errors.append("connected_device_profiles must be a list")
    if not isinstance(c.get("similar_prior_cases"), list):
        errors.append("similar_prior_cases must be a list")

    exp = c.get("exposure_usd")
    if not isinstance(exp, (int, float)) or exp < 0:
        errors.append(f"exposure_usd must be a non-negative float, got: {exp}")

    if c.get("verdict") == "legitimate":
        if c.get("exposure_usd") != 0.0:
            errors.append(f"Legitimate cases must have exposure_usd == 0.0, got: {exp}")
        if len(c.get("affected_txn_ids", [])) > 0:
            errors.append(f"Legitimate cases must have empty affected_txn_ids, got: {c.get('affected_txn_ids')}")
        if c.get("first_suspicious_txn_id") != "":
            errors.append(f"Legitimate cases must have empty first_suspicious_txn_id, got: {c.get('first_suspicious_txn_id')}")

    if not c.get("summary") or len(c.get("summary").strip()) < 10:
        errors.append("case summary must be an informative string (at least 10 chars)")

    if c.get("written_to_graph") is not True:
        errors.append(f"written_to_graph must be True, got {c.get('written_to_graph')}")
    if not c.get("graph_case_id"):
        errors.append("graph_case_id must be non-empty")

    # Evidence items
    evidence = c.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) == 0:
        errors.append("evidence list must not be empty")
    for idx, ev in enumerate(evidence):
        for ek in ["claim", "source", "ref", "entity_ids"]:
            if ek not in ev:
                errors.append(f"evidence[{idx}] missing '{ek}'")
        if ev.get("source") not in ALLOWED_SOURCES:
            errors.append(f"evidence[{idx}] invalid source '{ev.get('source')}'")

    # 3. SAR Object
    sar = data["sar"]
    for sk in ["file", "reason", "narrative", "subjects", "total_amount_usd", "activity_dates"]:
        if sk not in sar:
            errors.append(f"sar missing '{sk}'")

    if not isinstance(sar.get("file"), bool):
        errors.append(f"sar.file must be a boolean, got: {type(sar.get('file'))}")

    if sar.get("file") is True:
        if not sar.get("narrative") or len(sar.get("narrative").strip()) < 20:
            errors.append("sar.narrative must be non-empty and detailed when file == True")
        if not sar.get("subjects") or len(sar.get("subjects")) == 0:
            errors.append("sar.subjects must list affected entities when file == True")
        if sar.get("total_amount_usd", 0.0) <= 0:
            errors.append(f"sar.total_amount_usd must be > 0 when file == True, got: {sar.get('total_amount_usd')}")
        if not sar.get("activity_dates") or len(sar.get("activity_dates")) == 0:
            errors.append("sar.activity_dates must contain dates when file == True")
    else:
        if sar.get("narrative") != "":
            errors.append("sar.narrative must be empty string when file == False")
        if len(sar.get("subjects", [])) > 0:
            errors.append("sar.subjects must be empty when file == False")

    # 4. Next Best Actions Object
    nba = data["next_best_actions"]
    for nk in ["initial", "final", "what_changed"]:
        if nk not in nba:
            errors.append(f"next_best_actions missing '{nk}'")

    for list_name in ["initial", "final"]:
        act_list = nba.get(list_name, [])
        if not isinstance(act_list, list) or len(act_list) == 0:
            errors.append(f"next_best_actions.{list_name} must be a non-empty list")
        for idx, act in enumerate(act_list):
            for ak in ["action", "route", "reason"]:
                if ak not in act:
                    errors.append(f"{list_name}[{idx}] missing '{ak}'")
            if act.get("action") not in ALLOWED_ACTIONS:
                errors.append(f"{list_name}[{idx}] unknown action '{act.get('action')}'")
            if act.get("route") not in ALLOWED_ROUTES:
                errors.append(f"{list_name}[{idx}] unknown route '{act.get('route')}'")

    # Policy consistency: FILE_REPORT in final actions <=> sar.file == True
    has_file_report = any(a.get("action") == "FILE_REPORT" for a in nba.get("final", []))
    if has_file_report != sar.get("file"):
        errors.append(
            f"Inconsistency: FILE_REPORT in actions is {has_file_report}, but sar.file is {sar.get('file')}"
        )

    # 5. Evidence Requests
    ev_reqs = data["evidence_requests"]
    if not isinstance(ev_reqs, list):
        errors.append("evidence_requests must be a list")
    for idx, er in enumerate(ev_reqs):
        for erk in ["type", "asked_after_step", "assumed_response"]:
            if erk not in er:
                errors.append(f"evidence_requests[{idx}] missing '{erk}'")
        if er.get("type") not in {"customer_validation", "step_up_auth", "analyst_info"}:
            errors.append(f"evidence_requests[{idx}] unknown type '{er.get('type')}'")

    return errors


def validate_all_cases(cases_dir: str = "cases") -> bool:
    print(f"============================================================")
    print(f" TIGERGRAPH AGENTIC FRAUD INVESTIGATOR: SCHEMA VALIDATOR")
    print(f" Scanning directory: {cases_dir}")
    print(f"============================================================\n")

    if not os.path.exists(cases_dir):
        print(f"ERROR: Directory '{cases_dir}' does not exist.")
        return False

    total_valid = 0
    total_errors = 0

    for i in range(1, 21):
        case_id = f"HHG-{i:03d}"
        file_path = os.path.join(cases_dir, f"{case_id}.json")
        
        if not os.path.exists(file_path):
            print(f"[FAIL] {case_id}: File not found at {file_path}")
            total_errors += 1
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[FAIL] {case_id}: JSON parse error: {e}")
            total_errors += 1
            continue

        errs = validate_single_answer(data, case_id)
        if errs:
            print(f"[FAIL] {case_id}: {len(errs)} schema error(s):")
            for err in errs:
                print(f"   - {err}")
            total_errors += 1
        else:
            print(f"[PASS] {case_id}: Strictly conforms to answer_format.md")
            total_valid += 1

    print(f"\n------------------------------------------------------------")
    print(f"RESULTS: {total_valid}/20 Passed, {total_errors}/20 Failed.")
    print(f"------------------------------------------------------------")
    return total_errors == 0


if __name__ == "__main__":
    success = validate_all_cases()
    sys.exit(0 if success else 1)
