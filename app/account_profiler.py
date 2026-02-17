"""Account profiler for building behavioral baselines."""

import statistics
from datetime import datetime, timedelta
from typing import Optional
from collections import Counter

from .models import Transaction, AccountProfile, TransactionType
from .data_store import DataStore


class AccountProfiler:
    """
    Builds behavioral profiles for accounts based on transaction history.
    
    A profile includes:
    - Dormancy status (no transactions in last 180 days)
    - Average/median/std dev of transaction amounts
    - Distribution of transaction types
    - Common locations
    - Last transaction date
    """
    
    DORMANCY_THRESHOLD_DAYS = 180  # CedarBank's dormancy threshold
    
    def __init__(self, data_store: DataStore, reference_date: Optional[datetime] = None):
        """
        Initialize the profiler.
        
        Args:
            data_store: The data store containing transaction history
            reference_date: The date to use as "now" for dormancy calculations.
                          If None, uses current datetime.
        """
        self.data_store = data_store
        self.reference_date = reference_date or datetime.now()
    
    def build_profile(self, account_id: str) -> AccountProfile:
        """
        Build a behavioral profile for a single account.
        
        Args:
            account_id: The account to profile
            
        Returns:
            AccountProfile with behavioral baseline data
        """
        transactions = self.data_store.get_account_transactions(account_id)
        
        if not transactions:
            # No transaction history - new or empty account
            return AccountProfile(
                account_id=account_id,
                is_dormant=True,
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
        
        # Sort by timestamp
        transactions = sorted(transactions, key=lambda t: t.timestamp)
        
        # Calculate amount statistics
        amounts = [t.amount for t in transactions]
        avg_amount = statistics.mean(amounts)
        median_amount = statistics.median(amounts)
        max_amount = max(amounts)
        min_amount = min(amounts)
        std_dev_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
        
        # Transaction type distribution
        type_counts = Counter(t.transaction_type.value for t in transactions)
        type_distribution = dict(type_counts)
        
        # Most common transaction types (those making up >10% of transactions)
        total_txns = len(transactions)
        typical_types = [
            t_type for t_type, count in type_counts.items() 
            if count / total_txns >= 0.1
        ]
        
        # Common locations
        locations = [t.location for t in transactions if t.location]
        location_counts = Counter(locations)
        common_locations = [loc for loc, _ in location_counts.most_common(5)]
        
        # Dormancy calculation
        last_transaction = transactions[-1]
        last_txn_date = last_transaction.timestamp
        days_since_last = (self.reference_date - last_txn_date).days
        is_dormant = days_since_last >= self.DORMANCY_THRESHOLD_DAYS
        
        return AccountProfile(
            account_id=account_id,
            is_dormant=is_dormant,
            days_since_last_transaction=days_since_last,
            last_transaction_date=last_txn_date,
            total_transactions=total_txns,
            average_amount=round(avg_amount, 2),
            median_amount=round(median_amount, 2),
            max_amount=round(max_amount, 2),
            min_amount=round(min_amount, 2),
            std_dev_amount=round(std_dev_amount, 2),
            transaction_type_distribution=type_distribution,
            common_locations=common_locations,
            typical_transaction_types=typical_types,
            first_transaction_date=transactions[0].timestamp
        )
    
    def build_all_profiles(self) -> dict[str, AccountProfile]:
        """
        Build profiles for all accounts in the data store.
        
        Returns:
            Dictionary mapping account_id to AccountProfile
        """
        profiles = {}
        for account_id in self.data_store.get_all_account_ids():
            profile = self.build_profile(account_id)
            profiles[account_id] = profile
            self.data_store.set_profile(account_id, profile)
        return profiles
    
    def get_dormant_accounts(self) -> list[AccountProfile]:
        """Get all dormant account profiles."""
        all_profiles = self.data_store.get_all_profiles()
        return [p for p in all_profiles.values() if p.is_dormant]
    
    def get_active_accounts(self) -> list[AccountProfile]:
        """Get all active account profiles."""
        all_profiles = self.data_store.get_all_profiles()
        return [p for p in all_profiles.values() if not p.is_dormant]
    
    def refresh_profile(self, account_id: str) -> AccountProfile:
        """
        Refresh an account's profile with latest transaction data.
        
        Args:
            account_id: The account to refresh
            
        Returns:
            Updated AccountProfile
        """
        profile = self.build_profile(account_id)
        self.data_store.set_profile(account_id, profile)
        return profile
