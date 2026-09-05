import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker

try:
    fake = Faker('en_IN')
except Exception:
    fake = Faker()

FAILURE_SCENARIOS = [
    {
        "code": "insufficient_funds",
        "desc": "The issuing bank reported insufficient funds in account.",
        "method": "card",
        "sub_method": "HDFC Millennia Debit",
        "test_card": "4012 0000 0000 0002 (Razorpay Test Card - Insufficient Funds)"
    },
    {
        "code": "card_declined",
        "desc": "Transaction declined by card issuer: Do Not Honor / Card Limit Exceeded.",
        "method": "card",
        "sub_method": "ICICI Coral Credit",
        "test_card": "4000 0000 0000 0002 (Razorpay Test Card - Bank Declined)"
    },
    {
        "code": "GATEWAY_ERROR",
        "desc": "Payment gateway timeout connecting to HDFC netbanking switch.",
        "method": "netbanking",
        "sub_method": "HDFC Retail NetBanking",
        "test_card": None
    },
    {
        "code": "otp_timeout",
        "desc": "Customer OTP input window expired before 3DS authorization.",
        "method": "card",
        "sub_method": "Axis Flipkart Credit",
        "test_card": "4000 0000 0000 1092 (Razorpay 3DS OTP Timeout)"
    },
    {
        "code": "bank_server_down",
        "desc": "State Bank of India payment gateway temporary node outage.",
        "method": "netbanking",
        "sub_method": "SBI NetBanking Switch",
        "test_card": None
    },
    {
        "code": "network_timeout",
        "desc": "TCP connection timed out during UPI token exchange.",
        "method": "upi",
        "sub_method": "Google Pay UPI",
        "test_card": None
    },
    {
        "code": "invalid_cvv",
        "desc": "Security code validation failed against issuer bank.",
        "method": "card",
        "sub_method": "SBI SimplyClick Credit",
        "test_card": "4111 1111 1111 1111 (Incorrect CVV entered)"
    },
    {
        "code": "mandate_expired",
        "desc": "Auto-debit recurring subscription mandate expired on 2026-08-30.",
        "method": "card",
        "sub_method": "Kotak 811 e-Mandate",
        "test_card": None
    },
    {
        "code": "BAD_REQUEST_ERROR",
        "desc": "Invalid VPA format entered during checkout initialization.",
        "method": "upi",
        "sub_method": "PhonePe UPI",
        "test_card": None
    }
]

AMOUNTS = [499, 799, 999, 1299, 1499, 1999, 2499, 2999, 3499, 4999, 7499, 9999]

# 100+ Unique, Highly Diverse Indian Names (North, South, East, West)
FIRST_NAMES = [
    "Aarav", "Priya", "Vikram", "Ananya", "Rahul", "Sneha", "Aditya", "Pooja", "Rohan", "Deepika",
    "Karan", "Ritu", "Arjun", "Meera", "Nikhil", "Swati", "Varun", "Kavita", "Harsh", "Divya",
    "Siddharth", "Ishaan", "Tanvi", "Gautam", "Shruti", "Manish", "Bhavna", "Abhishek", "Neha", "Pranav",
    "Sangeetha", "Karthik", "Lavanya", "Venkatesh", "Deepa", "Murali", "Akshaya", "Suresh", "Lakshmi", "Harish",
    "Anirban", "Debashree", "Sourav", "Payel", "Prosenjit", "Debolina", "Subhash", "Mousumi", "Amitabh", "Indrani",
    "Chirag", "Jhanvi", "Bhavesh", "Daksha", "Ketan", "Kinjal", "Parth", "Dharini", "Hardik", "Urvashi"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Iyer", "Nair", "Kulkarni", "Deshmukh", "Gupta", "Joshi",
    "Malhotra", "Chopra", "Reddy", "Rao", "Menon", "Pillai", "Bhatia", "Agarwal", "Singh", "Yadav",
    "Sen", "Banerjee", "Mukherjee", "Chatterjee", "Bose", "Dutta", "Das", "Ghosh", "Majumdar", "Roy",
    "Shah", "Parekh", "Trivedi", "Vora", "Modi", "Thakkar", "Pandya", "Gala", "Zaveri", "Kapadia",
    "Hegde", "Shetty", "Pai", "Kamath", "Bhat", "Alva", "Prabhu", "Nayank", "Puranik", "Karanth"
]

TELECOM_PREFIXES = ["98", "97", "96", "99", "91", "88", "87", "85", "79", "78", "70", "80", "94", "93"]

_used_phones = set()
_used_names = set()

def generate_unique_phone():
    while True:
        prefix = random.choice(TELECOM_PREFIXES)
        suffix = random.randint(10000000, 99999999)
        phone = f"+91{prefix}{suffix}"
        if phone not in _used_phones:
            _used_phones.add(phone)
            return phone

def generate_unique_name():
    for _ in range(50):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        full = f"{first} {last}"
        if full not in _used_names:
            _used_names.add(full)
            return full
    # Fallback to random combination
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_failed_payment(index: int = 1, force_stopped: bool = False, specific_scenario: dict = None) -> dict:
    scenario = specific_scenario or random.choice(FAILURE_SCENARIOS)
    name = generate_unique_name()
    order_uuid = str(uuid.uuid4())[:10]
    order_id = f"order_rec_{order_uuid}"
    
    phone = generate_unique_phone()
    clean_first = name.split()[0].lower()
    clean_last = name.split()[1].lower() if len(name.split()) > 1 else "cust"
    email = f"{clean_first}.{clean_last}{random.randint(10, 99)}@gmail.com"
    amount = random.choice(AMOUNTS)
    
    # Setup attempt count & cooldown status
    if force_stopped:
        # Some reached attempt 3/3, some in cooldown
        if random.random() < 0.65:
            attempt_count = 3
            # 2.5 hours ago (recent, triggers 24h cooldown rule)
            last_attempt = (datetime.now(timezone.utc) - timedelta(hours=random.uniform(1.2, 8.5))).isoformat()
        else:
            attempt_count = 4  # Exceeded max attempts
            last_attempt = (datetime.now(timezone.utc) - timedelta(hours=random.uniform(25, 48))).isoformat()
    else:
        # First attempt (80%) or second attempt past cooldown (20%)
        if random.random() < 0.20:
            attempt_count = 2
            last_attempt = (datetime.now(timezone.utc) - timedelta(hours=random.uniform(26, 72))).isoformat()
        else:
            attempt_count = 1
            last_attempt = datetime.now(timezone.utc).isoformat()
            
    return {
        "order_id": order_id,
        "payment_id": f"pay_{order_uuid[:8]}",
        "customer_name": name,
        "customer_phone": phone,
        "customer_email": email,
        "amount": amount,
        "payment_method": scenario["method"],
        "payment_sub_method": scenario.get("sub_method", "Direct"),
        "failure_reason_raw": scenario["code"],
        "error_desc": scenario["desc"],
        "test_card": scenario.get("test_card"),
        "attempt_count": attempt_count,
        "last_attempt_at": last_attempt,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def generate_batch(count: int = 75) -> list:
    """
    Generates a cohort of failed transactions with balanced variety across all 9 causes.
    Guarantees that every failure reason is represented and ~14-18 cases trigger stopping rules.
    """
    _used_phones.clear()
    _used_names.clear()
    
    batch = []
    
    # Step 1: Ensure at least 4 transactions of EVERY failure scenario
    for scenario in FAILURE_SCENARIOS:
        for _ in range(4):
            batch.append(generate_failed_payment(len(batch) + 1, force_stopped=False, specific_scenario=scenario))
            
    # Step 2: Inject ~15 stopping rule cases across different reasons
    stopped_count = min(16, max(12, count // 5))
    for i in range(stopped_count):
        sc = random.choice(FAILURE_SCENARIOS)
        batch.append(generate_failed_payment(len(batch) + 1, force_stopped=True, specific_scenario=sc))
        
    # Step 3: Fill remainder up to count with balanced random scenarios
    remaining = count - len(batch)
    for _ in range(remaining):
        sc = random.choice(FAILURE_SCENARIOS)
        batch.append(generate_failed_payment(len(batch) + 1, force_stopped=False, specific_scenario=sc))
        
    random.shuffle(batch)
    return batch[:count]
