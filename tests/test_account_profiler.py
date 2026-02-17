"""Unit tests for AccountProfiler class."""

import pytest
from datetime import datetime, timedelta

from app.models import Transaction, TransactionType, AccountProfile
from app.data_store import DataStore
from app.account_profiler import AccountProfiler
from app.config import FraudDetectionConfig, DormancyConfig


@pytest.fixture
def data_store():
    """Create a fresh data store for each test."""
    return DataStore()


@pytest.fixture
def reference_date():
    """Reference date for testing."""
    return datetime(2026, 2, 17)


@pytest.fixture
def active_account_transactions(reference_date):
    """Transactions for an active account."""
    transactions = []
    for i in range(20):
        txn = Transaction(
            transaction_id=f"TXN-ACTIVE-{i}",
            account_id="ACC-ACTIVE",
            amount=50.0 + (i * 5),  # 50-145
            transaction_type=TransactionType.ONLINE_PURCHASE if i % 3 == 0 
                else TransactionType.ATM_WITHDRAWAL if i % 3 == 1 
                else TransactionType.BILL_PAYMENT,
            timestamp=reference_date - timedelta(days=i * 7),  # Weekly transactions
            location="Singapore" if i % 2 == 0 else "Kuala Lumpur"
        )
        transactions.append(txn)
    return transactions


@pytest.fixture
def dormant_account_transactions(reference_date):
    """Transactions for a dormant account."""
    transactions = []
    base_date = reference_date - timedelta(days=200)  # Last transaction 200 days ago
    for i in range(10):
        txn = Transaction(
            transaction_id=f"TXN-DORMANT-{i}",
            account_id="ACC-DORMANT",
            amount=100.0 + (i * 10),
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=base_date - timedelta(days=i * 14),  # Bi-weekly
            location="Jakarta"
        )
        transactions.append(txn)
    return transactions


class TestProfilerBasics:
    """Basic AccountProfiler functionality tests."""
    
    def test_build_profile_active_account(self, data_store, active_account_transactions, reference_date):
        """Test building profile for active account."""
        data_store.add_transactions_bulk(active_account_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-ACTIVE")
        
        assert profile.account_id == "ACC-ACTIVE"
        assert not profile.is_dormant
        assert profile.total_transactions == 20
        assert profile.days_since_last_transaction == 0  # Most recent is today-offset
    
    def test_build_profile_dormant_account(self, data_store, dormant_account_transactions, reference_date):
        """Test building profile for dormant account."""
        data_store.add_transactions_bulk(dormant_account_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-DORMANT")
        
        assert profile.account_id == "ACC-DORMANT"
        assert profile.is_dormant
        assert profile.days_since_last_transaction >= 200
        assert profile.total_transactions == 10
    
    def test_build_profile_unknown_account(self, data_store, reference_date):
        """Test building profile for account with no transactions."""
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-UNKNOWN")
        
        assert profile.account_id == "ACC-UNKNOWN"
        assert profile.is_dormant  # No transactions = dormant
        assert profile.total_transactions == 0
        assert profile.average_amount == 0.0
        assert len(profile.typical_transaction_types) == 0
    
    def test_build_all_profiles(self, data_store, active_account_transactions, dormant_account_transactions, reference_date):
        """Test building profiles for all accounts."""
        data_store.add_transactions_bulk(active_account_transactions)
        data_store.add_transactions_bulk(dormant_account_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profiles = profiler.build_all_profiles()
        
        assert len(profiles) == 2
        assert "ACC-ACTIVE" in profiles
        assert "ACC-DORMANT" in profiles


class TestProfilerStatistics:
    """Tests for statistical calculations in profiler."""
    
    def test_average_amount(self, data_store, reference_date):
        """Test average amount calculation."""
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0 * (i + 1),  # 100, 200, 300, 400, 500
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.average_amount == 300.0  # (100+200+300+400+500)/5
    
    def test_median_amount(self, data_store, reference_date):
        """Test median amount calculation."""
        # Amounts: 50, 100, 150, 200, 250
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=50.0 + (i * 50),
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.median_amount == 150.0  # Middle value
    
    def test_min_max_amount(self, data_store, reference_date):
        """Test min and max amount calculation."""
        amounts = [25.0, 100.0, 500.0, 75.0, 250.0]
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=amounts[i],
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.min_amount == 25.0
        assert profile.max_amount == 500.0
    
    def test_std_dev_amount(self, data_store, reference_date):
        """Test standard deviation calculation."""
        # All same amounts should have 0 std dev
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,  # All same
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.std_dev_amount == 0.0
    
    def test_single_transaction_stats(self, data_store, reference_date):
        """Test statistics with only one transaction."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=10),
            location="Singapore"
        )
        data_store.add_transaction(txn)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.average_amount == 100.0
        assert profile.median_amount == 100.0
        assert profile.min_amount == 100.0
        assert profile.max_amount == 100.0
        assert profile.std_dev_amount == 0.0


class TestProfilerTransactionTypes:
    """Tests for transaction type analysis."""
    
    def test_transaction_type_distribution(self, data_store, reference_date):
        """Test transaction type distribution calculation."""
        types = [
            TransactionType.ONLINE_PURCHASE,
            TransactionType.ONLINE_PURCHASE,
            TransactionType.ONLINE_PURCHASE,
            TransactionType.ATM_WITHDRAWAL,
            TransactionType.ATM_WITHDRAWAL,
            TransactionType.BILL_PAYMENT
        ]
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,
                transaction_type=types[i],
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            for i in range(6)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.transaction_type_distribution["online_purchase"] == 3
        assert profile.transaction_type_distribution["atm_withdrawal"] == 2
        assert profile.transaction_type_distribution["bill_payment"] == 1
    
    def test_typical_transaction_types(self, data_store, reference_date):
        """Test that typical transaction types are identified."""
        # Create transactions with varying type frequency
        transactions = []
        for i in range(10):
            transactions.append(Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            ))
        for i in range(3):
            transactions.append(Transaction(
                transaction_id=f"TXN-ATM-{i}",
                account_id="ACC-001",
                amount=50.0,
                transaction_type=TransactionType.ATM_WITHDRAWAL,
                timestamp=reference_date - timedelta(days=i + 10),
                location="Singapore"
            ))
        
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        # Online purchase should be in typical types (most common)
        assert "online_purchase" in profile.typical_transaction_types


class TestProfilerLocations:
    """Tests for location analysis."""
    
    def test_common_locations(self, data_store, reference_date):
        """Test common locations identification."""
        locations = ["Singapore", "Singapore", "Singapore", "Jakarta", "Bangkok"]
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location=locations[i]
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert "Singapore" in profile.common_locations
        assert profile.common_locations[0] == "Singapore"  # Most common first
    
    def test_no_locations(self, data_store, reference_date):
        """Test handling transactions with no location data."""
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location=None
            )
            for i in range(5)
        ]
        data_store.add_transactions_bulk(transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert len(profile.common_locations) == 0


class TestProfilerDormancy:
    """Tests for dormancy detection."""
    
    def test_dormancy_threshold_default(self, data_store, reference_date):
        """Test default 180-day dormancy threshold."""
        # Transaction 179 days ago - should be active
        txn_active = Transaction(
            transaction_id="TXN-ACTIVE",
            account_id="ACC-ACTIVE",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=179),
            location="Singapore"
        )
        # Transaction 181 days ago - should be dormant
        txn_dormant = Transaction(
            transaction_id="TXN-DORMANT",
            account_id="ACC-DORMANT",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=181),
            location="Singapore"
        )
        
        data_store.add_transaction(txn_active)
        data_store.add_transaction(txn_dormant)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile_active = profiler.build_profile("ACC-ACTIVE")
        profile_dormant = profiler.build_profile("ACC-DORMANT")
        
        assert not profile_active.is_dormant
        assert profile_dormant.is_dormant
    
    def test_dormancy_threshold_custom(self, data_store, reference_date):
        """Test custom dormancy threshold via config."""
        # Transaction 100 days ago
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=100),
            location="Singapore"
        )
        data_store.add_transaction(txn)
        
        # With 90-day threshold - should be dormant
        config_90 = FraudDetectionConfig()
        config_90.dormancy = DormancyConfig(threshold_days=90)
        profiler_90 = AccountProfiler(data_store, reference_date=reference_date, config=config_90)
        profile_90 = profiler_90.build_profile("ACC-001")
        assert profile_90.is_dormant
        
        # With 180-day threshold - should be active
        config_180 = FraudDetectionConfig()
        config_180.dormancy = DormancyConfig(threshold_days=180)
        profiler_180 = AccountProfiler(data_store, reference_date=reference_date, config=config_180)
        profile_180 = profiler_180.build_profile("ACC-001")
        assert not profile_180.is_dormant
    
    def test_days_since_last_transaction(self, data_store, reference_date):
        """Test accurate calculation of days since last transaction."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=45),
            location="Singapore"
        )
        data_store.add_transaction(txn)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-001")
        
        assert profile.days_since_last_transaction == 45


class TestProfilerDormantAccounts:
    """Tests for dormant account listing."""
    
    def test_get_dormant_accounts(self, data_store, reference_date):
        """Test getting list of dormant accounts."""
        # Active account
        for i in range(5):
            data_store.add_transaction(Transaction(
                transaction_id=f"TXN-ACTIVE-{i}",
                account_id="ACC-ACTIVE",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i * 10),
                location="Singapore"
            ))
        
        # Dormant accounts
        for acc in ["ACC-DORMANT-1", "ACC-DORMANT-2"]:
            data_store.add_transaction(Transaction(
                transaction_id=f"TXN-{acc}",
                account_id=acc,
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=200),
                location="Singapore"
            ))
        
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        
        dormant = profiler.get_dormant_accounts()
        
        assert len(dormant) == 2
        assert all(p.is_dormant for p in dormant)
    
    def test_get_active_accounts(self, data_store, reference_date):
        """Test getting list of active accounts."""
        # Active accounts
        for acc in ["ACC-ACTIVE-1", "ACC-ACTIVE-2", "ACC-ACTIVE-3"]:
            data_store.add_transaction(Transaction(
                transaction_id=f"TXN-{acc}",
                account_id=acc,
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=10),
                location="Singapore"
            ))
        
        # Dormant account
        data_store.add_transaction(Transaction(
            transaction_id="TXN-DORMANT",
            account_id="ACC-DORMANT",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=200),
            location="Singapore"
        ))
        
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        
        active = profiler.get_active_accounts()
        
        assert len(active) == 3
        assert all(not p.is_dormant for p in active)


class TestProfilerRefresh:
    """Tests for profile refresh functionality."""
    
    def test_refresh_profile(self, data_store, reference_date):
        """Test refreshing a profile after new transactions."""
        # Initial transaction
        txn1 = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=10),
            location="Singapore"
        )
        data_store.add_transaction(txn1)
        
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profile_v1 = profiler.build_profile("ACC-001")
        assert profile_v1.total_transactions == 1
        assert profile_v1.average_amount == 100.0
        
        # Add new transaction
        txn2 = Transaction(
            transaction_id="TXN-002",
            account_id="ACC-001",
            amount=200.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date - timedelta(days=5),
            location="Jakarta"
        )
        data_store.add_transaction(txn2)
        
        # Refresh profile
        profile_v2 = profiler.refresh_profile("ACC-001")
        
        assert profile_v2.total_transactions == 2
        assert profile_v2.average_amount == 150.0  # (100+200)/2
        assert "Jakarta" in profile_v2.common_locations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
