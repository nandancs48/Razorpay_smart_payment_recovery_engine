from datetime import datetime, timezone
from typing import Dict, Any, List
import database

class AuditLogger:
    @staticmethod
    def log_step(order_id: str, stage: str, data: Dict[str, Any]):
        """Persist a single step in the audit trail."""
        database.save_audit_log(order_id, stage, data)

    @staticmethod
    def get_full_trail(order_id: str) -> Dict[str, Any]:
        """Fetch the full chronological audit trail formatted for presentation."""
        raw_trail = database.get_audit_trail(order_id)
        return {
            "order_id": order_id,
            "total_steps": len(raw_trail),
            "steps": raw_trail
        }
