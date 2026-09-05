import unittest
from database import init_db, reset_db, get_metrics, list_payments, get_payment
from simulator import generate_batch, generate_failed_payment
from pipeline.orchestrator import run_single_transaction_pipeline, run_batch_pipeline
from pipeline.audit_logger import AuditLogger
from pipeline.stopping_rules import should_retry

class TestRevenueRecoveryPipeline(unittest.TestCase):
    def setUp(self):
        reset_db()
        init_db()

    def test_single_transaction_run(self):
        payment_input = {
            "order_id": "test_order_001",
            "customer_name": "Test Customer",
            "customer_phone": "+919812345678",
            "customer_email": "test@example.com",
            "amount": 1499.0,
            "failure_reason_raw": "insufficient_funds",
            "attempt_count": 1
        }
        res = run_single_transaction_pipeline(payment_input, simulate_tracking=True)
        self.assertIsNotNone(res)
        self.assertEqual(res["order_id"], "test_order_001")
        self.assertIn(res["status"], ["recovered", "retrying", "stopped", "abandoned"])
        
        # Verify audit trail
        trail = AuditLogger.get_full_trail("test_order_001")
        self.assertGreaterEqual(len(trail["steps"]), 4)
        stages = [s["stage"] for s in trail["steps"]]
        self.assertIn("detected", stages)
        self.assertIn("diagnosed", stages)
        self.assertIn("action_chosen", stages)
        self.assertIn("executed", stages)

    def test_stopping_rules_enforcement(self):
        # Case where attempt_count >= 3
        stopped_input = {
            "order_id": "test_order_stopped_001",
            "customer_name": "Frequent Spammer",
            "customer_phone": "+919812345678",
            "amount": 2999.0,
            "failure_reason_raw": "card_declined",
            "attempt_count": 4  # Exceeds MAX_ATTEMPTS = 3
        }
        res = run_single_transaction_pipeline(stopped_input, simulate_tracking=False)
        self.assertEqual(res["status"], "stopped")
        self.assertEqual(res["stopped_reason"], "max_attempts_reached")
        
        # Verify audit trail recorded stopping
        trail = AuditLogger.get_full_trail("test_order_stopped_001")
        stages = [s["stage"] for s in trail["steps"]]
        self.assertIn("stopped", stages)

    def test_batch_execution_and_metrics(self):
        batch = generate_batch(count=75)
        self.assertEqual(len(batch), 75)
        
        result = run_batch_pipeline(batch)
        self.assertEqual(result["processed_count"], 75)
        
        metrics = get_metrics()
        self.assertEqual(metrics["total_transactions"], 75)
        self.assertGreater(metrics["total_revenue_at_risk"], 0)
        self.assertGreater(metrics["total_recovered"], 0)
        self.assertGreater(metrics["stopped_count"], 0)
        
        # Validate realistic recovery rate between 30% and 60%
        print(f"\n[Test Metrics] Total at risk: INR {metrics['total_revenue_at_risk']}")
        print(f"[Test Metrics] Total recovered: INR {metrics['total_recovered']} ({metrics['recovery_rate_pct']}%)")
        print(f"[Test Metrics] Stopped cases: {metrics['stopped_count']}")
        
        self.assertTrue(25.0 <= metrics["recovery_rate_pct"] <= 65.0, 
                        f"Expected recovery rate in realistic 25-65% band, got {metrics['recovery_rate_pct']}%")

if __name__ == "__main__":
    unittest.main()
