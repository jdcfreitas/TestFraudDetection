"""FastAPI application for CedarBank Fraud Detection Service."""

import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .models import (
    TransactionRequest,
    RiskAssessment,
    AccountProfile,
    HealthResponse,
    Transaction,
    TransactionType,
    BatchTransactionRequest,
    BatchRiskAssessmentResponse,
    BatchRiskAssessmentResult,
    BatchSummary
)
from .data_store import data_store
from .account_profiler import AccountProfiler
from .risk_scorer import RiskScorer, ScoringWeights


# Global instances
profiler: Optional[AccountProfiler] = None
scorer: Optional[RiskScorer] = None


def load_test_data(data_path: Path, reference_date: Optional[datetime] = None) -> None:
    """Load test data from JSON file and build profiles."""
    global profiler, scorer
    
    if not data_path.exists():
        print(f"Warning: Test data file not found at {data_path}")
        return
    
    with open(data_path, "r") as f:
        data = json.load(f)
    
    transactions = []
    for txn_data in data.get("transactions", []):
        txn = Transaction(
            transaction_id=txn_data["transaction_id"],
            account_id=txn_data["account_id"],
            amount=txn_data["amount"],
            transaction_type=TransactionType(txn_data["transaction_type"]),
            timestamp=datetime.fromisoformat(txn_data["timestamp"]),
            location=txn_data.get("location"),
            merchant=txn_data.get("merchant")
        )
        transactions.append(txn)
    
    data_store.add_transactions_bulk(transactions)
    
    # Use reference date from data file or provided date
    ref_date = reference_date
    if ref_date is None and "reference_date" in data:
        ref_date = datetime.fromisoformat(data["reference_date"])
    
    # Build profiles
    profiler = AccountProfiler(data_store, reference_date=ref_date)
    profiler.build_all_profiles()
    
    # Initialize scorer
    scorer = RiskScorer(data_store, reference_date=ref_date)
    
    print(f"Loaded {len(transactions)} transactions for {data_store.total_accounts} accounts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global profiler, scorer
    
    # Load test data on startup
    data_path = Path(__file__).parent.parent / "data" / "test_transactions.json"
    load_test_data(data_path)
    
    # Initialize profiler and scorer if not already done
    if profiler is None:
        profiler = AccountProfiler(data_store)
    if scorer is None:
        scorer = RiskScorer(data_store)
    
    yield
    
    # Cleanup
    data_store.clear()


# Create FastAPI app
app = FastAPI(
    title="CedarBank Fraud Detection API",
    description="""
    Real-time fraud detection service for identifying suspicious dormant account reactivation patterns.
    
    ## Features
    - Transaction risk scoring based on account behavioral baselines
    - Dormant account detection (180+ days inactive)
    - Amount anomaly detection
    - Transaction type anomaly detection
    - Velocity spike detection
    
    ## Risk Levels
    - **LOW** (0-25): Transaction appears normal
    - **MEDIUM** (26-50): Flag for post-transaction review
    - **HIGH** (51-75): Require step-up authentication
    - **CRITICAL** (76-100): Block and require manual review
    """,
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check service health and data status."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        accounts_loaded=data_store.total_accounts,
        transactions_loaded=data_store.total_transactions
    )


@app.post("/api/v1/risk/assess", response_model=RiskAssessment, tags=["Risk Assessment"])
async def assess_transaction_risk(transaction: TransactionRequest):
    """
    Assess the risk of a transaction in real-time.
    
    This endpoint evaluates a transaction against the account's behavioral baseline
    and returns a risk score with explanation.
    
    **Risk Factors Evaluated:**
    - Dormancy: How long has the account been inactive?
    - Amount Anomaly: How unusual is this amount for this account?
    - Type Anomaly: Is this transaction type common for this account?
    - Velocity: Are there rapid-fire transactions after dormancy?
    
    **Response Time:** Sub-second (designed for real-time authorization)
    """
    if scorer is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    assessment = scorer.calculate_risk(transaction)
    return assessment


@app.post("/api/v1/risk/assess/batch", response_model=BatchRiskAssessmentResponse, tags=["Risk Assessment"])
async def assess_batch_transactions(batch: BatchTransactionRequest):
    """
    Assess risk for multiple transactions in a single request.
    
    This endpoint accepts up to 1000 transactions and returns risk assessments
    for all of them, along with summary statistics.
    
    **Use Cases:**
    - Bulk transaction review
    - Batch processing of queued transactions
    - Historical transaction analysis
    - Periodic risk re-evaluation
    
    **Response includes:**
    - Individual risk assessments for each transaction
    - Summary with risk level counts and statistics
    - Count of accounts in REACTIVATING state (high-risk)
    """
    if scorer is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    results = []
    risk_scores = []
    risk_level_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    reactivating_count = 0
    
    for idx, transaction in enumerate(batch.transactions):
        assessment = scorer.calculate_risk(transaction)
        results.append(BatchRiskAssessmentResult(
            transaction_index=idx,
            assessment=assessment
        ))
        risk_scores.append(assessment.risk_score)
        risk_level_counts[assessment.risk_level] += 1
        if assessment.account_status == "reactivating":
            reactivating_count += 1
    
    summary = BatchSummary(
        low_risk_count=risk_level_counts["LOW"],
        medium_risk_count=risk_level_counts["MEDIUM"],
        high_risk_count=risk_level_counts["HIGH"],
        critical_risk_count=risk_level_counts["CRITICAL"],
        average_risk_score=round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0,
        max_risk_score=max(risk_scores) if risk_scores else 0,
        reactivating_accounts=reactivating_count
    )
    
    return BatchRiskAssessmentResponse(
        total_transactions=len(batch.transactions),
        processed=len(results),
        results=results,
        summary=summary
    )


@app.get("/api/v1/accounts/{account_id}/profile", response_model=AccountProfile, tags=["Accounts"])
async def get_account_profile(account_id: str):
    """
    Get the behavioral profile for a specific account.
    
    Returns the account's transaction history analysis and behavioral baseline,
    useful for understanding normal patterns before assessing risk.
    
    **Profile includes:**
    - **Activity Status:** `is_dormant`, `days_since_last_transaction`, `last_transaction_date`
    - **Amount Statistics:** `average_amount`, `median_amount`, `min_amount`, `max_amount`, `std_dev_amount`
    - **Transaction Patterns:** `typical_transaction_types`, `transaction_type_distribution`
    - **Location Data:** `common_locations` (top 5 most frequent)
    - **History:** `total_transactions`, `first_transaction_date`
    
    **Example Response:**
    ```json
    {
      "account_id": "ACC-12345678",
      "is_dormant": true,
      "days_since_last_transaction": 245,
      "last_transaction_date": "2025-06-17T14:30:00",
      "average_amount": 125.50,
      "typical_transaction_types": ["online_purchase", "atm_withdrawal"],
      ...
    }
    ```
    """
    profile = data_store.get_profile(account_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return profile


@app.get("/api/v1/accounts/dormant", response_model=list[AccountProfile], tags=["Accounts"])
async def list_dormant_accounts(
    min_days: int = Query(180, description="Minimum days dormant to include")
):
    """
    List all dormant accounts.
    
    Returns accounts with no activity for 180+ days (configurable via min_days).
    """
    if profiler is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    dormant = profiler.get_dormant_accounts()
    
    # Filter by minimum days if specified
    if min_days > 180:
        dormant = [
            p for p in dormant 
            if p.days_since_last_transaction and p.days_since_last_transaction >= min_days
        ]
    
    return dormant


@app.get("/api/v1/accounts/stats", tags=["Accounts"])
async def get_account_statistics():
    """Get aggregate statistics about accounts."""
    all_profiles = data_store.get_all_profiles()
    
    dormant_count = sum(1 for p in all_profiles.values() if p.is_dormant)
    active_count = len(all_profiles) - dormant_count
    
    dormant_profiles = [p for p in all_profiles.values() if p.is_dormant]
    avg_dormancy_days = (
        sum(p.days_since_last_transaction or 0 for p in dormant_profiles) / len(dormant_profiles)
        if dormant_profiles else 0
    )
    
    return {
        "total_accounts": len(all_profiles),
        "active_accounts": active_count,
        "dormant_accounts": dormant_count,
        "dormancy_rate": round(dormant_count / len(all_profiles) * 100, 2) if all_profiles else 0,
        "average_dormancy_days": round(avg_dormancy_days, 1),
        "total_transactions": data_store.total_transactions
    }


@app.post("/api/v1/accounts/{account_id}/refresh", response_model=AccountProfile, tags=["Accounts"])
async def refresh_account_profile(account_id: str):
    """
    Refresh an account's behavioral profile.
    
    Use this after ingesting new transactions to update the account's baseline.
    """
    if profiler is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    transactions = data_store.get_account_transactions(account_id)
    if not transactions:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    
    profile = profiler.refresh_profile(account_id)
    return profile


@app.post("/api/v1/transactions/ingest", tags=["Data Ingestion"])
async def ingest_transactions(transactions: list[Transaction]):
    """
    Ingest historical transactions for account profiling.
    
    Use this endpoint to load transaction history that will be used
    to build behavioral baselines for accounts.
    """
    data_store.add_transactions_bulk(transactions)
    
    # Refresh affected profiles
    if profiler:
        affected_accounts = set(t.account_id for t in transactions)
        for account_id in affected_accounts:
            profiler.refresh_profile(account_id)
    
    return {
        "message": f"Ingested {len(transactions)} transactions",
        "affected_accounts": len(set(t.account_id for t in transactions))
    }


@app.put("/api/v1/config/weights", tags=["Configuration"])
async def update_scoring_weights(
    dormancy: float = Query(0.30, ge=0, le=1),
    amount_anomaly: float = Query(0.25, ge=0, le=1),
    type_anomaly: float = Query(0.18, ge=0, le=1),
    velocity: float = Query(0.12, ge=0, le=1),
    location_anomaly: float = Query(0.15, ge=0, le=1)
):
    """
    Update the risk scoring weights.
    
    Weights must sum to 1.0. Default weights:
    - dormancy: 0.30
    - amount_anomaly: 0.25
    - type_anomaly: 0.18
    - velocity: 0.12
    - location_anomaly: 0.15
    """
    global scorer
    
    total = dormancy + amount_anomaly + type_anomaly + velocity + location_anomaly
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=400, 
            detail=f"Weights must sum to 1.0, got {total}"
        )
    
    new_weights = ScoringWeights(
        dormancy=dormancy,
        amount_anomaly=amount_anomaly,
        type_anomaly=type_anomaly,
        velocity=velocity,
        location_anomaly=location_anomaly
    )
    
    scorer = RiskScorer(data_store, weights=new_weights)
    
    return {"message": "Weights updated", "weights": new_weights.__dict__}


# For running directly with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
