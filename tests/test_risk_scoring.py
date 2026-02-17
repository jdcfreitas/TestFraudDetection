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
    
    # Edge case: Sparse account with only 2 historical transactions
    for i in range(2):
        txn_date = reference_date - timedelta(days=250 + 30 * i)
        transactions.append(Transaction(
            transaction_id=f"TXN-SPARSE-{i}",
            account_id="ACC-SPARSE-001",
            amount=25.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=txn_date,
            location="Manila"
        ))
    
    # Edge case: Recently dormant account - just crossed 180-day threshold (185 days)
    for i in range(6):
        txn_date = reference_date - timedelta(days=185 + 20 * i)
        transactions.append(Transaction(
            transaction_id=f"TXN-RECENT-DORMANT-{i}",
            account_id="ACC-RECENT-DORMANT-001",
            amount=80.0 + (i * 10),
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=txn_date,
            location="Kuala Lumpur"
        ))
    
    # Edge case: Borderline active account - 179 days since last transaction (just under threshold)
    for i in range(4):
        txn_date = reference_date - timedelta(days=179 + 30 * i)
        transactions.append(Transaction(
            transaction_id=f"TXN-BORDERLINE-{i}",
            account_id="ACC-BORDERLINE-001",
            amount=60.0,
            transaction_type=TransactionType.BILL_PAYMENT,
            timestamp=txn_date,
            location="Ho Chi Minh City"
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
        assert data_store.total_accounts == 6  # Six unique accounts (including edge cases)
    
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
        
        assert len(profiles) == 6  # Including edge case accounts
        assert "ACC-ACTIVE-001" in profiles
        assert "ACC-DORMANT-001" in profiles
        assert "ACC-DIVERSE-001" in profiles
        assert "ACC-SPARSE-001" in profiles
        assert "ACC-RECENT-DORMANT-001" in profiles
        assert "ACC-BORDERLINE-001" in profiles
    
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
            dormancy=0.60, amount_anomaly=0.15, type_anomaly=0.10, velocity=0.05, location_anomaly=0.10
        )
        scorer_high = RiskScorer(data_store, weights=high_dormancy_weights, reference_date=reference_date)
        
        # Scorer with low dormancy weight
        low_dormancy_weights = ScoringWeights(
            dormancy=0.10, amount_anomaly=0.40, type_anomaly=0.25, velocity=0.10, location_anomaly=0.15
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
        assert "location_anomaly" in factor_names
    
    def test_location_anomaly_common_location(self, data_store, sample_transactions, reference_date):
        """Test that transactions from common locations score low on location anomaly."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # ACC-ACTIVE-001 has all transactions from Singapore
        transaction = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="Singapore"  # Common location for this account
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        location_factor = next(f for f in assessment.factors if f.factor_name == "location_anomaly")
        assert location_factor.score_contribution == 0.0
        assert "common location" in location_factor.description.lower()
    
    def test_location_anomaly_international(self, data_store, sample_transactions, reference_date):
        """Test that international locations increase risk for domestic accounts."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # Transaction from common domestic location
        domestic_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="Singapore"
        )
        
        # Same transaction but from international location
        international_txn = TransactionRequest(
            account_id="ACC-ACTIVE-001",
            amount=50.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="London"  # International location
        )
        
        domestic_assessment = scorer.calculate_risk(domestic_txn)
        international_assessment = scorer.calculate_risk(international_txn)
        
        assert international_assessment.risk_score > domestic_assessment.risk_score
        
        intl_location_factor = next(f for f in international_assessment.factors if f.factor_name == "location_anomaly")
        assert intl_location_factor.score_contribution > 0
    
    def test_location_anomaly_dormant_international(self, data_store, sample_transactions, reference_date):
        """Test that international location on dormant account scores very high."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # ACC-DORMANT-001 typically transacts from Jakarta (domestic)
        transaction = TransactionRequest(
            account_id="ACC-DORMANT-001",
            amount=100.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date,
            location="Moscow"  # International location on dormant account
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        location_factor = next(f for f in assessment.factors if f.factor_name == "location_anomaly")
        # Should have high contribution due to international + dormant combination
        assert location_factor.score_contribution >= 10  # 90 * 0.15 = 13.5
        assert "international" in location_factor.description.lower() or "dormant" in location_factor.description.lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_sparse_account_minimal_history(self, data_store, sample_transactions, reference_date):
        """Test accounts with only 1-2 historical transactions."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # ACC-SPARSE-001 has only 2 transactions, both small ATM withdrawals
        profile = data_store.get_profile("ACC-SPARSE-001")
        assert profile.total_transactions == 2
        assert profile.is_dormant  # 250+ days since last transaction
        
        # Normal transaction for sparse account
        normal_txn = TransactionRequest(
            account_id="ACC-SPARSE-001",
            amount=30.0,  # Close to historical average of 25
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date,
            location="Manila"
        )
        
        # Anomalous transaction - large wire transfer
        anomalous_txn = TransactionRequest(
            account_id="ACC-SPARSE-001",
            amount=3000.0,  # 120x the historical average
            transaction_type=TransactionType.WIRE_TRANSFER,  # Never used this type
            timestamp=reference_date,
            location="Dubai"  # International location
        )
        
        normal_assessment = scorer.calculate_risk(normal_txn)
        anomalous_assessment = scorer.calculate_risk(anomalous_txn)
        
        # Sparse account should still flag anomalies
        assert anomalous_assessment.risk_score > normal_assessment.risk_score
        assert anomalous_assessment.risk_level in ["HIGH", "CRITICAL"]
        assert anomalous_assessment.account_status == "reactivating"
    
    def test_recently_dormant_account(self, data_store, sample_transactions, reference_date):
        """Test accounts that just crossed the 180-day dormancy threshold."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # ACC-RECENT-DORMANT-001 has 185 days since last transaction (just over threshold)
        profile = data_store.get_profile("ACC-RECENT-DORMANT-001")
        assert profile.is_dormant
        assert 180 <= profile.days_since_last_transaction < 200
        
        # Transaction on recently dormant account
        transaction = TransactionRequest(
            account_id="ACC-RECENT-DORMANT-001",
            amount=85.0,  # Within normal range for this account (avg ~105)
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date,
            location="Kuala Lumpur"
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        # Should be flagged but lower risk than long-dormant accounts
        assert assessment.is_dormant_account
        assert assessment.account_status == "reactivating"
        # Dormancy factor should be moderate (not at max)
        dormancy_factor = next(f for f in assessment.factors if f.factor_name == "dormancy")
        assert 10 < dormancy_factor.score_contribution < 25  # Moderate dormancy contribution
    
    def test_borderline_active_account(self, data_store, sample_transactions, reference_date):
        """Test accounts just under the 180-day dormancy threshold (179 days)."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # ACC-BORDERLINE-001 has 179 days since last transaction (just under threshold)
        profile = data_store.get_profile("ACC-BORDERLINE-001")
        assert not profile.is_dormant  # Should NOT be dormant
        assert profile.days_since_last_transaction == 179
        
        # Transaction on borderline account
        transaction = TransactionRequest(
            account_id="ACC-BORDERLINE-001",
            amount=60.0,
            transaction_type=TransactionType.BILL_PAYMENT,
            timestamp=reference_date,
            location="Ho Chi Minh City"
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        # Should be treated as active, not dormant
        assert not assessment.is_dormant_account
        assert assessment.account_status == "active"
        # Dormancy factor should be zero
        dormancy_factor = next(f for f in assessment.factors if f.factor_name == "dormancy")
        assert dormancy_factor.score_contribution == 0.0
    
    def test_recently_dormant_vs_long_dormant(self, data_store, sample_transactions, reference_date):
        """Test that long-dormant accounts score higher than recently dormant."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        # Same transaction type and amount for fair comparison
        recent_dormant_txn = TransactionRequest(
            account_id="ACC-RECENT-DORMANT-001",  # 185 days dormant
            amount=500.0,
            transaction_type=TransactionType.WIRE_TRANSFER,
            timestamp=reference_date,
            location="Singapore"
        )
        
        long_dormant_txn = TransactionRequest(
            account_id="ACC-DORMANT-001",  # 200+ days dormant
            amount=500.0,
            transaction_type=TransactionType.WIRE_TRANSFER,
            timestamp=reference_date,
            location="Singapore"
        )
        
        recent_assessment = scorer.calculate_risk(recent_dormant_txn)
        long_assessment = scorer.calculate_risk(long_dormant_txn)
        
        # Long-dormant should score higher due to greater dormancy contribution
        recent_dormancy = next(f for f in recent_assessment.factors if f.factor_name == "dormancy")
        long_dormancy = next(f for f in long_assessment.factors if f.factor_name == "dormancy")
        assert long_dormancy.score_contribution > recent_dormancy.score_contribution
    
    def test_sparse_account_no_baseline_for_std_dev(self, data_store, sample_transactions, reference_date):
        """Test that sparse accounts handle missing statistical baseline gracefully."""
        data_store.add_transactions_bulk(sample_transactions)
        profiler = AccountProfiler(data_store, reference_date=reference_date)
        profiler.build_all_profiles()
        scorer = RiskScorer(data_store, reference_date=reference_date)
        
        profile = data_store.get_profile("ACC-SPARSE-001")
        # With only 2 transactions, std dev should still be calculable
        assert profile.total_transactions == 2
        assert profile.std_dev_amount >= 0  # Should not error
        
        # Transaction should still be scorable
        transaction = TransactionRequest(
            account_id="ACC-SPARSE-001",
            amount=100.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date,
            location="Manila"
        )
        
        assessment = scorer.calculate_risk(transaction)
        assert assessment.risk_score >= 0
        assert assessment.risk_score <= 100


class TestConfiguration:
    """Tests for configuration loading and custom config values."""
    
    def test_custom_dormancy_threshold(self, data_store, reference_date):
        """Test that dormancy threshold can be configured."""
        from app.config import FraudDetectionConfig, DormancyConfig
        
        # Create config with 90-day dormancy threshold instead of 180
        custom_config = FraudDetectionConfig()
        custom_config.dormancy = DormancyConfig(threshold_days=90)
        
        # Create account with 100 days since last transaction
        # (dormant with 90-day threshold, active with 180-day threshold)
        transactions = [
            Transaction(
                transaction_id="TXN-CUSTOM-1",
                account_id="ACC-CUSTOM-001",
                amount=50.0,
                transaction_type=TransactionType.ATM_WITHDRAWAL,
                timestamp=reference_date - timedelta(days=100),
                location="Singapore"
            )
        ]
        data_store.add_transactions_bulk(transactions)
        
        # With custom 90-day threshold
        profiler_custom = AccountProfiler(data_store, reference_date=reference_date, config=custom_config)
        profile_custom = profiler_custom.build_profile("ACC-CUSTOM-001")
        assert profile_custom.is_dormant  # Should be dormant (100 > 90)
        
        # With default 180-day threshold
        default_config = FraudDetectionConfig()
        profiler_default = AccountProfiler(data_store, reference_date=reference_date, config=default_config)
        profile_default = profiler_default.build_profile("ACC-CUSTOM-001")
        assert not profile_default.is_dormant  # Should NOT be dormant (100 < 180)
    
    def test_custom_risk_weights(self, data_store, reference_date):
        """Test that risk weights can be configured via config object."""
        from app.config import FraudDetectionConfig, RiskWeightsConfig
        
        # Create config with high dormancy weight
        custom_config = FraudDetectionConfig()
        custom_config.risk_weights = RiskWeightsConfig(
            dormancy=0.60,
            amount_anomaly=0.15,
            type_anomaly=0.10,
            velocity=0.05,
            location_anomaly=0.10
        )
        
        transactions = [
            Transaction(
                transaction_id="TXN-WEIGHT-1",
                account_id="ACC-WEIGHT-001",
                amount=50.0,
                transaction_type=TransactionType.ATM_WITHDRAWAL,
                timestamp=reference_date - timedelta(days=200),
                location="Singapore"
            )
        ]
        data_store.add_transactions_bulk(transactions)
        
        profiler = AccountProfiler(data_store, reference_date=reference_date, config=custom_config)
        profiler.build_all_profiles()
        
        scorer = RiskScorer(data_store, reference_date=reference_date, config=custom_config)
        
        transaction = TransactionRequest(
            account_id="ACC-WEIGHT-001",
            amount=50.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=reference_date,
            location="Singapore"
        )
        
        assessment = scorer.calculate_risk(transaction)
        
        # Dormancy should contribute more with 60% weight
        dormancy_factor = next(f for f in assessment.factors if f.factor_name == "dormancy")
        # 200 days dormant should score ~47 raw, with 60% weight = ~28 contribution
        assert dormancy_factor.score_contribution > 20
    
    def test_config_from_yaml(self, tmp_path):
        """Test loading configuration from YAML file."""
        from app.config import FraudDetectionConfig
        
        config_content = """
dormancy:
  threshold_days: 120

velocity:
  window_minutes: 30
  threshold_count: 5

risk_weights:
  dormancy: 0.40
  amount_anomaly: 0.20
  type_anomaly: 0.15
  velocity: 0.10
  location_anomaly: 0.15

risk_levels:
  low_max: 20
  medium_max: 45
  high_max: 70
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        
        config = FraudDetectionConfig.from_yaml(config_file)
        
        assert config.dormancy.threshold_days == 120
        assert config.velocity.window_minutes == 30
        assert config.velocity.threshold_count == 5
        assert config.risk_weights.dormancy == 0.40
        assert config.risk_levels.low_max == 20
        assert config.risk_levels.medium_max == 45


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
