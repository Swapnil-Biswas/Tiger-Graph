"""
Mock Actions Execution API
Stubs downstream core banking integrations (card blocks, transaction declines,
customer messaging, CRM case progression, and regulatory SAR filings).
"""

from typing import Dict, Any, List
from datetime import datetime


class MockActionsAPI:
    def __init__(self):
        self.execution_log: List[Dict[str, Any]] = []

    def execute(self, action: str, target_id: str, payload: Dict[str, Any] = None, approver: str = "AutomatedAgent") -> Dict[str, Any]:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "action": action,
            "target_id": target_id,
            "status": "executed",
            "approver": approver,
            "timestamp": ts,
            "payload": payload or {},
            "simulated": True,
        }
        self.execution_log.append(entry)
        return {
            "success": True,
            "message": f"Action {action} executed successfully on {target_id}",
            "record": entry,
        }

    def get_history(self, target_id: str = None) -> List[Dict[str, Any]]:
        if target_id:
            return [e for e in self.execution_log if e["target_id"] == target_id]
        return self.execution_log
