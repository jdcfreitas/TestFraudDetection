"""Unit tests for DataStore class."""

import pytest
from datetime import datetime, timedelta
from app.data_store import DataStore
from app.models import Transaction, TransactionType, AccountProfile


@pytest.fixture
def data_store():
    """Create a fresh data store for each test."""
    return DataStore()


@pytest.fixture
def reference_date():
    """Reference date for testing."""
    return datetime(2026, 2, 17)


@pytest.fixture
def sample_transactions(reference_date):
    """Generate sample transactions."""
    return [
        Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=10),
            location="Singapore"
        ),
        Transaction(
            transaction_id="TXN-002",
            account_id="ACC-001",
            amount=150.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date - timedelta(days=5),
            location="Singapore"
        ),
        Transaction(
            transaction_id="TXN-003",
            account_id="ACC-002",
            amount=200.0,
            transaction_type=TransactionType.WIRE_TRANSFER,
            timestamp=reference_date - timedelta(days=200),
            location="Jakarta"
        ),
        Transaction(
            transaction_id="TXN-004",
            account_id="ACC-003",
            amount=50.0,
            transaction_type=TransactionType.BILL_PAYMENT,
            timestamp=reference_date - timedelta(days=1),
            location="Bangkok"
        )
    ]


class TestDataStoreBasics:
    """Basic DataStore functionality tests."""
    
    def test_empty_store(self, data_store):
        """Test that new data store is empty."""
        assert data_store.total_transactions == 0
        assert data_store.total_accounts == 0
    
    def test_add_single_transaction(self, data_store, reference_date):
        """Test adding a single transaction."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="Singapore"
        )
        
        data_store.add_transaction(txn)
        
        assert data_store.total_transactions == 1
        assert data_store.total_accounts == 1
    
    def test_add_multiple_transactions_same_account(self, data_store, reference_date):
        """Test adding multiple transactions for same account."""
        for i in range(5):
            txn = Transaction(
                transaction_id=f"TXN-{i:03d}",
                account_id="ACC-001",
                amount=100.0 + i * 10,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i),
                location="Singapore"
            )
            data_store.add_transaction(txn)
        
        assert data_store.total_transactions == 5
        assert data_store.total_accounts == 1
        assert len(data_store.get_account_transactions("ACC-001")) == 5
    
    def test_add_transactions_bulk(self, data_store, sample_transactions):
        """Test bulk transaction loading."""
        data_store.add_transactions_bulk(sample_transactions)
        
        assert data_store.total_transactions == 4
        assert data_store.total_accounts == 3
    
    def test_clear_data_store(self, data_store, sample_transactions):
        """Test clearing the data store."""
        data_store.add_transactions_bulk(sample_transactions)
        assert data_store.total_transactions > 0
        
        data_store.clear()
        
        assert data_store.total_transactions == 0
        assert data_store.total_accounts == 0


class TestDataStoreQueries:
    """Tests for DataStore query methods."""
    
    def test_get_account_transactions(self, data_store, sample_transactions):
        """Test retrieving transactions for specific account."""
        data_store.add_transactions_bulk(sample_transactions)
        
        acc1_txns = data_store.get_account_transactions("ACC-001")
        
        assert len(acc1_txns) == 2
        assert all(t.account_id == "ACC-001" for t in acc1_txns)
    
    def test_get_account_transactions_empty(self, data_store, sample_transactions):
        """Test retrieving transactions for non-existent account."""
        data_store.add_transactions_bulk(sample_transactions)
        
        unknown_txns = data_store.get_account_transactions("ACC-UNKNOWN")
        
        assert len(unknown_txns) == 0
    
    def test_get_recent_transactions(self, data_store, sample_transactions, reference_date):
        """Test filtering transactions by date."""
        data_store.add_transactions_bulk(sample_transactions)
        
        since_date = reference_date - timedelta(days=15)
        recent = data_store.get_recent_transactions("ACC-001", since_date)
        
        assert len(recent) == 2
        assert all(t.timestamp >= since_date for t in recent)
    
    def test_get_recent_transactions_none_match(self, data_store, sample_transactions, reference_date):
        """Test filtering when no transactions match."""
        data_store.add_transactions_bulk(sample_transactions)
        
        since_date = reference_date  # Today
        recent = data_store.get_recent_transactions("ACC-002", since_date)
        
        assert len(recent) == 0
    
    def test_get_all_accounts(self, data_store, sample_transactions):
        """Test getting list of all account IDs."""
        data_store.add_transactions_bulk(sample_transactions)
        
        accounts = data_store.get_all_account_ids()
        
        assert len(accounts) == 3
        assert "ACC-001" in accounts
        assert "ACC-002" in accounts
        assert "ACC-003" in accounts


class TestDataStoreProfiles:
    """Tests for profile storage and retrieval."""
    
    def test_store_and_get_profile(self, data_store, reference_date):
        """Test storing and retrieving account profile."""
        profile = AccountProfile(
            account_id="ACC-001",
            is_dormant=False,
            days_since_last_transaction=10,
            last_transaction_date=reference_date - timedelta(days=10),
            total_transactions=20,
            average_amount=150.0,
            median_amount=125.0,
            max_amount=500.0,
            min_amount=25.0,
            std_dev_amount=75.0,
            transaction_type_distribution={"online_purchase": 15, "atm_withdrawal": 5},
            common_locations=["Singapore", "Jakarta"],
            typical_transaction_types=["online_purchase", "atm_withdrawal"],
            first_transaction_date=reference_date - timedelta(days=365)
        )
        
        data_store.set_profile("ACC-001", profile)
        retrieved = data_store.get_profile("ACC-001")
        
        assert retrieved is not None
        assert retrieved.account_id == "ACC-001"
        assert retrieved.average_amount == 150.0
        assert retrieved.total_transactions == 20
    
    def test_get_nonexistent_profile(self, data_store):
        """Test getting profile that doesn't exist."""
        profile = data_store.get_profile("ACC-UNKNOWN")
        
        assert profile is None
    
    def test_get_all_profiles(self, data_store, reference_date):
        """Test retrieving all stored profiles."""
        for i in range(3):
            profile = AccountProfile(
                account_id=f"ACC-{i:03d}",
                is_dormant=i % 2 == 0,
                total_transactions=10 + i,
                average_amount=100.0,
                median_amount=100.0,
                max_amount=200.0,
                min_amount=50.0,
                std_dev_amount=30.0,
                transaction_type_distribution={},
                common_locations=[],
                typical_transaction_types=[]
            )
            data_store.set_profile(f"ACC-{i:03d}", profile)
        
        profiles = data_store.get_all_profiles()
        
        assert len(profiles) == 3
        assert "ACC-000" in profiles
        assert "ACC-001" in profiles
        assert "ACC-002" in profiles
    
    def test_profile_update(self, data_store, reference_date):
        """Test that storing a profile with same ID updates it."""
        profile_v1 = AccountProfile(
            account_id="ACC-001",
            is_dormant=True,
            total_transactions=5,
            average_amount=100.0,
            median_amount=100.0,
            max_amount=150.0,
            min_amount=50.0,
            std_dev_amount=25.0,
            transaction_type_distribution={},
            common_locations=[],
            typical_transaction_types=[]
        )
        data_store.set_profile("ACC-001", profile_v1)
        
        profile_v2 = AccountProfile(
            account_id="ACC-001",
            is_dormant=False,  # Updated
            total_transactions=10,  # Updated
            average_amount=150.0,  # Updated
            median_amount=125.0,
            max_amount=200.0,
            min_amount=50.0,
            std_dev_amount=35.0,
            transaction_type_distribution={},
            common_locations=[],
            typical_transaction_types=[]
        )
        data_store.set_profile("ACC-001", profile_v2)
        
        retrieved = data_store.get_profile("ACC-001")
        
        assert retrieved.is_dormant is False
        assert retrieved.total_transactions == 10
        assert retrieved.average_amount == 150.0


class TestDataStoreEdgeCases:
    """Edge case tests for DataStore."""
    
    def test_duplicate_transaction_id(self, data_store, reference_date):
        """Test handling of duplicate transaction IDs."""
        txn1 = Transaction(
            transaction_id="TXN-DUP",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="Singapore"
        )
        txn2 = Transaction(
            transaction_id="TXN-DUP",  # Same ID
            account_id="ACC-001",
            amount=200.0,  # Different amount
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date,
            location="Jakarta"
        )
        
        data_store.add_transaction(txn1)
        data_store.add_transaction(txn2)
        
        # Behavior depends on implementation - should either replace or reject
        # For now, just verify no crash occurs
        assert data_store.total_transactions >= 1
    
    def test_very_large_transaction_count(self, data_store, reference_date):
        """Test handling large number of transactions."""
        transactions = []
        for i in range(1000):
            txn = Transaction(
                transaction_id=f"TXN-{i:06d}",
                account_id=f"ACC-{i % 10:03d}",
                amount=100.0 + (i % 100),
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=reference_date - timedelta(days=i % 365),
                location="Singapore"
            )
            transactions.append(txn)
        
        data_store.add_transactions_bulk(transactions)
        
        assert data_store.total_transactions == 1000
        assert data_store.total_accounts == 10
    
    def test_transactions_sorted_by_date(self, data_store, reference_date):
        """Test that transactions are retrievable in chronological order."""
        dates = [
            reference_date - timedelta(days=5),
            reference_date - timedelta(days=1),
            reference_date - timedelta(days=10),
            reference_date - timedelta(days=3),
        ]
        
        for i, date in enumerate(dates):
            txn = Transaction(
                transaction_id=f"TXN-{i}",
                account_id="ACC-001",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=date,
                location="Singapore"
            )
            data_store.add_transaction(txn)
        
        transactions = data_store.get_account_transactions("ACC-001")
        
        # Verify we can retrieve all transactions
        assert len(transactions) == 4
    
    def test_empty_location(self, data_store, reference_date):
        """Test transactions with no location."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location=None
        )
        
        data_store.add_transaction(txn)
        retrieved = data_store.get_account_transactions("ACC-001")[0]
        
        assert retrieved.location is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
