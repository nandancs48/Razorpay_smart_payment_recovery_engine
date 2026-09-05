import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from config import BASELINE_CONVERSION_RATES
import database
from pipeline.audit_logger import AuditLogger

def record_payment_success(order_id: str, payment_id: Optional[str] = None, source: str = "webhook") -> bool:
    """Updates database and logs audit trail when payment is captured/paid."""
    payment = database.get_payment(order_id)
    if not payment:
        return False
        
    now = datetime.now(timezone.utc).isoformat()
    database.update_payment(
        order_id,
        status="recovered",
        recovered_at=now,
        payment_id=payment_id or payment.get("payment_id")
    )
    
    AuditLogger.log_step(order_id, "tracked", {
        "outcome": "recovered",
        "amount_recovered": payment["amount"],
        "source": source,
        "recovered_at": now,
        "detail": "Customer successfully completed payment via recovery link"
    })
    return True

def simulate_customer_response(payment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates realistic customer payment response based on root failure cause.
    Maintains realistic variance (35-55% aggregate conversion) so demos look authentic.
    """
    reason = payment.get("diagnosed_reason", "bank_server_down")
    base_rate = BASELINE_CONVERSION_RATES.get(reason, 0.40)
    
    order_id = payment["order_id"]
    is_success = random.random() < base_rate
    now = datetime.now(timezone.utc).isoformat()
    
    if is_success:
        database.update_payment(order_id, status="recovered", recovered_at=now)
        AuditLogger.log_step(order_id, "tracked", {
            "outcome": "recovered",
            "amount_recovered": payment["amount"],
            "source": "simulated_customer_action",
            "recovered_at": now,
            "detail": f"Customer responded to {payment.get('recovery_action')} and paid ₹{payment['amount']}"
        })
        payment["status"] = "recovered"
    else:
        # Non-recovered: check if we give up or keep pending
        attempt_count = payment.get("attempt_count", 1)
        if attempt_count >= 3:
            outcome = "abandoned"
            database.update_payment(order_id, status="abandoned", stopped_reason="customer_unresponsive")
            AuditLogger.log_step(order_id, "tracked", {
                "outcome": "abandoned",
                "detail": "Customer did not convert after maximum recovery attempts. Sale lost."
            })
            payment["status"] = "abandoned"
        else:
            outcome = "retrying"
            AuditLogger.log_step(order_id, "tracked", {
                "outcome": "pending_cooldown",
                "detail": "No payment received yet. Awaiting cooldown before potential next retry."
            })
            payment["status"] = "retrying"
            
    return payment
