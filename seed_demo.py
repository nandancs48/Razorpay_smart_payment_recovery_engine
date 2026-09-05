from database import reset_db, get_metrics
from simulator import generate_batch
from pipeline.orchestrator import run_batch_pipeline

def seed_demo_data(count: int = 75):
    print("Resetting database...")
    reset_db()
    print(f"Generating realistic diverse cohort of {count} failed payment scenarios...")
    batch = generate_batch(count=count)
    print("Running autonomous 6-stage recovery pipeline...")
    result = run_batch_pipeline(batch)
    metrics = get_metrics()
    
    print("\n=======================================================")
    print("   RAZORPAY AI REVENUE RECOVERY AGENT — DEMO SEEDED")
    print("=======================================================")
    print(f"Total Transactions:      {metrics['total_transactions']}")
    print(f"Total Revenue At Risk:   INR {metrics['total_revenue_at_risk']:,.2f}")
    print(f"Total Won Back:          INR {metrics['total_recovered']:,.2f} ({metrics['recovery_rate_pct']}%)")
    print(f"Net Recovered (ROI):     INR {metrics['financial_roi']['net_recovered']:,.2f} ({metrics['financial_roi']['roi_multiplier']}x ROI)")
    print(f"Total Outreach Cost:     INR {metrics['financial_roi']['total_outreach_cost']:,.2f}")
    print(f"Avg Cost per Recovery:   INR {metrics['financial_roi']['cost_per_recovery']:,.2f}")
    print(f"Stopped (Guardrails):    {metrics['stopped_count']} cases safely halted")
    print("\nStacked Reason Breakdown (Won / Total):")
    for r in metrics["reason_breakdown"]:
        print(f"  - {r['reason']:<20}: {r['recovered']}/{r['total_count']} ({r['recovery_rate']}%) | Retrying: {r['retrying']} | Stopped: {r['stopped']}")
    print("\nPayment Method Efficiency:")
    for m in metrics["payment_method_breakdown"]:
        print(f"  - {m['method']:<12}: {m['recovered_count']}/{m['total_count']} ({m['recovery_rate']}%) | Won: INR {m['recovered_amount']:,.2f}")
    print("\nReady for presentation at http://127.0.0.1:8000")
    print("=======================================================\n")

if __name__ == "__main__":
    seed_demo_data(75)
