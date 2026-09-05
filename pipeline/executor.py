import hashlib
from datetime import datetime, timezone
from typing import Dict, Any
import config
import database
from pipeline.audit_logger import AuditLogger

def get_razorpay_client():
    if config.HAS_REAL_RAZORPAY:
        try:
            import razorpay
            return razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
        except Exception:
            return None
    return None

def create_recovery_link(payment: Dict[str, Any], host_url: str = "http://127.0.0.1:8000") -> Dict[str, Any]:
    """
    Creates a Razorpay Payment Link using live test mode if keys configured,
    or falls back to an interactive local test checkout simulator.
    """
    amount_paise = int(round(payment["amount"] * 100))
    order_id = payment["order_id"]
    client = get_razorpay_client()
    
    if client:
        try:
            contact = payment.get("customer_phone", "").replace(" ", "").replace("-", "")
            if not contact or len(contact) < 10 or len(set(contact[-6:])) <= 1:
                contact = "+919820123456"
            elif not contact.startswith("+"):
                contact = "+91" + contact[-10:]

            link = client.payment_link.create({
                "amount": amount_paise,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Recovery Payment - Order {order_id}",
                "customer": {
                    "name": payment.get("customer_name", "Customer"),
                    "contact": contact,
                    "email": payment.get("customer_email", "customer@example.com")
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "notes": {
                    "order_id": order_id,
                    "recovery_agent": "Track03_Agent"
                }
            })
            return {
                "link_id": link.get("id"),
                "short_url": link.get("short_url"),
                "mode": "live_razorpay_testmode"
            }
        except Exception as e:
            # Fallback to interactive sandbox link if network/auth issues occur
            pass

    # Interactive Local Test Checkout Link (WORKS OUT-OF-THE-BOX WITHOUT CHARGING REAL MONEY)
    local_url = f"{host_url.rstrip('/')}/pay/{order_id}"
    return {
        "link_id": f"sandbox_{order_id}",
        "short_url": local_url,
        "mode": "sandbox_simulation"
    }

def execute_recovery(payment: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes chosen recovery action:
    - Generates Razorpay payment link
    - Updates outreach copy with link URL
    - Logs simulated communication (SMS/Email)
    - Records audit trail step
    """
    order_id = payment["order_id"]
    link_info = create_recovery_link(payment)
    payment_link_url = link_info["short_url"]
    
    # Refresh copy with real link
    final_sms = strategy["sms_draft"].replace("rzp.io/i/recov", payment_link_url)
    
    # Save simulated communication
    database.save_recovery_action({
        "order_id": order_id,
        "action_type": strategy["action"],
        "channel": strategy["channel"],
        "timing_offset": f"+{strategy['timing_hours']} hours" if strategy['timing_hours'] > 0 else "immediate",
        "message_content": final_sms,
        "payment_link": payment_link_url,
        "status": "sent"
    })
    
    # Update payment record
    database.update_payment(
        order_id,
        recovery_link=payment_link_url,
        sms_preview=final_sms,
        status="retrying"
    )
    
    # Audit log entry
    AuditLogger.log_step(order_id, "executed", {
        "channel": strategy["channel"],
        "action": strategy["action"],
        "payment_link": payment_link_url,
        "link_mode": link_info["mode"],
        "message_dispatched": final_sms,
        "result": "success",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    payment["recovery_link"] = payment_link_url
    payment["status"] = "retrying"
    return payment
