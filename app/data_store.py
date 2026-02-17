"""In-memory data store for accounts and transactions."""

from datetime import datetime
from typing import Optional
from .models import Transaction, AccountProfile


class DataStore:
    """In-memory storage for transaction history and account profiles."""
    
    def __init__(self):
        self._transactions: dict[str, list[Transaction]] = {}  # account_id -> transactions
        self._profiles: dict[str, AccountProfile] = {}  # account_id -> profile
        self._all_transactions: list[Transaction] = []
    
    def add_transaction(self, transaction: Transaction) -> None:
        """Add a transaction to the store."""
        if transaction.account_id not in self._transactions:
            self._transactions[transaction.account_id] = []
        self._transactions[transaction.account_id].append(transaction)
        self._all_transactions.append(transaction)
    
    def add_transactions_bulk(self, transactions: list[Transaction]) -> None:
        """Add multiple transactions at once."""
        for txn in transactions:
            self.add_transaction(txn)
    
    def get_account_transactions(self, account_id: str) -> list[Transaction]:
        """Get all transactions for an account, sorted by timestamp."""
        transactions = self._transactions.get(account_id, [])
        return sorted(transactions, key=lambda t: t.timestamp)
    
    def get_all_account_ids(self) -> list[str]:
        """Get all unique account IDs."""
        return list(self._transactions.keys())
    
    def set_profile(self, account_id: str, profile: AccountProfile) -> None:
        """Store an account profile."""
        self._profiles[account_id] = profile
    
    def get_profile(self, account_id: str) -> Optional[AccountProfile]:
        """Get an account profile."""
        return self._profiles.get(account_id)
    
    def get_all_profiles(self) -> dict[str, AccountProfile]:
        """Get all account profiles."""
        return self._profiles.copy()
    
    def get_recent_transactions(
        self, 
        account_id: str, 
        since: datetime,
        before: Optional[datetime] = None
    ) -> list[Transaction]:
        """Get transactions for an account within a time window."""
        transactions = self.get_account_transactions(account_id)
        filtered = [t for t in transactions if t.timestamp >= since]
        if before:
            filtered = [t for t in filtered if t.timestamp < before]
        return filtered
    
    def clear(self) -> None:
        """Clear all data."""
        self._transactions.clear()
        self._profiles.clear()
        self._all_transactions.clear()
    
    @property
    def total_accounts(self) -> int:
        """Total number of accounts."""
        return len(self._transactions)
    
    @property
    def total_transactions(self) -> int:
        """Total number of transactions."""
        return len(self._all_transactions)


# Global data store instance
data_store = DataStore()
