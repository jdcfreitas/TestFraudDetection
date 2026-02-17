"""
Test Data Generator for CedarBank Fraud Detection Service.

Generates realistic transaction data with:
- 50+ unique accounts
- 1,000+ historical transactions over 12 months
- Mix of active and dormant accounts
- Various transaction types and amounts
- Suspicious transactions for testing
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# Configuration
NUM_ACCOUNTS = 55
NUM_TRANSACTIONS = 1200
ACTIVE_ACCOUNTS_RATIO = 0.65  # 65% active, 35% dormant
REFERENCE_DATE = datetime(2026, 2, 17)  # "Today" for the simulation
HISTORY_START = REFERENCE_DATE - timedelta(days=365)  # 12 months of history

# Transaction types with typical characteristics
TRANSACTION_TYPES = {
    "atm_withdrawal": {"min": 20, "max": 500, "weight": 0.25},
    "online_purchase": {"min": 5, "max": 300, "weight": 0.30},
    "wire_transfer": {"min": 100, "max": 5000, "weight": 0.05},
    "bill_payment": {"min": 30, "max": 500, "weight": 0.20},
    "peer_to_peer": {"min": 10, "max": 500, "weight": 0.15},
    "pos_purchase": {"min": 5, "max": 200, "weight": 0.04},
    "international_wire": {"min": 500, "max": 10000, "weight": 0.01},
}

# Locations (Southeast Asia focus for CedarBank)
LOCATIONS = [
    "Singapore", "Jakarta", "Bangkok", "Kuala Lumpur", "Manila",
    "Ho Chi Minh City", "Hanoi", "Bali", "Phuket", "Penang",
    "Cebu", "Chiang Mai", "Yangon", "Phnom Penh", "Brunei"
]

# Some international locations for anomaly testing
INTERNATIONAL_LOCATIONS = [
    "London", "New York", "Dubai", "Tokyo", "Sydney",
    "Moscow", "Lagos", "Sao Paulo"
]

# Merchants by transaction type
MERCHANTS = {
    "online_purchase": ["Amazon", "Lazada", "Shopee", "Tokopedia", "Grab", "Foodpanda"],
    "pos_purchase": ["7-Eleven", "FamilyMart", "Starbucks", "McDonalds", "Uniqlo"],
    "bill_payment": ["Electricity Corp", "Water Authority", "Telco Services", "Insurance Co"],
}


class AccountProfile:
    """Represents an account with its behavioral characteristics."""
    
    def __init__(self, account_id: str, is_dormant: bool):
        self.account_id = account_id
        self.is_dormant = is_dormant
        
        # Randomly assign account characteristics
        self.spending_tier = random.choice(["low", "medium", "high"])
        self.primary_location = random.choice(LOCATIONS)
        self.secondary_locations = random.sample(
            [loc for loc in LOCATIONS if loc != self.primary_location],
            k=random.randint(1, 3)
        )
        
        # Transaction type preferences
        self.preferred_types = self._assign_preferred_types()
        
        # Amount ranges based on spending tier
        self.amount_multiplier = {
            "low": 0.3,
            "medium": 1.0,
            "high": 2.5
        }[self.spending_tier]
        
        # Transaction frequency
        if is_dormant:
            # Dormant accounts: last transaction was 180+ days ago
            self.dormancy_start = REFERENCE_DATE - timedelta(
                days=random.randint(180, 400)
            )
            self.transactions_per_month = random.randint(1, 5)
        else:
            self.dormancy_start = None
            self.transactions_per_month = random.randint(3, 15)
    
    def _assign_preferred_types(self) -> list[str]:
        """Assign 2-4 preferred transaction types to the account."""
        # Weight towards common types
        types = list(TRANSACTION_TYPES.keys())
        weights = [TRANSACTION_TYPES[t]["weight"] for t in types]
        
        num_preferred = random.randint(2, 4)
        preferred = []
        for _ in range(num_preferred):
            choice = random.choices(types, weights=weights)[0]
            if choice not in preferred:
                preferred.append(choice)
        
        return preferred


def generate_accounts(num_accounts: int) -> list[AccountProfile]:
    """Generate account profiles."""
    accounts = []
    num_dormant = int(num_accounts * (1 - ACTIVE_ACCOUNTS_RATIO))
    
    for i in range(num_accounts):
        account_id = f"ACC-{str(uuid.uuid4())[:8].upper()}"
        is_dormant = i < num_dormant
        accounts.append(AccountProfile(account_id, is_dormant))
    
    # Shuffle to mix dormant and active
    random.shuffle(accounts)
    return accounts


def generate_transaction(
    account: AccountProfile,
    timestamp: datetime,
    force_type: Optional[str] = None
) -> dict:
    """Generate a single transaction for an account."""
    # Select transaction type
    if force_type:
        txn_type = force_type
    else:
        # 80% chance of preferred type, 20% chance of random
        if random.random() < 0.8 and account.preferred_types:
            txn_type = random.choice(account.preferred_types)
        else:
            txn_type = random.choice(list(TRANSACTION_TYPES.keys()))
    
    # Generate amount based on type and account tier
    type_config = TRANSACTION_TYPES[txn_type]
    base_amount = random.uniform(type_config["min"], type_config["max"])
    amount = round(base_amount * account.amount_multiplier, 2)
    
    # Select location
    if random.random() < 0.85:
        location = account.primary_location
    elif random.random() < 0.95:
        location = random.choice(account.secondary_locations)
    else:
        location = random.choice(LOCATIONS)
    
    # Select merchant if applicable
    merchant = None
    if txn_type in MERCHANTS:
        merchant = random.choice(MERCHANTS[txn_type])
    
    return {
        "transaction_id": f"TXN-{str(uuid.uuid4())[:12].upper()}",
        "account_id": account.account_id,
        "amount": amount,
        "transaction_type": txn_type,
        "timestamp": timestamp.isoformat(),
        "location": location,
        "merchant": merchant
    }


def generate_transactions(accounts: list[AccountProfile]) -> list[dict]:
    """Generate historical transactions for all accounts."""
    transactions = []
    
    for account in accounts:
        # Determine transaction date range
        if account.is_dormant:
            # Transactions only until dormancy start
            end_date = account.dormancy_start
        else:
            # Active accounts transact until reference date
            end_date = REFERENCE_DATE - timedelta(days=random.randint(0, 30))
        
        # Generate transactions throughout the history period
        current_date = HISTORY_START
        while current_date < end_date:
            # Generate some transactions this month
            num_txns = random.randint(1, account.transactions_per_month + 2)
            
            for _ in range(num_txns):
                # Random day within the month
                day_offset = random.randint(0, 28)
                txn_date = current_date + timedelta(
                    days=day_offset,
                    hours=random.randint(6, 22),
                    minutes=random.randint(0, 59)
                )
                
                if txn_date < end_date:
                    txn = generate_transaction(account, txn_date)
                    transactions.append(txn)
            
            current_date += timedelta(days=30)
    
    return transactions


def generate_suspicious_transactions(accounts: list[AccountProfile]) -> list[dict]:
    """Generate suspicious transactions for testing risk detection."""
    suspicious = []
    
    # Get dormant accounts for suspicious activity
    dormant_accounts = [a for a in accounts if a.is_dormant]
    
    # Scenario 1: Large transaction on dormant account (3 cases)
    for account in random.sample(dormant_accounts, min(3, len(dormant_accounts))):
        txn = generate_transaction(
            account,
            REFERENCE_DATE - timedelta(hours=random.randint(1, 24))
        )
        # Make amount very large relative to typical
        txn["amount"] = round(txn["amount"] * random.uniform(8, 15), 2)
        txn["_suspicious_reason"] = "Large amount on dormant account"
        suspicious.append(txn)
    
    # Scenario 2: First-ever wire transfer on dormant account (2 cases)
    wire_candidates = [
        a for a in dormant_accounts 
        if "wire_transfer" not in a.preferred_types and "international_wire" not in a.preferred_types
    ]
    for account in random.sample(wire_candidates, min(2, len(wire_candidates))):
        txn = generate_transaction(
            account,
            REFERENCE_DATE - timedelta(hours=random.randint(1, 12)),
            force_type="international_wire"
        )
        txn["amount"] = round(random.uniform(2000, 8000), 2)
        txn["location"] = random.choice(INTERNATIONAL_LOCATIONS)
        txn["_suspicious_reason"] = "First international wire on dormant account"
        suspicious.append(txn)
    
    # Scenario 3: Rapid succession of transactions after dormancy (2 cases)
    for account in random.sample(dormant_accounts, min(2, len(dormant_accounts))):
        base_time = REFERENCE_DATE - timedelta(hours=random.randint(2, 6))
        for i in range(4):  # 4 rapid transactions
            txn = generate_transaction(
                account,
                base_time + timedelta(minutes=random.randint(5, 15) * i)
            )
            txn["amount"] = round(txn["amount"] * random.uniform(2, 4), 2)
            txn["_suspicious_reason"] = f"Velocity spike - transaction {i+1} of 4"
            suspicious.append(txn)
    
    # Scenario 4: Geographic anomaly + dormancy (2 cases)
    for account in random.sample(dormant_accounts, min(2, len(dormant_accounts))):
        txn = generate_transaction(
            account,
            REFERENCE_DATE - timedelta(hours=random.randint(1, 48))
        )
        txn["location"] = random.choice(INTERNATIONAL_LOCATIONS)
        txn["amount"] = round(txn["amount"] * random.uniform(3, 6), 2)
        txn["_suspicious_reason"] = "Geographic anomaly on dormant account"
        suspicious.append(txn)
    
    # Scenario 5: Edge case - account with only 1-2 historical transactions
    sparse_account = AccountProfile(f"ACC-SPARSE-{random.randint(100,999)}", is_dormant=True)
    sparse_account.dormancy_start = REFERENCE_DATE - timedelta(days=250)
    
    # Add minimal history
    sparse_txn = generate_transaction(
        sparse_account,
        HISTORY_START + timedelta(days=30)
    )
    sparse_txn["amount"] = 25.00  # Small amount
    suspicious.append(sparse_txn)
    
    # Now a suspicious large transaction
    suspicious_sparse = generate_transaction(
        sparse_account,
        REFERENCE_DATE - timedelta(hours=3),
        force_type="wire_transfer"
    )
    suspicious_sparse["amount"] = 3500.00
    suspicious_sparse["_suspicious_reason"] = "Large wire on sparse history dormant account"
    suspicious.append(suspicious_sparse)
    
    return suspicious


def main():
    """Generate and save test data."""
    print("Generating CedarBank test data...")
    
    # Set random seed for reproducibility
    random.seed(42)
    
    # Generate accounts
    accounts = generate_accounts(NUM_ACCOUNTS)
    print(f"Generated {len(accounts)} accounts")
    print(f"  - Active: {sum(1 for a in accounts if not a.is_dormant)}")
    print(f"  - Dormant: {sum(1 for a in accounts if a.is_dormant)}")
    
    # Generate historical transactions
    transactions = generate_transactions(accounts)
    print(f"Generated {len(transactions)} historical transactions")
    
    # Generate suspicious transactions (these are NOT added to historical data)
    # They represent "new" transactions we want to test against dormant accounts
    suspicious = generate_suspicious_transactions(accounts)
    print(f"Generated {len(suspicious)} suspicious test transactions")
    
    # Historical transactions only (suspicious are kept separate for testing)
    all_transactions = transactions
    
    # Sort by timestamp
    all_transactions.sort(key=lambda t: t["timestamp"])
    
    # Prepare output data
    output = {
        "reference_date": REFERENCE_DATE.isoformat(),
        "metadata": {
            "total_accounts": len(accounts),
            "active_accounts": sum(1 for a in accounts if not a.is_dormant),
            "dormant_accounts": sum(1 for a in accounts if a.is_dormant),
            "total_transactions": len(all_transactions),
            "suspicious_transactions": len(suspicious),
            "date_range": {
                "start": HISTORY_START.isoformat(),
                "end": REFERENCE_DATE.isoformat()
            }
        },
        "transactions": all_transactions,
        "suspicious_test_cases": suspicious
    }
    
    # Save to file
    output_path = Path(__file__).parent / "test_transactions.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nTest data saved to: {output_path}")
    print(f"Total file size: {output_path.stat().st_size / 1024:.1f} KB")
    
    # Print some statistics
    print("\nTransaction type distribution:")
    type_counts = {}
    for txn in transactions:
        t = txn["transaction_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count} ({count/len(transactions)*100:.1f}%)")


if __name__ == "__main__":
    main()
