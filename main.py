"""Fraud Detection Service - Main Entry Point.

This script runs the fraud detection demo and can start the API server.

Usage:
    python main.py           # Run the demo
    python main.py --serve   # Start the API server
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.models import Transaction, TransactionRequest, TransactionType
from app.data_store import DataStore
from app.account_profiler import AccountProfiler
from app.risk_scorer import RiskScorer


def load_test_data():
    """Load the generated test data."""
    data_path = Path(__file__).parent / "data" / "test_transactions.json"
    
    if not data_path.exists():
        print("Error: Test data not found. Run 'python data/generate_test_data.py' first.")
        sys.exit(1)
    
    with open(data_path) as f:
        data = json.load(f)
    
    return data


def print_divider(title: str = ""):
    """Print a visual divider."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print("-" * 60)


def print_assessment(assessment, scenario: str = ""):
    """Pretty print a risk assessment."""
    if scenario:
        print(f"\n📋 Scenario: {scenario}")
    
    # Risk level emoji
    level_emoji = {
        "LOW": "🟢",
        "MEDIUM": "🟡",
        "HIGH": "🟠",
        "CRITICAL": "🔴"
    }
    
    emoji = level_emoji.get(assessment.risk_level, "⚪")
    
    print(f"   Account: {assessment.account_id}")
    print(f"   Risk Score: {assessment.risk_score}/100 {emoji} {assessment.risk_level}")
    print(f"   Dormant: {'Yes' if assessment.is_dormant_account else 'No'}", end="")
    if assessment.days_dormant:
        print(f" ({assessment.days_dormant} days)")
    else:
        print()
    print(f"   Explanation: {assessment.explanation}")
    print(f"   Recommendation: {assessment.recommendation}")
    
    print("\n   Risk Factor Breakdown:")
    for factor in sorted(assessment.factors, key=lambda f: -f.score_contribution):
        bar_len = int(factor.score_contribution / 2)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"     • {factor.factor_name:15} [{bar}] {factor.score_contribution:5.1f}")
        print(f"       {factor.description}")


def main():
    """Run the demo."""
    print_divider("Fraud Detection Service - Demo")
    
    # Load data
    print("\n📊 Loading test data...")
    data = load_test_data()
    reference_date = datetime.fromisoformat(data["reference_date"])
    
    # Initialize data store
    store = DataStore()
    
    for txn_data in data["transactions"]:
        txn = Transaction(
            transaction_id=txn_data["transaction_id"],
            account_id=txn_data["account_id"],
            amount=txn_data["amount"],
            transaction_type=TransactionType(txn_data["transaction_type"]),
            timestamp=datetime.fromisoformat(txn_data["timestamp"]),
            location=txn_data.get("location"),
            merchant=txn_data.get("merchant")
        )
        store.add_transaction(txn)
    
    print(f"   ✓ Loaded {store.total_transactions} transactions for {store.total_accounts} accounts")
    
    # Build profiles
    print("\n📈 Building account profiles...")
    profiler = AccountProfiler(store, reference_date=reference_date)
    profiles = profiler.build_all_profiles()
    
    dormant_accounts = profiler.get_dormant_accounts()
    active_accounts = profiler.get_active_accounts()
    
    print(f"   ✓ Active accounts: {len(active_accounts)}")
    print(f"   ✓ Dormant accounts: {len(dormant_accounts)}")
    
    # Initialize scorer
    scorer = RiskScorer(store, reference_date=reference_date)
    
    print_divider("Account Profiles Sample")
    
    # Show a few profiles
    sample_dormant = dormant_accounts[0] if dormant_accounts else None
    sample_active = active_accounts[0] if active_accounts else None
    
    if sample_active:
        print(f"\n🟢 Active Account: {sample_active.account_id}")
        print(f"   Last transaction: {sample_active.days_since_last_transaction} days ago")
        print(f"   Total transactions: {sample_active.total_transactions}")
        print(f"   Average amount: ${sample_active.average_amount:.2f}")
        print(f"   Common types: {', '.join(sample_active.typical_transaction_types)}")
    
    if sample_dormant:
        print(f"\n🔴 Dormant Account: {sample_dormant.account_id}")
        print(f"   Last transaction: {sample_dormant.days_since_last_transaction} days ago")
        print(f"   Total transactions: {sample_dormant.total_transactions}")
        print(f"   Average amount: ${sample_dormant.average_amount:.2f}")
        print(f"   Common types: {', '.join(sample_dormant.typical_transaction_types)}")
    
    print_divider("Risk Assessment Scenarios")
    
    # Scenario 1: Normal transaction on active account
    if sample_active:
        txn1 = TransactionRequest(
            account_id=sample_active.account_id,
            amount=sample_active.average_amount * 1.2,
            transaction_type=TransactionType(sample_active.typical_transaction_types[0]) if sample_active.typical_transaction_types else TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        assessment1 = scorer.calculate_risk(txn1)
        print_assessment(assessment1, "Normal transaction on active account")
    
    # Scenario 2: Large transaction on dormant account
    if sample_dormant:
        txn2 = TransactionRequest(
            account_id=sample_dormant.account_id,
            amount=sample_dormant.average_amount * 10,
            transaction_type=TransactionType.WIRE_TRANSFER,
            timestamp=reference_date
        )
        assessment2 = scorer.calculate_risk(txn2)
        print_assessment(assessment2, "Large wire transfer on dormant account")
    
    # Scenario 3: First international wire on dormant account
    if sample_dormant:
        txn3 = TransactionRequest(
            account_id=sample_dormant.account_id,
            amount=5000.00,
            transaction_type=TransactionType.INTERNATIONAL_WIRE,
            timestamp=reference_date,
            location="Lagos"
        )
        assessment3 = scorer.calculate_risk(txn3)
        print_assessment(assessment3, "First international wire to foreign location")
    
    # Scenario 4: Unknown account
    txn4 = TransactionRequest(
        account_id="ACC-UNKNOWN-999",
        amount=2500.00,
        transaction_type=TransactionType.WIRE_TRANSFER,
        timestamp=reference_date
    )
    assessment4 = scorer.calculate_risk(txn4)
    print_assessment(assessment4, "Transaction from unknown account")
    
    print_divider("Suspicious Test Cases from Generated Data")
    
    # Test the suspicious transactions from the generated data
    suspicious_cases = data.get("suspicious_test_cases", [])[:5]  # Show first 5
    
    for i, txn_data in enumerate(suspicious_cases, 1):
        txn = TransactionRequest(
            account_id=txn_data["account_id"],
            amount=txn_data["amount"],
            transaction_type=TransactionType(txn_data["transaction_type"]),
            timestamp=datetime.fromisoformat(txn_data["timestamp"]),
            location=txn_data.get("location")
        )
        
        assessment = scorer.calculate_risk(txn)
        reason = txn_data.get("_suspicious_reason", "Unknown")
        print_assessment(assessment, f"Test Case {i}: {reason}")
    
    print_divider("Summary Statistics")
    
    # Run all suspicious cases and show distribution
    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    
    for txn_data in suspicious_cases:
        txn = TransactionRequest(
            account_id=txn_data["account_id"],
            amount=txn_data["amount"],
            transaction_type=TransactionType(txn_data["transaction_type"]),
            timestamp=datetime.fromisoformat(txn_data["timestamp"]),
            location=txn_data.get("location")
        )
        assessment = scorer.calculate_risk(txn)
        risk_distribution[assessment.risk_level] += 1
    
    total_suspicious = len(suspicious_cases)
    print(f"\n📊 Risk Distribution for {total_suspicious} Suspicious Test Cases:")
    print(f"   🟢 LOW:      {risk_distribution['LOW']:3d} ({risk_distribution['LOW']/total_suspicious*100:.1f}%)")
    print(f"   🟡 MEDIUM:   {risk_distribution['MEDIUM']:3d} ({risk_distribution['MEDIUM']/total_suspicious*100:.1f}%)")
    print(f"   🟠 HIGH:     {risk_distribution['HIGH']:3d} ({risk_distribution['HIGH']/total_suspicious*100:.1f}%)")
    print(f"   🔴 CRITICAL: {risk_distribution['CRITICAL']:3d} ({risk_distribution['CRITICAL']/total_suspicious*100:.1f}%)")
    
    high_risk_pct = (risk_distribution['HIGH'] + risk_distribution['CRITICAL']) / total_suspicious * 100
    print(f"\n   ✓ Detection Rate (HIGH+CRITICAL): {high_risk_pct:.1f}%")
    
    print_divider()
    print("\n✅ Demo complete! Run the API server with:")
    print("   python main.py --serve")
    print("   # or: uvicorn app.api:app --reload")
    print("\n   Then visit http://localhost:8000/docs for the interactive API documentation.\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        import uvicorn
        from app.api import app
        print("Starting Fraud Detection API server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()
