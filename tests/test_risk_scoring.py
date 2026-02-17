"""Unit tests for the CedarBank Fraud Detection Service."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Transaction, TransactionRequest, TransactionType, AccountProfile, AccountStatus
from app.data_store import DataStore
from app.account_profiler import AccountProfiler
from app.risk_scorer import RiskScorer, ScoringWeights


# Test fixtures
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
    """Generate sample transactions for testing."""
    transactions = []
    
    # Active account with regular transactions
    for i in range(12):
        txn_date = reference_date - timedelta(days=30 * i + 5)
        transactions.append(Transaction(
            transaction_id=f"TXN-ACTIVE-{i}",
            account_id="ACC-ACTIVE-001",
            amount=50.0 + (i * 5),
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=txn_date,
            location="Singapore"
        ))
    
    # Dormant account - no transactions for 200 days
    for i in range(5):
        txn_date = reference_date - timedelta(days=200 + 30 * i)
        transactions.append(Transaction(
            transaction_id=f"TXN-DORMANT-{i}",
            account_id="ACC-DORMANT-001",
            amount=30.0 + (i * 2),
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=txn_date,
            location="Jakarta"
        ))
    
    # Account with diverse transaction types
    types = [
        TransactionType.ONLINE_PURCHASE,
        TransactionType.ATM_WITHDRAWAL,
        TransactionType.BILL_PAYMENT,
        TransactionType.PEER_TO_PEER
    ]
    for i, txn_type in enumerate(types * 3):
        txn_date = reference_date - timedelta(days=10 * i + 5)
        transactions.append(Transaction(
            transaction_id=f"TXN-DIVERSE-{i}",
            account_id="ACC-DIVERSE-001",
            amount=100.0,
            transaction_type=txn_type,
            timestamp=txn_date,
            location="Bangkok"
        ))
    
    return transactions


class TestDataStore:
    """Tests for the DataStore class."""
    
    def test_add_transaction(self, data_store):
        """Test adding a single transaction."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=datetime.now(),
            location="Singapore"
        )
        
        data_store.add_transaction(txn)
        
        assert data_store.total_transactions == 1
        assert data_store.total_accounts == 1
        assert len(data_store.get_account_transactions("ACC-001")) == 1
    
    def test_add_transactions_bulk(self, data_store, sample_transactions):
        """Test adding multiple transactions at once."""
        data_store.add_transactions_bulk(sample_transactions)
        
        assert data_store.total_transactions == len(sample_transactions)
        assert data_store.total_accounts == 3  # Three unique accounts
    
    def test_get_recent_transactions(self, data_store, sample_transactions, reference_date):
        """Test filtering transactions by date range."""
        data_store.add_transactions_bulk(sample_transactions)
        
        since = reference_date - timedelta(days=60)
        recent = data_store.get_recent_transactions("ACC-ACTIVE-001", since)
        
        assert len(recent) > 0
        assert all(t.timestamp >= since for t in recent)


class TestAccountProfiler:
    """Tests for the AccountProfiler class."""
    
    def test_build_profile_active_account(self, data_store, sample_transactions, reference_date):
        """Test profiling an active account."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-ACTIVE-001")
        
        assert profile.account_id == "ACC-ACTIVE-001"
        assert not profile.is_dormant
        assert profile.total_transactions == 12
        assert profile.average_amount > 0
    
    def test_build_profile_dormant_account(self, data_store, sample_transactions, reference_date):
        """Test profiling a dormant account."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-DORMANT-001")
        
        assert profile.account_id == "ACC-DORMANT-001"
        assert profile.is_dormant
        assert profile.days_since_last_transaction >= 200
        assert profile.total_transactions == 5
    
    def test_build_profile_unknown_account(self, data_store, reference_date):
        """Test profiling an account with no transactions."""
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-UNKNOWN")
        
        assert profile.account_id == "ACC-UNKNOWN"
        assert profile.is_dormant
        assert profile.total_transactions == 0
    
    def test_build_all_profiles(self, data_store, sample_transactions, reference_date):
        """Test building profiles for all accounts."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profiles = profiler.build_all_profiles()
        
        assert len(profiles) == 3
        assert "ACC-ACTIVE-001" in profiles
        assert "ACC-DORMANT-001" in profiles
        assert "ACC-DIVERSE-001" in profiles
    
    def test_transaction_type_distribution(self, data_store, sample_transactions, reference_date):
        """Test that transaction type distribution is calculated correctly."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        
        profile = profiler.build_profile("ACC-DIVERSE-001")
        
        assert len(profile.transaction_type_distribution) == 4
        assert all(count == 3 for count in profile.transaction_type_distribution.values())


class TestRiskScorer:
    """Tests for the RiskScorer class."""
    
    def test_low_risk_active_account(self, data_store, sample_transactions, reference_date):
        """Test that normal transactions on active accounts score low."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=55.0,  # Within normal range
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        assert assessment.risk_score <= 25
        assert assessment.risk_level == "LOW"
        assert not assessment.is_dormant_account
    
    def test_high_risk_dormant_account(self, data_store, sample_transactions, reference_date):
        """Test that transactions on dormant accounts score high."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-DORMANT-001",
            amount=500.0,  # Much higher than historical average (~35)
            transaction_type=TransactionType.WIRE_TRANSFER,  # New type
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        assert assessment.risk_score >= 50
        assert assessment.risk_level in ["HIGH", "CRITICAL"]
        assert assessment.is_dormant_account
    
    def test_amount_anomaly_detection(self, data_store, sample_transactions, reference_date):
        """Test that large amount deviations are detected."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # Normal amount
        normal_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=60.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        # Anomalous amount (10x normal)
        anomalous_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=750.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        normal_assessment = scorer.calculate_risk(normal_txn)
        anomalous_assessment = scorer.calculate_risk(anomalous_txn)
        
        assert anomalous_assessment.risk_score > normal_assessment.risk_score
    
    def test_type_anomaly_detection(self, data_store, sample_transactions, reference_date):
        """Test that unusual transaction types are detected."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # Common type for this account
        common_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        # Unusual type (first international wire)
        unusual_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.INTERNATIONAL_WIRE,
            timestamp=reference_date
        )
        
        common_assessment = scorer.calculate_risk(common_txn)
        unusual_assessment = scorer.calculate_risk(unusual_txn)
        
        assert unusual_assessment.risk_score > common_assessment.risk_score
    
    def test_unknown_account_high_risk(self, data_store, reference_date):
        """Test that unknown accounts receive high risk scores."""
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-UNKNOWN",
            amount=1000.0,
            transaction_type=TransactionType.WIRE_TRANSFER,
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        assert assessment.risk_score >= 75
        assert assessment.risk_level == "CRITICAL"
        assert assessment.account_status == AccountStatus.NEW.value
    
    def test_account_status_active(self, data_store, sample_transactions, reference_date):
        """Test that active accounts have ACTIVE status."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=55.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        assert assessment.account_status == AccountStatus.ACTIVE.value
    
    def test_account_status_reactivating(self, data_store, sample_transactions, reference_date):
        """Test that dormant accounts get REACTIVATING status when transacting."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # Transaction on a dormant account
        transaction = TransactionRequest(
            account_id="ACC-DORMANT-001",
            amount=100.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        assert assessment.account_status == AccountStatus.REACTIVATING.value
        assert assessment.is_dormant_account

    def test_custom_weights(self, data_store, sample_transactions, reference_date):
        """Test that custom weights affect scoring."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        
        # Scorer with high dormancy weight
        high_dormancy_weights = ScoringWeights(
            dormancy=0.70, amount_anomaly=0.15, type_anomaly=0.10, velocity=0.05
        )
        scorer_high = RiskScorer(data_store, weights=high_dormancy_weights, reference_date=reference_date)
        
        # Scorer with low dormancy weight
        low_dormancy_weights = ScoringWeights(
            dormancy=0.10, amount_anomaly=0.50, type_anomaly=0.30, velocity=0.10
        )
        scorer_low = RiskScorer(data_store, weights=low_dormancy_weights, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-DORMANT-001",
            amount=35.0,  # Normal amount
            transaction_type=TransactionType.ATM_WITHDRAWAL,  # Normal type
            timestamp=reference_date
        )
        
        high_score = scorer_high.calculate_risk(transaction)
        low_score = scorer_low.calculate_risk(transaction)
        
        # High dormancy weight should produce higher score
        assert high_score.risk_score > low_score.risk_score
    
    def test_risk_factors_included(self, data_store, sample_transactions, reference_date):
        """Test that all risk factors are included in assessment."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        transaction = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        factor_names = {f.factor_name for f in assessment.factors}
        assert "dormancy" in factor_names
        assert "amount_anomaly" in factor_names
        assert "type_anomaly" in factor_names
        assert "velocity" in factor_names


class TestIntegration:
    """Integration tests using the generated test data."""
    
    @pytest.fixture
    def loaded_system(self):
        """Load the generated test data."""
        data_path = Path(__file__).parent.parent / "data" / "test_transactions.json"
        
        if not data_path.exists():
            pytest.skip("Test data not generated. Run generate_test_data.py first.")
        
        with open(data_path) as f:
            data = json.load(f)
        
        store = DataStore()
        reference_date = datetime.fromisoformat(data["reference_date"])
        
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
        
        profiler = AccountProfiler(store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(store, reference_date=reference_date)
        
        return store, profiler, scorer, data
    
    def test_suspicious_transactions_high_risk(self, loaded_system):
        """Test that suspicious test cases score high."""
        store, profiler, scorer, data = loaded_system
        
        suspicious_cases = data.get("suspicious_test_cases", [])
        if not suspicious_cases:
            pytest.skip("No suspicious test cases in data")
        
        high_risk_count = 0
        for txn_data in suspicious_cases:
            transaction = TransactionRequest(
                account_id=txn_data["account_id"],
                amount=txn_data["amount"],
                transaction_type=TransactionType(txn_data["transaction_type"]),
                timestamp=datetime.fromisoformat(txn_data["timestamp"]),
                location=txn_data.get("location")
            )
            
            assessment = scorer.calculate_risk(transaction)
            
            if assessment.risk_score >= 50:
                high_risk_count += 1
        
        # At least 50% of suspicious transactions should score HIGH or CRITICAL
        # (Some scenarios like velocity spikes on already-flagged accounts may score lower)
        assert high_risk_count / len(suspicious_cases) >= 0.50
    
    def test_dormant_account_detection(self, loaded_system):
        """Test that dormant accounts are correctly identified."""
        store, profiler, scorer, data = loaded_system
        
        dormant_accounts = profiler.get_dormant_accounts()
        active_accounts = profiler.get_active_accounts()
        
        # Should have both dormant and active accounts
        assert len(dormant_accounts) > 0
        assert len(active_accounts) > 0
        
        # Dormant accounts should have 180+ days since last transaction
        for profile in dormant_accounts:
            assert profile.days_since_last_transaction >= 180


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
