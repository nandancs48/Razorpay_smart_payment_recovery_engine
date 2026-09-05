from typing import Dict, Any, Tuple
from config import RECOVERY_STRATEGIES, GEMINI_API_KEY, OPENAI_API_KEY
import database
from pipeline.audit_logger import AuditLogger

REASONING_EXPLANATIONS = {
    "insufficient_funds": "Customer has insufficient funds. Delaying retry by 3 days (often aligns with salary/top-up cycles) rather than badgering immediately.",
    "card_declined": "Issuing bank declined card. Immediately prompting customer with a fresh link recommending alternate payment via UPI or Netbanking.",
    "network_timeout": "Transient socket/network interruption. Safe to trigger an automated instant retry after 2 minutes with no customer friction.",
    "mandate_expired": "Recurring mandate expired. Triggering email with one-click re-authorization flow to renew payment instructions.",
    "otp_timeout": "OTP verification timed out. Customer was actively checking out; sending instant SMS retry link within 5 minutes while intent is high.",
    "bank_server_down": "Bank gateway switch reported temporary downtime. Scheduling payment link retry in 1 hour after bank services recover.",
    "invalid_cvv": "Customer entered invalid card credentials. Dispatching instant secure link with prefilled cart to retry card or switch to UPI.",
    "user_input_error": "Checkout form error detected. Resending clean checkout session link."
}

def draft_sms_copy(payment: Dict[str, Any], reason: str, link_url: str = "") -> str:
    """Drafts an empathetic, high-converting SMS under 160 characters."""
    name = payment.get("customer_name", "there").split()[0]
    amount = f"₹{int(payment.get('amount', 0))}"
    link = link_url if link_url else "rzp.io/i/recov"
    
    # Try LLM if configured
    if GEMINI_API_KEY:
        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"Write a friendly SMS under 150 chars to {name} about their payment of {amount} that couldn't go through ({reason}). Include link {link}. No hashtags."
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=3)
            if res.status_code == 200:
                txt = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if len(txt) <= 160:
                    return txt
        except Exception:
            pass

    # High-converting personalized template engine
    templates = {
        "insufficient_funds": f"Hi {name}, your payment of {amount} couldn't be completed. We've saved your order! Complete it whenever you're ready: {link}",
        "card_declined": f"Hi {name}, your card payment of {amount} was declined. You can easily complete your order using UPI/GPay here: {link}",
        "otp_timeout": f"Hi {name}, looks like your OTP timed out for {amount}. Don't worry, click here to complete your payment securely: {link}",
        "bank_server_down": f"Hi {name}, your bank servers were temporarily down for {amount}. All systems are back up! Tap to complete: {link}",
        "invalid_cvv": f"Hi {name}, payment of {amount} failed due to card details. Tap here to re-enter or switch to UPI: {link}",
        "network_timeout": f"Hi {name}, payment of {amount} had a connection hiccup. Tap to resume your order: {link}",
    }
    
    return templates.get(
        reason,
        f"Hi {name}, your payment of {amount} was not completed. Tap here to finish securely: {link}"
    )

def draft_hinglish_copy(payment: Dict[str, Any], reason: str, link_url: str = "") -> str:
    """Hinglish copy generation for enhanced Indian consumer engagement (Stretch Goal)."""
    name = payment.get("customer_name", "dost").split()[0]
    amount = f"₹{int(payment.get('amount', 0))}"
    link = link_url if link_url else "rzp.io/i/recov"
    
    hinglish_map = {
        "card_declined": f"Namaste {name}, aapka card se {amount} ka payment decline ho gaya. Bina kisi tension ke UPI se complete karein: {link}",
        "insufficient_funds": f"Namaste {name}, aapka {amount} ka order safe hai. Jab bhi ready hon, yahan click karke payment karein: {link}",
        "otp_timeout": f"Namaste {name}, OTP miss ho gaya? Koi baat nahi, yahan click karke {amount} ka payment turant complete karein: {link}",
        "bank_server_down": f"Namaste {name}, bank server down hone ke karan {amount} atka tha. Abhi try karein, sab chal raha hai: {link}"
    }
    return hinglish_map.get(reason, f"Namaste {name}, aapka {amount} ka payment ruk gaya tha. Yahan se complete karein: {link}")

def select_recovery_strategy(payment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Selects strategy based on diagnosed reason and drafts personalized outreach copy.
    """
    reason = payment.get("diagnosed_reason", "bank_server_down")
    strat = RECOVERY_STRATEGIES.get(reason, RECOVERY_STRATEGIES["bank_server_down"])
    
    explanation = REASONING_EXPLANATIONS.get(reason, "Standard recovery procedure applied.")
    sms_draft = draft_sms_copy(payment, reason)
    hinglish_draft = draft_hinglish_copy(payment, reason)
    
    strategy_payload = {
        "action": strat["action"],
        "action_label": strat["label"],
        "channel": strat["channel"],
        "timing_hours": strat["timing_hours"],
        "reasoning": explanation,
        "sms_draft": sms_draft,
        "hinglish_draft": hinglish_draft
    }
    
    order_id = payment["order_id"]
    database.update_payment(order_id, recovery_action=strat["action"], sms_preview=sms_draft)
    
    AuditLogger.log_step(order_id, "action_chosen", {
        "action": strat["action"],
        "channel": strat["channel"],
        "timing_hours": strat["timing_hours"],
        "reasoning": explanation,
        "sms_preview": sms_draft
    })
    
    return strategy_payload
