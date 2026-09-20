"""
Case Event Stream Logger
Maintains a chronological, immutable event log for every step of an investigation.
Used to render the investigation timeline in the UI and answer files.
"""

from typing import List, Dict, Any
from datetime import datetime


class CaseEventLogger:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[Dict[str, Any]] = []

    def log_event(self, step_name: str, details: Dict[str, Any], actor: str = "agent"):
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "case_id": self.case_id,
            "step": step_name,
            "timestamp": ts,
            "actor": actor,
            "details": details,
        }
        self.events.append(entry)
        return entry

    def get_timeline(self) -> List[Dict[str, Any]]:
        return self.events
