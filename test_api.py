import unittest
from fastapi.testclient import TestClient
from main import app
import database

class TestFastAPIEndpoints(unittest.TestCase):
    def setUp(self):
        database.reset_db()
        self.client = TestClient(app)

    def test_root_dashboard_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("AI Revenue Recovery Agent", res.text)

    def test_metrics_empty(self):
        res = self.client.get("/api/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_transactions", data)
        self.assertIn("total_revenue_at_risk", data)
        self.assertIn("recovery_rate_pct", data)

    def test_simulate_single_and_audit(self):
        payload = {
            "customer_name": "Aarav Sharma",
            "amount": 2499.0,
            "failure_reason_raw": "card_declined",
            "attempt_count": 1
        }
        res = self.client.post("/api/simulate/webhook", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        order_id = data["payment"]["order_id"]
        
        # Test audit trail retrieval
        audit_res = self.client.get(f"/api/transactions/{order_id}/audit")
        self.assertEqual(audit_res.status_code, 200)
        audit_data = audit_res.json()
        self.assertEqual(audit_data["payment"]["order_id"], order_id)
        self.assertGreater(len(audit_data["audit"]["steps"]), 3)

    def test_batch_run_and_transactions_list(self):
        res = self.client.post("/api/batch/run", json={"count": 25})
        self.assertEqual(res.status_code, 200)
        
        # Fetch transactions
        t_res = self.client.get("/api/transactions?limit=25")
        self.assertEqual(t_res.status_code, 200)
        t_data = t_res.json()
        self.assertEqual(len(t_data["transactions"]), 25)

    def test_webhook_payment_failed_and_recovered(self):
        # 1. Post simulated Razorpay webhook payment.failed
        webhook_failed = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_wh_123",
                        "order_id": "order_test_wh_123",
                        "amount": 499900,
                        "currency": "INR",
                        "method": "card",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Payment was declined by the bank due to insufficient funds",
                        "notes": {
                            "customer_name": "Rohan Gupta"
                        }
                    }
                }
            }
        }
        res = self.client.post("/api/webhook/razorpay", json=webhook_failed)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "processed")
        
        # Verify payment created in DB
        payment = database.get_payment("order_test_wh_123")
        self.assertIsNotNone(payment)
        self.assertEqual(payment["amount"], 4999.0)

        # 2. Post simulated Razorpay webhook payment_link.paid
        webhook_paid = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_123",
                        "order_id": "order_test_wh_123"
                    }
                }
            }
        }
        res_paid = self.client.post("/api/webhook/razorpay", json=webhook_paid)
        self.assertEqual(res_paid.status_code, 200)
        self.assertEqual(res_paid.json()["status"], "recovered")
        
        # Verify status is now recovered
        updated_payment = database.get_payment("order_test_wh_123")
        self.assertEqual(updated_payment["status"], "recovered")

    def test_promise_to_pay(self):
        # Create an order first
        payload = {
            "customer_name": "Deepika Joshi",
            "amount": 1999.0,
            "failure_reason_raw": "insufficient_funds",
            "attempt_count": 1
        }
        res = self.client.post("/api/simulate/webhook", json=payload)
        order_id = res.json()["payment"]["order_id"]

        p2p_payload = {
            "order_id": order_id,
            "customer_name": "Deepika Joshi",
            "promised_date": "2026-09-10",
            "notes": "Salary credit on the 10th"
        }
        p2p_res = self.client.post("/api/promise-to-pay", json=p2p_payload)
        self.assertEqual(p2p_res.status_code, 200)

        updated = database.get_payment(order_id)
        self.assertEqual(updated["status"], "stopped")
        self.assertEqual(updated["stopped_reason"], "promise_to_pay_active")

if __name__ == "__main__":
    unittest.main()
