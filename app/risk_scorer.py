"""Risk scoring engine for transaction fraud detection."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .models import (
    AccountProfile, 
    AccountStatus,
    Transaction, 
    TransactionRequest,
    RiskAssessment, 
    RiskFactor,
    TransactionType
)
from .data_store import DataStore


@dataclass
class ScoringWeights:
    """Configurable weights for risk factors."""
    dormancy: float = 0.35       # Weight for dormancy factor
    amount_anomaly: float = 0.30  # Weight for amount deviation
    type_anomaly: float = 0.20    # Weight for transaction type anomaly
    velocity: float = 0.15        # Weight for velocity spike
    
    def __post_init__(self):
        total = self.dormancy + self.amount_anomaly + self.type_anomaly + self.velocity
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class RiskScorer:
    """
    Calculates risk scores for transactions based on account behavior.
    
    Risk Score Components:
    1. Dormancy Factor (35%): Higher score for longer dormancy periods
    2. Amount Anomaly (30%): Higher score for amounts deviating from historical average
    3. Transaction Type Anomaly (20%): Higher score for unusual transaction types
    4. Velocity Spike (15%): Higher score for rapid transactions after dormancy
    
    Final score is 0-100, where:
    - 0-25: LOW risk
    - 26-50: MEDIUM risk
    - 51-75: HIGH risk
    - 76-100: CRITICAL risk
    """
    
    DORMANCY_THRESHOLD_DAYS = 180
    VELOCITY_WINDOW_MINUTES = 60  # Check for rapid transactions within this window
    VELOCITY_THRESHOLD = 3  # Number of transactions in window that triggers concern
    
    def __init__(
        self, 
        data_store: DataStore, 
        weights: Optional[ScoringWeights] = None,
        reference_date: Optional[datetime] = None
    ):
        """
        Initialize the risk scorer.
        
        Args:
            data_store: The data store with transaction history and profiles
            weights: Custom scoring weights (uses defaults if not provided)
            reference_date: The date to use as "now" for calculations
        """
        self.data_store = data_store
        self.weights = weights or ScoringWeights()
        self.reference_date = reference_date or datetime.now()
    
    def calculate_risk(self, transaction: TransactionRequest) -> RiskAssessment:
        """
        Calculate the risk score for a transaction.
        
        Args:
            transaction: The transaction to assess
            
        Returns:
            RiskAssessment with score, explanation, and factor breakdown
        """
        profile = self.data_store.get_profile(transaction.account_id)
        
        if profile is None:
            # Unknown account - high risk by default
            return RiskAssessment(
                account_id=transaction.account_id,
                risk_score=85,
                risk_level="CRITICAL",
                account_status=AccountStatus.NEW.value,
                explanation="Unknown account with no transaction history",
                factors=[
                    RiskFactor(
                        factor_name="unknown_account",
                        score_contribution=85.0,
                        description="No historical data available for this account"
                    )
                ],
                is_dormant_account=True,
                days_dormant=None,
                recommendation="BLOCK - Manual review required for unknown account"
            )
        
        # Calculate individual risk factors
        factors = []
        
        # 1. Dormancy Factor
        dormancy_score, dormancy_factor = self._calculate_dormancy_score(profile)
        factors.append(dormancy_factor)
        
        # 2. Amount Anomaly Factor
        amount_score, amount_factor = self._calculate_amount_anomaly(
            transaction.amount, profile
        )
        factors.append(amount_factor)
        
        # 3. Transaction Type Anomaly Factor
        type_score, type_factor = self._calculate_type_anomaly(
            transaction.transaction_type, profile
        )
        factors.append(type_factor)
        
        # 4. Velocity Spike Factor
        velocity_score, velocity_factor = self._calculate_velocity_spike(
            transaction, profile
        )
        factors.append(velocity_factor)
        
        # Calculate weighted final score
        final_score = (
            dormancy_score * self.weights.dormancy +
            amount_score * self.weights.amount_anomaly +
            type_score * self.weights.type_anomaly +
            velocity_score * self.weights.velocity
        )
        final_score = min(100, max(0, round(final_score)))
        
        # Determine risk level
        risk_level = self._get_risk_level(final_score)
        
        # Generate explanation
        explanation = self._generate_explanation(
            profile, transaction, factors, final_score
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(final_score, risk_level)
        
        # Determine account status
        account_status = self._determine_account_status(profile)
        
        return RiskAssessment(
            account_id=transaction.account_id,
            risk_score=final_score,
            risk_level=risk_level,
            account_status=account_status,
            explanation=explanation,
            factors=factors,
            is_dormant_account=profile.is_dormant,
            days_dormant=profile.days_since_last_transaction if profile.is_dormant else None,
            recommendation=recommendation
        )
    
    def _determine_account_status(self, profile: AccountProfile) -> str:
        """
        Determine the account status based on its profile.
        
        Returns:
            Account status: ACTIVE, DORMANT, REACTIVATING, or NEW
        """
        if profile.total_transactions == 0:
            return AccountStatus.NEW.value
        
        if profile.is_dormant:
            # Account is dormant - the current transaction is a reactivation attempt
            return AccountStatus.REACTIVATING.value
        
        return AccountStatus.ACTIVE.value
    
    def _calculate_dormancy_score(
        self, profile: AccountProfile
    ) -> tuple[float, RiskFactor]:
        """Calculate dormancy risk score (0-100)."""
        if not profile.is_dormant:
            return 0.0, RiskFactor(
                factor_name="dormancy",
                score_contribution=0.0,
                description="Account is active (not dormant)"
            )
        
        days_dormant = profile.days_since_last_transaction or 0
        
        # Scoring curve: starts at threshold, maxes out at 2 years
        if days_dormant < self.DORMANCY_THRESHOLD_DAYS:
            score = 0.0
        elif days_dormant < 270:  # 180-270 days: moderate risk
            score = 40.0 + (days_dormant - 180) * 0.33
        elif days_dormant < 365:  # 270-365 days: high risk
            score = 70.0 + (days_dormant - 270) * 0.21
        else:  # 365+ days: very high risk
            score = min(100.0, 90.0 + (days_dormant - 365) * 0.027)
        
        return score, RiskFactor(
            factor_name="dormancy",
            score_contribution=round(score * self.weights.dormancy, 2),
            description=f"Account dormant for {days_dormant} days"
        )
    
    def _calculate_amount_anomaly(
        self, amount: float, profile: AccountProfile
    ) -> tuple[float, RiskFactor]:
        """Calculate amount anomaly score (0-100)."""
        if profile.total_transactions == 0 or profile.average_amount == 0:
            # No baseline - treat large amounts as suspicious
            if amount > 1000:
                score = 70.0
                desc = f"Large amount ${amount:.2f} with no transaction history"
            else:
                score = 30.0
                desc = f"Amount ${amount:.2f} with no baseline for comparison"
            return score, RiskFactor(
                factor_name="amount_anomaly",
                score_contribution=round(score * self.weights.amount_anomaly, 2),
                description=desc
            )
        
        # Calculate deviation from average
        deviation_ratio = amount / profile.average_amount
        
        # Also consider standard deviation if available
        if profile.std_dev_amount > 0:
            z_score = abs(amount - profile.average_amount) / profile.std_dev_amount
        else:
            z_score = deviation_ratio - 1
        
        # Scoring based on deviation
        if deviation_ratio <= 1.5:
            score = 0.0
            desc = f"Amount ${amount:.2f} is within normal range (avg: ${profile.average_amount:.2f})"
        elif deviation_ratio <= 3.0:
            score = 30.0 + (deviation_ratio - 1.5) * 20
            desc = f"Amount ${amount:.2f} is {deviation_ratio:.1f}x the historical average"
        elif deviation_ratio <= 5.0:
            score = 60.0 + (deviation_ratio - 3.0) * 10
            desc = f"Amount ${amount:.2f} is {deviation_ratio:.1f}x the historical average (unusual)"
        elif deviation_ratio <= 10.0:
            score = 80.0 + (deviation_ratio - 5.0) * 2
            desc = f"Amount ${amount:.2f} is {deviation_ratio:.1f}x the historical average (highly anomalous)"
        else:
            score = min(100.0, 90.0 + (deviation_ratio - 10.0))
            desc = f"Amount ${amount:.2f} is {deviation_ratio:.1f}x the historical average (extreme anomaly)"
        
        return score, RiskFactor(
            factor_name="amount_anomaly",
            score_contribution=round(score * self.weights.amount_anomaly, 2),
            description=desc
        )
    
    def _calculate_type_anomaly(
        self, txn_type: TransactionType, profile: AccountProfile
    ) -> tuple[float, RiskFactor]:
        """Calculate transaction type anomaly score (0-100)."""
        type_value = txn_type.value
        type_dist = profile.transaction_type_distribution
        
        if profile.total_transactions == 0:
            # No history - moderate concern for high-risk types
            high_risk_types = {
                TransactionType.WIRE_TRANSFER.value,
                TransactionType.INTERNATIONAL_WIRE.value
            }
            if type_value in high_risk_types:
                score = 60.0
                desc = f"High-risk transaction type '{type_value}' with no account history"
            else:
                score = 20.0
                desc = f"Transaction type '{type_value}' with no baseline"
            return score, RiskFactor(
                factor_name="type_anomaly",
                score_contribution=round(score * self.weights.type_anomaly, 2),
                description=desc
            )
        
        # Check if this type was ever used
        type_count = type_dist.get(type_value, 0)
        type_percentage = (type_count / profile.total_transactions) * 100 if profile.total_transactions > 0 else 0
        
        # High-risk transaction types get extra scrutiny
        high_risk_types = {
            TransactionType.WIRE_TRANSFER.value: 1.3,
            TransactionType.INTERNATIONAL_WIRE.value: 1.5
        }
        risk_multiplier = high_risk_types.get(type_value, 1.0)
        
        if type_count == 0:
            # First time using this transaction type
            score = min(100, 70.0 * risk_multiplier)
            desc = f"First-ever '{type_value}' transaction for this account"
        elif type_percentage < 5:
            # Very rare type for this account
            score = min(100, 50.0 * risk_multiplier)
            desc = f"Rare transaction type '{type_value}' ({type_percentage:.1f}% of history)"
        elif type_percentage < 20:
            # Uncommon type
            score = 25.0 * risk_multiplier
            desc = f"Uncommon transaction type '{type_value}' ({type_percentage:.1f}% of history)"
        else:
            # Common type for this account
            score = 0.0
            desc = f"Common transaction type '{type_value}' ({type_percentage:.1f}% of history)"
        
        return score, RiskFactor(
            factor_name="type_anomaly",
            score_contribution=round(score * self.weights.type_anomaly, 2),
            description=desc
        )
    
    def _calculate_velocity_spike(
        self, transaction: TransactionRequest, profile: AccountProfile
    ) -> tuple[float, RiskFactor]:
        """Calculate velocity spike score (0-100)."""
        if not profile.is_dormant:
            # Velocity is less concerning for active accounts
            return 0.0, RiskFactor(
                factor_name="velocity",
                score_contribution=0.0,
                description="Velocity check skipped for active account"
            )
        
        # Check for recent transactions in the velocity window
        txn_time = transaction.timestamp or self.reference_date
        window_start = txn_time - timedelta(minutes=self.VELOCITY_WINDOW_MINUTES)
        
        recent_txns = self.data_store.get_recent_transactions(
            transaction.account_id,
            since=window_start,
            before=txn_time
        )
        
        txn_count = len(recent_txns)
        
        if txn_count == 0:
            score = 0.0
            desc = "No rapid-fire transactions detected"
        elif txn_count < self.VELOCITY_THRESHOLD:
            score = txn_count * 15.0
            desc = f"{txn_count} transactions in last {self.VELOCITY_WINDOW_MINUTES} minutes after dormancy"
        else:
            score = min(100.0, 45.0 + (txn_count - self.VELOCITY_THRESHOLD) * 15)
            desc = f"Velocity spike: {txn_count} transactions in {self.VELOCITY_WINDOW_MINUTES} minutes after long dormancy"
        
        return score, RiskFactor(
            factor_name="velocity",
            score_contribution=round(score * self.weights.velocity, 2),
            description=desc
        )
    
    def _get_risk_level(self, score: int) -> str:
        """Convert numeric score to risk level."""
        if score <= 25:
            return "LOW"
        elif score <= 50:
            return "MEDIUM"
        elif score <= 75:
            return "HIGH"
        else:
            return "CRITICAL"
    
    def _generate_explanation(
        self, 
        profile: AccountProfile,
        transaction: TransactionRequest,
        factors: list[RiskFactor],
        final_score: int
    ) -> str:
        """Generate human-readable explanation of the risk score."""
        risk_level = self._get_risk_level(final_score)
        
        parts = [f"{risk_level} risk (score: {final_score}/100)"]
        
        # Add most significant factors
        significant_factors = [f for f in factors if f.score_contribution > 5]
        significant_factors.sort(key=lambda f: f.score_contribution, reverse=True)
        
        if significant_factors:
            factor_descs = [f.description for f in significant_factors[:3]]
            parts.append("; ".join(factor_descs))
        
        return ". ".join(parts)
    
    def _generate_recommendation(self, score: int, risk_level: str) -> str:
        """Generate action recommendation based on risk score."""
        if risk_level == "LOW":
            return "ALLOW - Transaction appears normal"
        elif risk_level == "MEDIUM":
            return "ALLOW WITH MONITORING - Flag for post-transaction review"
        elif risk_level == "HIGH":
            return "STEP-UP AUTH - Require additional verification (SMS/email OTP)"
        else:  # CRITICAL
            return "BLOCK - Manual review required before approval"
