"""Pydantic models for the fraud detection service."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """Types of transactions supported by CedarBank."""
    ATM_WITHDRAWAL = "atm_withdrawal"
    ONLINE_PURCHASE = "online_purchase"
    WIRE_TRANSFER = "wire_transfer"
    BILL_PAYMENT = "bill_payment"
    PEER_TO_PEER = "peer_to_peer"
    POS_PURCHASE = "pos_purchase"
    INTERNATIONAL_WIRE = "international_wire"


class Transaction(BaseModel):
    """Model representing a single transaction."""
    transaction_id: str
    account_id: str
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    transaction_type: TransactionType
    timestamp: datetime
    location: Optional[str] = Field(None, description="City or country code")
    merchant: Optional[str] = None


class TransactionRequest(BaseModel):
    """Request model for risk assessment API."""
    account_id: str
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    transaction_type: TransactionType
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)
    location: Optional[str] = None
    merchant: Optional[str] = None


class RiskFactor(BaseModel):
    """Individual risk factor contribution."""
    factor_name: str
    score_contribution: float
    description: str


class RiskAssessment(BaseModel):
    """Response model for risk assessment."""
    account_id: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    account_status: str  # ACTIVE, DORMANT, REACTIVATING, NEW
    explanation: str
    factors: list[RiskFactor]
    is_dormant_account: bool
    days_dormant: Optional[int] = None
    recommendation: str


class AccountProfile(BaseModel):
    """Profile representing an account's behavioral baseline."""
    account_id: str
    is_dormant: bool
    days_since_last_transaction: Optional[int] = None
    last_transaction_date: Optional[datetime] = None
    total_transactions: int
    average_amount: float
    median_amount: float
    max_amount: float
    min_amount: float
    std_dev_amount: float
    transaction_type_distribution: dict[str, int]
    common_locations: list[str]
    typical_transaction_types: list[str]
    first_transaction_date: Optional[datetime] = None


class AccountStatus(str, Enum):
    """Account activity status."""
    ACTIVE = "active"
    DORMANT = "dormant"
    REACTIVATING = "reactivating"  # Dormant account with recent transaction (high-risk)
    NEW = "new"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    accounts_loaded: int
    transactions_loaded: int
