import time
from typing import Dict, Any, List
import database
from pipeline.detector import process_detected_failure
from pipeline.stopping_rules import should_retry, enforce_stop
from pipeline.diagnoser import run_diagnoser
from pipeline.strategy_engine import select_recovery_strategy
from pipeline.executor import execute_recovery
from pipeline.tracker import simulate_customer_response

def run_single_transaction_pipeline(raw_payment: Dict[str, Any], simulate_tracking: bool = True) -> Dict[str, Any]:
    """
    Orchestrates the recovery pipeline for a single failed payment:
    [Detected] -> [Diagnosed] -> [Strategy Selected] -> [Stopping Check] -> [Executed] -> [Tracked]
    """
    # 1. DETECTOR: capture failure event, normalize & save
    payment = process_detected_failure(raw_payment)
    
    # 2. DIAGNOSER: 2-tier root cause classification
    payment = run_diagnoser(payment)
    
    # 3. STRATEGY ENGINE: reason -> action + personalized copy
    strategy = select_recovery_strategy(payment)
    
    # 4. STOPPING RULES: compliance and fatigue guardrails
    allowed, stop_reason, stop_meta = should_retry(payment, is_initial_trigger=False)
    if not allowed:
        enforce_stop(payment, stop_reason, stop_meta)
        return database.get_payment(payment["order_id"])
        
    # 5. EXECUTOR: call Razorpay API for link + dispatch simulated SMS/Email
    payment = execute_recovery(payment, strategy)
    
    # 6. TRACKER: update outcome
    if simulate_tracking:
        payment = simulate_customer_response(payment)
        
    return payment

def run_batch_pipeline(raw_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Runs a batch of transactions and returns summary metrics."""
    processed = []
    for item in raw_batch:
        res = run_single_transaction_pipeline(item, simulate_tracking=True)
        processed.append(res)
    
    metrics = database.get_metrics()
    return {
        "processed_count": len(processed),
        "metrics": metrics
    }
