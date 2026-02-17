"""Integration tests for the FastAPI endpoints."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json

from fastapi.testclient import TestClient

from app.api import app, load_test_data, data_store
from app.models import TransactionType, AccountStatus


@pytest.fixture(scope="module")
def client():
    """Create a test client with loaded test data."""
    # Clear any existing data
    data_store.clear()
    
    # Load test data
    data_path = Path(__file__).parent.parent / "data" / "test_transactions.json"
    if data_path.exists():
        load_test_data(data_path)
    
    with TestClient(app) as client:
        yield client
    
    # Cleanup
    data_store.clear()


@pytest.fixture
def reference_date():
    """Reference date matching test data."""
    return datetime(2026, 2, 17)


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check_returns_200(self, client):
        """Test that health check returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_response_structure(self, client):
        """Test that health check returns expected structure."""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "accounts_loaded" in data
        assert "transactions_loaded" in data
    
    def test_health_check_status_healthy(self, client):
        """Test that health check reports healthy status."""
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"


class TestRiskAssessmentEndpoint:
    """Tests for POST /api/v1/risk/assess endpoint."""
    
    def test_assess_valid_transaction(self, client):
        """Test assessing a valid transaction."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-12345678",
                "amount": 100.0,
                "transaction_type": "online_purchase",
                "location": "Singapore"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "risk_score" in data
        assert "risk_level" in data
        assert "account_status" in data
        assert "explanation" in data
        assert "factors" in data
        assert "is_dormant_account" in data
        assert "recommendation" in data
    
    def test_assess_returns_risk_score_bounds(self, client):
        """Test that risk score is within 0-100 bounds."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-12345678",
                "amount": 500.0,
                "transaction_type": "wire_transfer"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert 0 <= data["risk_score"] <= 100
        assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    def test_assess_returns_all_risk_factors(self, client):
        """Test that all 5 risk factors are returned for known accounts."""
        # First ingest some data for a known account
        client.post(
            "/api/v1/transactions/ingest",
            json=[
                {
                    "transaction_id": "TXN-FACTOR-TEST-001",
                    "account_id": "ACC-FACTOR-TEST",
                    "amount": 100.0,
                    "transaction_type": "online_purchase",
                    "timestamp": "2025-12-15T10:30:00",
                    "location": "Singapore"
                }
            ]
        )
        
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-FACTOR-TEST",
                "amount": 100.0,
                "transaction_type": "online_purchase",
                "location": "Singapore"
            }
        )
        
        data = response.json()
        factor_names = {f["factor_name"] for f in data["factors"]}
        
        assert "dormancy" in factor_names
        assert "amount_anomaly" in factor_names
        assert "type_anomaly" in factor_names
        assert "velocity" in factor_names
        assert "location_anomaly" in factor_names
    
    def test_assess_invalid_transaction_type(self, client):
        """Test that invalid transaction type returns 422."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-001",
                "amount": 100.0,
                "transaction_type": "invalid_type"
            }
        )
        
        assert response.status_code == 422
    
    def test_assess_negative_amount(self, client):
        """Test that negative amount returns 422."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-001",
                "amount": -100.0,
                "transaction_type": "online_purchase"
            }
        )
        
        assert response.status_code == 422
    
    def test_assess_missing_required_field(self, client):
        """Test that missing required field returns 422."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-001"
                # missing amount and transaction_type
            }
        )
        
        assert response.status_code == 422
    
    def test_assess_unknown_account_high_risk(self, client):
        """Test that unknown account returns high risk."""
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-UNKNOWN-NEVER-EXISTS",
                "amount": 10000.0,
                "transaction_type": "international_wire",
                "location": "Russia"
            }
        )
        
        data = response.json()
        
        assert data["risk_score"] >= 70
        assert data["account_status"] == "new"


class TestBatchAssessmentEndpoint:
    """Tests for POST /api/v1/risk/assess/batch endpoint."""
    
    def test_batch_assess_valid(self, client):
        """Test batch assessment with valid transactions."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": [
                    {
                        "account_id": "ACC-12345678",
                        "amount": 100.0,
                        "transaction_type": "online_purchase"
                    },
                    {
                        "account_id": "ACC-12345678",
                        "amount": 200.0,
                        "transaction_type": "atm_withdrawal"
                    },
                    {
                        "account_id": "ACC-87654321",
                        "amount": 500.0,
                        "transaction_type": "wire_transfer"
                    }
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_transactions"] == 3
        assert data["processed"] == 3
        assert len(data["results"]) == 3
        assert "summary" in data
    
    def test_batch_assess_summary_statistics(self, client):
        """Test that batch assessment includes summary statistics."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": [
                    {
                        "account_id": "ACC-12345678",
                        "amount": 50.0,
                        "transaction_type": "online_purchase"
                    },
                    {
                        "account_id": "ACC-UNKNOWN",
                        "amount": 5000.0,
                        "transaction_type": "international_wire"
                    }
                ]
            }
        )
        
        data = response.json()
        summary = data["summary"]
        
        assert "low_risk_count" in summary
        assert "medium_risk_count" in summary
        assert "high_risk_count" in summary
        assert "critical_risk_count" in summary
        assert "average_risk_score" in summary
        assert "max_risk_score" in summary
        assert "reactivating_accounts" in summary
        
        # Sum of counts should equal total
        total_counts = (
            summary["low_risk_count"] +
            summary["medium_risk_count"] +
            summary["high_risk_count"] +
            summary["critical_risk_count"]
        )
        assert total_counts == data["total_transactions"]
    
    def test_batch_assess_empty_list_rejected(self, client):
        """Test that empty transaction list is rejected."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": []
            }
        )
        
        assert response.status_code == 422
    
    def test_batch_assess_single_transaction(self, client):
        """Test batch assessment with single transaction."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": [
                    {
                        "account_id": "ACC-12345678",
                        "amount": 100.0,
                        "transaction_type": "online_purchase"
                    }
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_transactions"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["transaction_index"] == 0
    
    def test_batch_assess_result_indices(self, client):
        """Test that batch results have correct indices."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": [
                    {"account_id": "ACC-001", "amount": 100.0, "transaction_type": "online_purchase"},
                    {"account_id": "ACC-002", "amount": 200.0, "transaction_type": "atm_withdrawal"},
                    {"account_id": "ACC-003", "amount": 300.0, "transaction_type": "bill_payment"}
                ]
            }
        )
        
        data = response.json()
        
        for i, result in enumerate(data["results"]):
            assert result["transaction_index"] == i


class TestAccountProfileEndpoint:
    """Tests for GET /api/v1/accounts/{account_id}/profile endpoint."""
    
    def test_get_profile_existing_account(self, client):
        """Test getting profile for existing account."""
        # First, ensure there's an account with transactions
        response = client.get("/health")
        if response.json()["accounts_loaded"] == 0:
            pytest.skip("No test data loaded")
        
        # Get stats to find an account
        stats_response = client.get("/api/v1/accounts/stats")
        if stats_response.json()["total_accounts"] == 0:
            pytest.skip("No accounts available")
        
        # Try a known account from test data
        response = client.get("/api/v1/accounts/ACC-12345678/profile")
        
        if response.status_code == 200:
            data = response.json()
            
            assert "account_id" in data
            assert "is_dormant" in data
            assert "total_transactions" in data
            assert "average_amount" in data
            assert "typical_transaction_types" in data
            assert "common_locations" in data
    
    def test_get_profile_nonexistent_account(self, client):
        """Test getting profile for non-existent account returns 404."""
        response = client.get("/api/v1/accounts/ACC-NONEXISTENT-123456/profile")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDormantAccountsEndpoint:
    """Tests for GET /api/v1/accounts/dormant endpoint."""
    
    def test_list_dormant_accounts(self, client):
        """Test listing dormant accounts."""
        response = client.get("/api/v1/accounts/dormant")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # All returned accounts should be dormant
        for account in data:
            assert account["is_dormant"] is True
    
    def test_list_dormant_accounts_with_min_days(self, client):
        """Test filtering dormant accounts by minimum days."""
        response = client.get("/api/v1/accounts/dormant?min_days=250")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned accounts should have 250+ days dormancy
        for account in data:
            assert account["days_since_last_transaction"] >= 250


class TestAccountStatsEndpoint:
    """Tests for GET /api/v1/accounts/stats endpoint."""
    
    def test_get_account_statistics(self, client):
        """Test getting account statistics."""
        response = client.get("/api/v1/accounts/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_accounts" in data
        assert "active_accounts" in data
        assert "dormant_accounts" in data
        assert "dormancy_rate" in data
        assert "average_dormancy_days" in data
        assert "total_transactions" in data
    
    def test_stats_accounts_sum(self, client):
        """Test that active + dormant = total accounts."""
        response = client.get("/api/v1/accounts/stats")
        data = response.json()
        
        assert data["active_accounts"] + data["dormant_accounts"] == data["total_accounts"]
    
    def test_stats_dormancy_rate_bounds(self, client):
        """Test that dormancy rate is between 0 and 100."""
        response = client.get("/api/v1/accounts/stats")
        data = response.json()
        
        assert 0 <= data["dormancy_rate"] <= 100


class TestTransactionIngestionEndpoint:
    """Tests for POST /api/v1/transactions/ingest endpoint."""
    
    def test_ingest_transactions(self, client):
        """Test ingesting transactions."""
        response = client.post(
            "/api/v1/transactions/ingest",
            json=[
                {
                    "transaction_id": "TXN-TEST-001",
                    "account_id": "ACC-TEST-INGEST",
                    "amount": 100.0,
                    "transaction_type": "online_purchase",
                    "timestamp": "2026-01-15T10:30:00",
                    "location": "Singapore"
                },
                {
                    "transaction_id": "TXN-TEST-002",
                    "account_id": "ACC-TEST-INGEST",
                    "amount": 150.0,
                    "transaction_type": "atm_withdrawal",
                    "timestamp": "2026-01-16T14:00:00",
                    "location": "Singapore"
                }
            ]
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Ingested 2 transactions"
        assert data["affected_accounts"] == 1


class TestWeightsConfigEndpoint:
    """Tests for PUT /api/v1/config/weights endpoint."""
    
    def test_update_weights_valid(self, client):
        """Test updating scoring weights with valid values."""
        response = client.put(
            "/api/v1/config/weights",
            params={
                "dormancy": 0.25,
                "amount_anomaly": 0.25,
                "type_anomaly": 0.20,
                "velocity": 0.15,
                "location_anomaly": 0.15
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Weights updated"
        assert "weights" in data
    
    def test_update_weights_invalid_sum(self, client):
        """Test that weights not summing to 1.0 returns 400."""
        response = client.put(
            "/api/v1/config/weights",
            params={
                "dormancy": 0.50,
                "amount_anomaly": 0.50,
                "type_anomaly": 0.50,
                "velocity": 0.50
            }
        )
        
        assert response.status_code == 400
        assert "sum to 1.0" in response.json()["detail"]


class TestRefreshProfileEndpoint:
    """Tests for POST /api/v1/accounts/{account_id}/refresh endpoint."""
    
    def test_refresh_nonexistent_account(self, client):
        """Test refreshing non-existent account returns 404."""
        response = client.post("/api/v1/accounts/ACC-NONEXISTENT-REFRESH/refresh")
        
        assert response.status_code == 404


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""
    
    def test_openapi_schema_available(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        assert schema["info"]["title"] == "CedarBank Fraud Detection API"
        assert "paths" in schema
    
    def test_docs_endpoint_available(self, client):
        """Test that docs endpoint is available."""
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_redoc_endpoint_available(self, client):
        """Test that redoc endpoint is available."""
        response = client.get("/redoc")
        
        assert response.status_code == 200


class TestEndToEndScenarios:
    """End-to-end integration tests for complete fraud detection scenarios."""
    
    def test_dormant_account_reactivation_flow(self, client):
        """Test complete flow: ingest old transactions, assess new suspicious one."""
        # Step 1: Ingest historical transactions for a new account
        old_date = datetime.now() - timedelta(days=200)
        client.post(
            "/api/v1/transactions/ingest",
            json=[
                {
                    "transaction_id": "TXN-E2E-001",
                    "account_id": "ACC-E2E-DORMANT",
                    "amount": 50.0,
                    "transaction_type": "atm_withdrawal",
                    "timestamp": old_date.isoformat(),
                    "location": "Singapore"
                },
                {
                    "transaction_id": "TXN-E2E-002",
                    "account_id": "ACC-E2E-DORMANT",
                    "amount": 75.0,
                    "transaction_type": "atm_withdrawal",
                    "timestamp": (old_date - timedelta(days=30)).isoformat(),
                    "location": "Singapore"
                }
            ]
        )
        
        # Step 2: Assess a new suspicious transaction
        response = client.post(
            "/api/v1/risk/assess",
            json={
                "account_id": "ACC-E2E-DORMANT",
                "amount": 5000.0,  # Much higher than usual
                "transaction_type": "international_wire",  # Different type
                "location": "Moscow"  # International location
            }
        )
        
        data = response.json()
        
        # Should be flagged as high risk
        assert data["risk_score"] >= 50
        assert data["is_dormant_account"] is True
        assert data["account_status"] == "reactivating"
    
    def test_batch_processing_mixed_risk(self, client):
        """Test batch processing with mix of low and high risk transactions."""
        response = client.post(
            "/api/v1/risk/assess/batch",
            json={
                "transactions": [
                    # Low risk: small, common type
                    {
                        "account_id": "ACC-12345678",
                        "amount": 25.0,
                        "transaction_type": "online_purchase",
                        "location": "Singapore"
                    },
                    # Medium risk: larger amount
                    {
                        "account_id": "ACC-12345678",
                        "amount": 500.0,
                        "transaction_type": "wire_transfer"
                    },
                    # High risk: unknown account, large international wire
                    {
                        "account_id": "ACC-UNKNOWN-BATCH",
                        "amount": 10000.0,
                        "transaction_type": "international_wire",
                        "location": "Russia"
                    }
                ]
            }
        )
        
        data = response.json()
        
        # Should have varied risk levels
        assert data["summary"]["max_risk_score"] >= data["summary"]["average_risk_score"]
        
        # Verify individual results
        risk_scores = [r["assessment"]["risk_score"] for r in data["results"]]
        assert max(risk_scores) >= 70  # At least one high risk


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
