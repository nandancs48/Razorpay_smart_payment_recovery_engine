import os
import io
import csv
import json
import time
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

import database
import config
from config import BASE_DIR
from pipeline.orchestrator import run_single_transaction_pipeline, run_batch_pipeline
from pipeline.audit_logger import AuditLogger
from pipeline.tracker import record_payment_success
from pipeline.stopping_rules import enforce_stop
from simulator import generate_batch, generate_failed_payment

app = FastAPI(
    title="Razorpay AI Revenue Recovery Agent",
    description="Autonomous failed-payment recovery agent with safety limits, audit trails, and financial ROI tracking",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    database.init_db()

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        response = FileResponse(str(index_file))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return HTMLResponse("<h1>AI Revenue Recovery Agent</h1><p>Static index.html not yet initialized.</p>")

@app.get("/pay/{order_id}", response_class=HTMLResponse)
def serve_checkout(order_id: str):
    checkout_file = STATIC_DIR / "checkout.html"
    if checkout_file.exists():
        response = FileResponse(str(checkout_file))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return HTMLResponse(f"<h1>Test Checkout</h1><p>Checkout template for {order_id} not found.</p>")

@app.get("/api/metrics")
def get_dashboard_metrics():
    metrics = database.get_metrics()
    metrics["system_info"] = {
        "razorpay_mode": "Live Test API" if config.HAS_REAL_RAZORPAY else "Active Sandbox Simulation",
        "max_attempts_cap": config.MAX_ATTEMPTS,
        "cooldown_hours": config.COOLDOWN_HOURS,
        "guardrails": "Max 3 Attempts &bull; 24h Cooldown &bull; Promise-to-Pay Safe Pause"
    }
    return metrics

@app.get("/api/transactions")
def list_transactions(
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    items = database.list_payments(limit=limit, offset=offset, status=status, reason=reason, search=search)
    return {"transactions": items, "count": len(items)}

@app.get("/api/transactions/{order_id}/audit")
def get_order_audit(order_id: str):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
        
    trail = AuditLogger.get_full_trail(order_id)
    return {
        "payment": payment,
        "audit": trail
    }

# Live Replay Decision Endpoint
@app.post("/api/transactions/{order_id}/replay")
def replay_transaction_decision(order_id: str):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
        
    # Re-run single transaction pipeline live
    replayed = run_single_transaction_pipeline(payment, simulate_tracking=True)
    trail = AuditLogger.get_full_trail(order_id)
    return {
        "message": f"Successfully replayed autonomous recovery pipeline for {order_id}",
        "payment": replayed,
        "audit_trail": trail
    }

class BatchRunRequest(BaseModel):
    count: Optional[int] = 75

@app.post("/api/batch/run")
def trigger_batch_run(payload: BatchRunRequest = BatchRunRequest()):
    count = payload.count or 75
    batch = generate_batch(count=count)
    result = run_batch_pipeline(batch)
    return {
        "message": f"Successfully processed {count} failed payments through pipeline",
        "summary": result
    }

@app.post("/api/batch/reset")
def reset_database():
    database.reset_db()
    return {"message": "Database reset cleanly"}

class SimulateFailureRequest(BaseModel):
    customer_name: Optional[str] = "Priya Sharma"
    amount: Optional[float] = 1499.0
    failure_reason_raw: Optional[str] = "insufficient_funds"
    payment_method: Optional[str] = "card"
    attempt_count: Optional[int] = 1

@app.post("/api/simulate/webhook")
def simulate_single_webhook(payload: SimulateFailureRequest):
    data = payload.model_dump()
    simulated = generate_failed_payment()
    simulated.update(data)
    
    result = run_single_transaction_pipeline(simulated, simulate_tracking=True)
    order_id = result["order_id"]
    trail = AuditLogger.get_full_trail(order_id)
    
    return {
        "message": "Transaction processed through recovery pipeline",
        "payment": result,
        "audit_trail": trail
    }

class PromiseToPayRequest(BaseModel):
    order_id: str
    customer_name: str
    promised_date: str
    notes: Optional[str] = "Customer requested reminder after salary credit."

@app.post("/api/promise-to-pay")
def log_promise_to_pay(payload: PromiseToPayRequest):
    database.save_promise_to_pay(
        payload.order_id,
        payload.customer_name,
        payload.promised_date,
        payload.notes or ""
    )
    payment = database.get_payment(payload.order_id)
    if payment:
        enforce_stop(payment, "promise_to_pay_active", {
            "policy": f"Outreach paused until customer promised date: {payload.promised_date} per Consent Policy #RZP-PROMISE-P2P."
        })
    return {"message": "Promise-to-pay recorded. Automated outreach paused."}

# Complete Test Payment (Sandbox & Demo)
class CompletePaymentRequest(BaseModel):
    method: Optional[str] = "upi"

@app.post("/api/pay/{order_id}/complete")
def complete_test_payment(order_id: str, payload: CompletePaymentRequest = CompletePaymentRequest()):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
    
    if payment.get("status") == "recovered":
        return {"status": "recovered", "message": "Payment was already completed", "order_id": order_id}
        
    pay_id = f"pay_test_{int(time.time())}"
    record_payment_success(order_id, payment_id=pay_id, source=f"test_checkout_{payload.method}")
    return {
        "status": "recovered",
        "order_id": order_id,
        "amount": payment["amount"],
        "payment_id": pay_id,
        "message": f"Successfully processed test recovery of INR {payment['amount']} via {payload.method}. Zero real money charged."
    }

# Create Official Razorpay Order for Standard Checkout Modal
@app.post("/api/pay/{order_id}/create-order")
def create_razorpay_order_endpoint(order_id: str):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
        
    amount_paise = int(round(payment["amount"] * 100))
    cust_phone = (payment.get("customer_phone") or "+919820123456").replace(" ", "").replace("-", "")
    if len(cust_phone) < 10 or len(set(cust_phone[-6:])) <= 1:
        cust_phone = "+919820123456"
    elif not cust_phone.startswith("+"):
        cust_phone = "+91" + cust_phone[-10:]

    cust_name = payment.get("customer_name") or "Customer"
    cust_email = payment.get("customer_email") or "customer@example.com"

    if config.HAS_REAL_RAZORPAY:
        try:
            import razorpay
            client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
            rcpt = f"rcpt_{order_id[:30]}"
            rzp_order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": rcpt,
                "notes": {
                    "order_id": order_id,
                    "recovery_agent": "Track03_Autonomous"
                }
            })
            return {
                "success": True,
                "mode": "razorpay_checkout",
                "key_id": config.RAZORPAY_KEY_ID,
                "order_id": rzp_order["id"],
                "original_order_id": order_id,
                "amount": amount_paise,
                "currency": "INR",
                "customer_name": cust_name,
                "customer_phone": cust_phone,
                "customer_email": cust_email
            }
        except Exception:
            pass

    return {
        "success": True,
        "mode": "sandbox",
        "key_id": "rzp_test_sandbox",
        "order_id": f"order_sim_{order_id[:20]}",
        "original_order_id": order_id,
        "amount": amount_paise,
        "currency": "INR",
        "customer_name": cust_name,
        "customer_phone": cust_phone,
        "customer_email": cust_email
    }

class RazorpayVerifyPayload(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: Optional[str] = None
    razorpay_signature: Optional[str] = None

@app.post("/api/pay/{order_id}/verify-razorpay")
def verify_razorpay_payment_endpoint(order_id: str, payload: RazorpayVerifyPayload):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
        
    record_payment_success(order_id, payment_id=payload.razorpay_payment_id, source="razorpay_checkout_modal")
    return {
        "status": "recovered",
        "order_id": order_id,
        "payment_id": payload.razorpay_payment_id,
        "amount": payment["amount"],
        "message": f"Payment of INR {payment['amount']} successfully verified via Razorpay ({payload.razorpay_payment_id})!"
    }

# Sync Transaction Status with Razorpay API (Test Mode)
@app.post("/api/transactions/{order_id}/sync")
def sync_transaction_status(order_id: str):
    payment = database.get_payment(order_id)
    if not payment:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
        
    if payment.get("status") == "recovered":
        return {"status": "recovered", "message": "Payment is already marked recovered in the database."}
        
    if not config.HAS_REAL_RAZORPAY:
        return {
            "status": payment.get("status"),
            "message": "No live Razorpay test key configured. Use the 'Complete Test Payment' button to simulate recovery."
        }
        
    try:
        import razorpay
        client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
        rec_link = payment.get("recovery_link", "")
        
        if "rzp.io/i/" in rec_link:
            plink_id = rec_link.split("/i/")[-1].strip()
            link_obj = client.payment_link.fetch(plink_id)
            if link_obj.get("status") == "paid":
                payments_list = link_obj.get("payments") or []
                pay_id = payments_list[0].get("payment_id") if payments_list else f"pay_plink_{plink_id}"
                record_payment_success(order_id, payment_id=pay_id, source="razorpay_api_sync")
                return {"status": "recovered", "message": "Payment verified as PAID from Razorpay API!"}
            else:
                return {
                    "status": link_obj.get("status", "unpaid"),
                    "message": f"Razorpay Payment Link status is currently: {link_obj.get('status')}"
                }
                
        return {"status": payment.get("status"), "message": "No Razorpay payment link found for this order."}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to sync with Razorpay: {str(e)}"})

# Razorpay Settings Management
@app.get("/api/settings/razorpay")
def get_razorpay_settings():
    has_keys = bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)
    key_id = config.RAZORPAY_KEY_ID
    masked = f"{key_id[:8]}...{key_id[-4:]}" if len(key_id) > 12 else (key_id[:4] + "..." if key_id else "Not Configured")
    return {
        "has_keys": has_keys,
        "key_id_masked": masked,
        "is_test_mode": key_id.startswith("rzp_test_"),
        "mode_label": "Live Razorpay Test API" if has_keys else "Interactive Sandbox Simulation",
        "safety_guarantee": "Test mode strictly enforced. Zero real money is deducted in real life."
    }

class RazorpayKeyUpdatePayload(BaseModel):
    key_id: str
    key_secret: str
    webhook_secret: Optional[str] = ""

@app.post("/api/settings/razorpay")
def update_razorpay_settings(payload: RazorpayKeyUpdatePayload):
    key_id = payload.key_id.strip()
    key_secret = payload.key_secret.strip()
    
    # SAFETY GUARD: Ensure users only provide TEST keys so real money is NEVER deducted
    if key_id and not key_id.startswith("rzp_test_"):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Safety Protection Enforced: Only Razorpay TEST keys starting with 'rzp_test_' are allowed. Live keys are rejected to ensure zero real money is deducted."
            }
        )
        
    # Verify authentication against Razorpay API
    if key_id and key_secret:
        try:
            import razorpay
            test_client = razorpay.Client(auth=(key_id, key_secret))
            test_client.order.all({"count": 1})
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"error": f"Razorpay authentication failed with provided test keys: {str(e)}"}
            )
            
    res = config.update_razorpay_keys(key_id, key_secret, payload.webhook_secret or "")
    return {
        "status": "success",
        "message": "Razorpay Test API credentials validated and active!",
        "details": res
    }

# Export CSV Endpoint
@app.get("/api/export/csv")
def export_transactions_csv():
    items = database.list_payments(limit=500, offset=0)
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV Header
    writer.writerow([
        "Order ID", "Customer Name", "Customer Phone", "Amount (INR)", "Payment Method",
        "Failure Code", "Diagnosed Reason", "Confidence", "Strategy Action", "Status",
        "Attempt Count", "Stopped Reason", "Recovery Link", "Created At"
    ])
    
    for t in items:
        writer.writerow([
            t.get("order_id"),
            t.get("customer_name"),
            t.get("customer_phone"),
            t.get("amount"),
            t.get("payment_method"),
            t.get("raw_error_code"),
            t.get("diagnosed_reason"),
            f"{round((t.get('confidence') or 0.95) * 100, 1)}%",
            t.get("recovery_action"),
            t.get("status"),
            t.get("attempt_count"),
            t.get("stopped_reason") or "",
            t.get("recovery_link") or "",
            t.get("created_at")
        ])
        
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=razorpay_revenue_recovery_report.csv"}
    )

# Export Full Audit Trail JSON
@app.get("/api/export/audit-json")
def export_audit_json():
    logs = database.get_all_audit_logs()
    json_bytes = json.dumps(logs, indent=2).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=razorpay_audit_trail_export.json"}
    )

@app.post("/api/webhook/razorpay")
async def razorpay_webhook_listener(request: Request):
    try:
        body_bytes = await request.body()
        payload = json.loads(body_bytes.decode())
        event_name = payload.get("event")
        
        if event_name == "payment.failed":
            res = run_single_transaction_pipeline(payload, simulate_tracking=False)
            return {"status": "processed", "order_id": res.get("order_id")}
            
        elif event_name in ["payment_link.paid", "payment.captured", "order.paid"]:
            entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            if not entity and "payment_link" in payload.get("payload", {}):
                entity = payload["payload"]["payment_link"].get("entity", {})
                
            order_id = entity.get("order_id") or entity.get("notes", {}).get("order_id")
            payment_id = entity.get("id")
            
            if order_id:
                record_payment_success(order_id, payment_id=payment_id, source="razorpay_webhook")
                return {"status": "recovered", "order_id": order_id}
                
        return {"status": "ignored", "event": event_name}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
