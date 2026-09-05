import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Razorpay credentials
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

# Check if real Razorpay keys are active
HAS_REAL_RAZORPAY = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

def update_razorpay_keys(key_id: str, key_secret: str, webhook_secret: str = "") -> dict:
    global RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET, HAS_REAL_RAZORPAY
    RAZORPAY_KEY_ID = key_id.strip()
    RAZORPAY_KEY_SECRET = key_secret.strip()
    if webhook_secret:
        RAZORPAY_WEBHOOK_SECRET = webhook_secret.strip()
    HAS_REAL_RAZORPAY = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
    
    env_file = BASE_DIR / ".env"
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
    
    key_dict = {
        "RAZORPAY_KEY_ID": RAZORPAY_KEY_ID,
        "RAZORPAY_KEY_SECRET": RAZORPAY_KEY_SECRET,
    }
    if webhook_secret:
        key_dict["RAZORPAY_WEBHOOK_SECRET"] = RAZORPAY_WEBHOOK_SECRET
        
    new_lines = []
    seen = set()
    for line in lines:
        matched = False
        for k, v in key_dict.items():
            if line.startswith(f"{k}="):
                new_lines.append(f"{k}={v}")
                seen.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)
            
    for k, v in key_dict.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")
            
    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {
        "has_real_razorpay": HAS_REAL_RAZORPAY,
        "key_id_masked": f"{RAZORPAY_KEY_ID[:8]}...{RAZORPAY_KEY_ID[-4:]}" if len(RAZORPAY_KEY_ID) > 12 else (RAZORPAY_KEY_ID[:4] + "..." if RAZORPAY_KEY_ID else ""),
        "is_test_mode": RAZORPAY_KEY_ID.startswith("rzp_test_")
    }

# LLM API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
HAS_LLM = bool(GEMINI_API_KEY or OPENAI_API_KEY)

# Database
DB_PATH = BASE_DIR / "recovery.db"

# Stopping Rules Constraints
MAX_ATTEMPTS = 3
COOLDOWN_HOURS = 24

# Failure Categories & Default Strategies
RECOVERY_STRATEGIES = {
    "insufficient_funds": {
        "action": "retry_payment_link",
        "timing_hours": 72,  # +3 days
        "channel": "SMS",
        "label": "Scheduled Link (+3 days)"
    },
    "card_declined": {
        "action": "new_payment_link_suggest_upi",
        "timing_hours": 0,  # Immediate
        "channel": "SMS + Email",
        "label": "Immediate UPI Suggestion"
    },
    "network_timeout": {
        "action": "auto_retry",
        "timing_hours": 0.033,  # +2 minutes
        "channel": "Auto-retry",
        "label": "Instant Auto-Retry"
    },
    "mandate_expired": {
        "action": "reauthorization_flow",
        "timing_hours": 0,  # Immediate
        "channel": "Email",
        "label": "Re-auth Flow"
    },
    "otp_timeout": {
        "action": "instant_retry_link",
        "timing_hours": 0.083,  # +5 minutes
        "channel": "SMS",
        "label": "Instant Retry Link (+5m)"
    },
    "bank_server_down": {
        "action": "retry_payment_link",
        "timing_hours": 1,  # +1 hour
        "channel": "SMS",
        "label": "Downtime Recovery (+1h)"
    },
    "invalid_cvv": {
        "action": "new_payment_link",
        "timing_hours": 0,  # Immediate
        "channel": "SMS",
        "label": "Immediate Link with CVV Prompt"
    },
    "user_input_error": {
        "action": "new_payment_link",
        "timing_hours": 0,
        "channel": "SMS",
        "label": "Immediate Checkout Link"
    }
}

# Financial & Outreach Cost Configuration (for ROI metric)
SMS_COST_INR = 1.50
EMAIL_COST_INR = 0.20
AUTORETRY_COST_INR = 0.00

# Realistic baseline conversion probabilities by reason (to ensure 35-55% realistic demo distribution)
BASELINE_CONVERSION_RATES = {
    "network_timeout": 0.76,
    "otp_timeout": 0.62,
    "bank_server_down": 0.44,
    "card_declined": 0.39,
    "user_input_error": 0.38,
    "invalid_cvv": 0.35,
    "insufficient_funds": 0.26,
    "mandate_expired": 0.24,
}

# Payment method baseline recovery performance
PAYMENT_METHOD_CONVERSION = {
    "upi": 0.58,
    "card": 0.36,
    "netbanking": 0.32
}
