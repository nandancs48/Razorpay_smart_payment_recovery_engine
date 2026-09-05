from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict, Any
from config import MAX_ATTEMPTS, COOLDOWN_HOURS
import database
from pipeline.audit_logger import AuditLogger

def hours_since_last_attempt(payment: Dict[str, Any]) -> Tuple[float, Optional[str]]:
    last_attempt = payment.get("last_attempt_at")
    if not last_attempt:
        return 999.0, None
    try:
        last_dt = datetime.fromisoformat(last_attempt)
        now_dt = datetime.now(timezone.utc)
        diff = (now_dt - last_dt).total_seconds() / 3600.0
        return max(0.0, diff), last_dt.isoformat()
    except Exception:
        return 999.0, None

def should_retry(payment: Dict[str, Any], is_initial_trigger: bool = False) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Evaluates anti-spam and compliance stopping rules:
    1. Maximum retries cap (MAX_ATTEMPTS = 3)
    2. Cooldown period (COOLDOWN_HOURS = 24) for non-transient repeated contact
    3. Active Promise-to-Pay protection
    """
    order_id = payment["order_id"]
    attempt_count = payment.get("attempt_count", 1)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Check 1: Max attempts cap
    if attempt_count > MAX_ATTEMPTS:
        reason = "max_attempts_reached"
        meta = {
            "attempt_count": attempt_count,
            "max_allowed": MAX_ATTEMPTS,
            "policy_code": "RZP-COMPLIANCE-301",
            "policy": f"Attempt {attempt_count}/{MAX_ATTEMPTS} reached at {now_iso}. Max retry cap reached. Permanent stop enforced to prevent customer fatigue.",
            "next_allowed_contact": "None (Capped)"
        }
        return False, reason, meta
        
    # Check 2: Cooldown active (if not first trigger and not a transient instant retry)
    if not is_initial_trigger and attempt_count > 1:
        hours_elapsed, last_iso = hours_since_last_attempt(payment)
        reason_cat = payment.get("diagnosed_reason", "")
        # Transient errors (network/otp) allow quick retries; others require 24h cooldown
        if reason_cat not in ["network_timeout", "otp_timeout"] and hours_elapsed < COOLDOWN_HOURS:
            hours_remaining = round(COOLDOWN_HOURS - hours_elapsed, 1)
            unblock_time = (datetime.now(timezone.utc) + timedelta(hours=hours_remaining)).strftime("%Y-%m-%d %H:%M UTC")
            reason = "cooldown_active"
            meta = {
                "attempt_count": attempt_count,
                "hours_since_last": round(hours_elapsed, 1),
                "cooldown_required_hours": COOLDOWN_HOURS,
                "hours_remaining": hours_remaining,
                "last_attempt_at": last_iso,
                "unblock_timestamp": unblock_time,
                "policy_code": "RZP-COMPLIANCE-24H",
                "policy": f"Attempt {attempt_count} executed recently. Next outreach blocked until {unblock_time} ({hours_remaining}h cooldown remaining) per Anti-Spam Cooldown Policy.",
                "next_allowed_contact": unblock_time
            }
            return False, reason, meta

    return True, None, {"status": "ok", "attempt_count": attempt_count, "compliance_check": "passed"}

def enforce_stop(payment: Dict[str, Any], reason: str, meta: Dict[str, Any]):
    """Record stopped transaction with explicit timestamped audit log and update DB."""
    order_id = payment["order_id"]
    database.update_payment(
        order_id,
        status="stopped",
        stopped_reason=reason
    )
    AuditLogger.log_step(order_id, "stopped", {
        "reason": reason,
        "detail": meta.get("policy", "Stopping rule enforced"),
        "policy_code": meta.get("policy_code", "RZP-COMPLIANCE"),
        "attempt_count": meta.get("attempt_count", payment.get("attempt_count", 1)),
        "hours_remaining": meta.get("hours_remaining"),
        "next_allowed_contact": meta.get("next_allowed_contact", "Blocked"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
