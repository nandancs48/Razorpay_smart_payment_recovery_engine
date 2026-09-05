from datetime import datetime, timezone
from typing import Dict, Any
import database
from pipeline.audit_logger import AuditLogger

def parse_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standard payment data from Razorpay webhook or synthetic failure payload."""
    if "payload" in payload and "payment" in payload["payload"]:
        entity = payload["payload"]["payment"].get("entity", {})
        notes = entity.get("notes", {})
        customer_name = notes.get("customer_name") or notes.get("name") or "Valued Customer"
        
        raw_code = entity.get("error_code") or entity.get("error_reason") or "GATEWAY_ERROR"
        raw_desc = entity.get("error_description") or "Transaction failed at bank gateway"
        
        amount_paise = entity.get("amount", 0)
        amount_rupees = round(amount_paise / 100.0, 2) if amount_paise > 0 else 999.0
        
        return {
            "order_id": entity.get("order_id") or f"order_{entity.get('id', 'unknown')}",
            "payment_id": entity.get("id"),
            "customer_name": customer_name,
            "customer_phone": entity.get("contact", "+919876543210"),
            "customer_email": entity.get("email", "customer@example.com"),
            "amount": amount_rupees,
            "payment_method": entity.get("method", "card"),
            "raw_error_code": raw_code,
            "raw_error_desc": raw_desc,
            "attempt_count": int(notes.get("attempt_count", 1))
        }
    else:
        # Flat simulator format
        return {
            "order_id": payload["order_id"],
            "payment_id": payload.get("payment_id", f"pay_{payload['order_id'][:8]}"),
            "customer_name": payload.get("customer_name", "Valued Customer"),
            "customer_phone": payload.get("customer_phone", "+919876543210"),
            "customer_email": payload.get("customer_email", "customer@example.com"),
            "amount": float(payload.get("amount", 999)),
            "payment_method": payload.get("payment_method", "card"),
            "raw_error_code": payload.get("failure_reason_raw", "unknown_failure"),
            "raw_error_desc": payload.get("error_desc", f"Payment failed: {payload.get('failure_reason_raw')}"),
            "attempt_count": int(payload.get("attempt_count", 1))
        }

def process_detected_failure(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Captures the failure event, normalizes it, writes to DB, and logs audit stage."""
    parsed = parse_webhook_payload(raw_data)
    
    # Check if payment already exists
    existing = database.get_payment(parsed["order_id"])
    if existing:
        attempt_count = existing.get("attempt_count", 1) + 1
        parsed["attempt_count"] = attempt_count
    
    parsed["status"] = "detected"
    parsed["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
    
    database.save_payment(parsed)
    
    # Audit log entry
    AuditLogger.log_step(parsed["order_id"], "detected", {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amount": parsed["amount"],
        "payment_method": parsed["payment_method"],
        "raw_error_code": parsed["raw_error_code"],
        "raw_error_desc": parsed["raw_error_desc"],
        "attempt_count": parsed["attempt_count"]
    })
    
    return database.get_payment(parsed["order_id"])
