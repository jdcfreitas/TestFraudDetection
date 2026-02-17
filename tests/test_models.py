"""Unit tests for Pydantic models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    Transaction,
    TransactionRequest,
    TransactionType,
    RiskFactor,
    RiskAssessment,
    AccountProfile,
    AccountStatus,
    HealthResponse,
    BatchTransactionRequest,
    BatchRiskAssessmentResult,
    BatchRiskAssessmentResponse,
    BatchSummary
)


class TestTransactionType:
    """Tests for TransactionType enum."""
    
    def test_all_types_exist(self):
        """Verify all expected transaction types are defined."""
        expected_types = [
            "atm_withdrawal",
            "online_purchase",
            "wire_transfer",
            "bill_payment",
            "peer_to_peer",
            "pos_purchase",
            "international_wire"
        ]
        
        for type_value in expected_types:
            assert TransactionType(type_value) is not None
    
    def test_enum_string_value(self):
        """Test that enum values are strings."""
        assert TransactionType.ATM_WITHDRAWAL.value == "atm_withdrawal"
        assert TransactionType.ONLINE_PURCHASE.value == "online_purchase"
        assert str(TransactionType.WIRE_TRANSFER) == "TransactionType.WIRE_TRANSFER"
    
    def test_invalid_type_raises(self):
        """Test that invalid transaction type raises ValueError."""
        with pytest.raises(ValueError):
            TransactionType("invalid_type")


class TestTransaction:
    """Tests for Transaction model."""
    
    def test_valid_transaction(self):
        """Test creating a valid transaction."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=datetime.now(),
            location="Singapore",
            merchant="Amazon"
        )
        
        assert txn.transaction_id == "TXN-001"
        assert txn.account_id == "ACC-001"
        assert txn.amount == 100.0
        assert txn.transaction_type == TransactionType.ONLINE_PURCHASE
        assert txn.location == "Singapore"
        assert txn.merchant == "Amazon"
    
    def test_minimal_transaction(self):
        """Test transaction with only required fields."""
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=50.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=datetime.now()
        )
        
        assert txn.location is None
        assert txn.merchant is None
    
    def test_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Transaction(
                transaction_id="TXN-001",
                account_id="ACC-001",
                amount=-100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=datetime.now()
            )
        
        assert "greater than 0" in str(exc_info.value).lower()
    
    def test_zero_amount_rejected(self):
        """Test that zero amount is rejected."""
        with pytest.raises(ValidationError):
            Transaction(
                transaction_id="TXN-001",
                account_id="ACC-001",
                amount=0.0,
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=datetime.now()
            )
    
    def test_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            Transaction(
                transaction_id="TXN-001",
                account_id="ACC-001",
                # missing amount
                transaction_type=TransactionType.ONLINE_PURCHASE,
                timestamp=datetime.now()
            )


class TestTransactionRequest:
    """Tests for TransactionRequest model."""
    
    def test_valid_request(self):
        """Test creating a valid transaction request."""
        req = TransactionRequest(
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            location="Singapore"
        )
        
        assert req.account_id == "ACC-001"
        assert req.amount == 100.0
        assert req.timestamp is not None  # Auto-generated
    
    def test_custom_timestamp(self):
        """Test providing custom timestamp."""
        custom_time = datetime(2025, 6, 15, 14, 30, 0)
        req = TransactionRequest(
            account_id="ACC-001",
            amount=50.0,
            transaction_type=TransactionType.ATM_WITHDRAWAL,
            timestamp=custom_time
        )
        
        assert req.timestamp == custom_time
    
    def test_transaction_type_from_string(self):
        """Test that transaction type can be provided as string."""
        req = TransactionRequest(
            account_id="ACC-001",
            amount=50.0,
            transaction_type="online_purchase"
        )
        
        assert req.transaction_type == TransactionType.ONLINE_PURCHASE


class TestRiskFactor:
    """Tests for RiskFactor model."""
    
    def test_valid_risk_factor(self):
        """Test creating a valid risk factor."""
        factor = RiskFactor(
            factor_name="dormancy",
            score_contribution=15.5,
            description="Account has been inactive for 200 days"
        )
        
        assert factor.factor_name == "dormancy"
        assert factor.score_contribution == 15.5
        assert "200 days" in factor.description


class TestRiskAssessment:
    """Tests for RiskAssessment model."""
    
    def test_valid_assessment(self):
        """Test creating a valid risk assessment."""
        assessment = RiskAssessment(
            account_id="ACC-001",
            risk_score=65,
            risk_level="HIGH",
            account_status="reactivating",
            explanation="Dormant account reactivation detected",
            factors=[
                RiskFactor(
                    factor_name="dormancy",
                    score_contribution=30.0,
                    description="Account dormant for 200+ days"
                )
            ],
            is_dormant_account=True,
            days_dormant=205,
            recommendation="Require step-up authentication"
        )
        
        assert assessment.risk_score == 65
        assert assessment.risk_level == "HIGH"
        assert assessment.is_dormant_account
        assert len(assessment.factors) == 1
    
    def test_risk_score_bounds(self):
        """Test that risk score must be between 0 and 100."""
        with pytest.raises(ValidationError):
            RiskAssessment(
                account_id="ACC-001",
                risk_score=150,  # Invalid: > 100
                risk_level="CRITICAL",
                account_status="dormant",
                explanation="Test",
                factors=[],
                is_dormant_account=True,
                recommendation="Test"
            )
        
        with pytest.raises(ValidationError):
            RiskAssessment(
                account_id="ACC-001",
                risk_score=-10,  # Invalid: < 0
                risk_level="LOW",
                account_status="active",
                explanation="Test",
                factors=[],
                is_dormant_account=False,
                recommendation="Test"
            )


class TestAccountProfile:
    """Tests for AccountProfile model."""
    
    def test_valid_profile(self):
        """Test creating a valid account profile."""
        profile = AccountProfile(
            account_id="ACC-001",
            is_dormant=True,
            days_since_last_transaction=200,
            last_transaction_date=datetime(2025, 7, 1),
            total_transactions=50,
            average_amount=125.50,
            median_amount=100.0,
            max_amount=500.0,
            min_amount=10.0,
            std_dev_amount=75.25,
            transaction_type_distribution={
                "online_purchase": 30,
                "atm_withdrawal": 15,
                "bill_payment": 5
            },
            common_locations=["Singapore", "Kuala Lumpur"],
            typical_transaction_types=["online_purchase", "atm_withdrawal"],
            first_transaction_date=datetime(2023, 1, 15)
        )
        
        assert profile.is_dormant
        assert profile.days_since_last_transaction == 200
        assert profile.total_transactions == 50
        assert len(profile.common_locations) == 2
    
    def test_new_account_profile(self):
        """Test profile for account with no transactions."""
        profile = AccountProfile(
            account_id="ACC-NEW",
            is_dormant=True,  # No transactions = dormant by default
            days_since_last_transaction=None,
            last_transaction_date=None,
            total_transactions=0,
            average_amount=0.0,
            median_amount=0.0,
            max_amount=0.0,
            min_amount=0.0,
            std_dev_amount=0.0,
            transaction_type_distribution={},
            common_locations=[],
            typical_transaction_types=[],
            first_transaction_date=None
        )
        
        assert profile.total_transactions == 0
        assert profile.average_amount == 0.0
        assert len(profile.typical_transaction_types) == 0


class TestAccountStatus:
    """Tests for AccountStatus enum."""
    
    def test_all_statuses_exist(self):
        """Verify all expected account statuses are defined."""
        assert AccountStatus.ACTIVE.value == "active"
        assert AccountStatus.DORMANT.value == "dormant"
        assert AccountStatus.REACTIVATING.value == "reactivating"
        assert AccountStatus.NEW.value == "new"
    
    def test_status_count(self):
        """Verify exactly 4 statuses exist."""
        assert len(AccountStatus) == 4


class TestBatchModels:
    """Tests for batch request/response models."""
    
    def test_batch_request_valid(self):
        """Test creating a valid batch request."""
        batch = BatchTransactionRequest(
            transactions=[
                TransactionRequest(
                    account_id="ACC-001",
                    amount=100.0,
                    transaction_type=TransactionType.ONLINE_PURCHASE
                ),
                TransactionRequest(
                    account_id="ACC-002",
                    amount=200.0,
                    transaction_type=TransactionType.ATM_WITHDRAWAL
                )
            ]
        )
        
        assert len(batch.transactions) == 2
    
    def test_batch_request_empty_rejected(self):
        """Test that empty batch is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BatchTransactionRequest(transactions=[])
        
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value).lower()
    
    def test_batch_request_max_size(self):
        """Test that batch size is limited to 1000."""
        transactions = [
            TransactionRequest(
                account_id=f"ACC-{i:04d}",
                amount=100.0,
                transaction_type=TransactionType.ONLINE_PURCHASE
            )
            for i in range(1001)
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            BatchTransactionRequest(transactions=transactions)
        
        assert "max_length" in str(exc_info.value).lower() or "at most 1000" in str(exc_info.value).lower()
    
    def test_batch_summary(self):
        """Test creating a batch summary."""
        summary = BatchSummary(
            low_risk_count=5,
            medium_risk_count=3,
            high_risk_count=2,
            critical_risk_count=0,
            average_risk_score=35.5,
            max_risk_score=72,
            reactivating_accounts=2
        )
        
        assert summary.low_risk_count == 5
        assert summary.reactivating_accounts == 2
        assert summary.average_risk_score == 35.5


class TestHealthResponse:
    """Tests for HealthResponse model."""
    
    def test_valid_health_response(self):
        """Test creating a valid health response."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            accounts_loaded=100,
            transactions_loaded=5000
        )
        
        assert response.status == "healthy"
        assert response.accounts_loaded == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
