# Fraud Detection Service

A real-time fraud detection API for identifying suspicious dormant account reactivation patterns.

## Overview

This service detects fraudulent activity on dormant accounts (inactive for 180+ days) by analyzing transaction patterns and calculating risk scores based on multiple factors:

- **Dormancy Factor**: How long has the account been inactive?
- **Amount Anomaly**: How unusual is the transaction amount compared to history?
- **Transaction Type Anomaly**: Is this transaction type rare for this account?
- **Velocity Spike**: Are there rapid-fire transactions after long dormancy?

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate Test Data

```bash
python data/generate_test_data.py
```

This generates:
- 55 unique accounts (36 active, 19 dormant)
- ~2,800+ historical transactions over 12 months
- 17 suspicious test transactions for validation

### 3. Run the Demo

```bash
python main.py
```

This demonstrates the risk scoring engine with various scenarios.

### 4. Start the API Server

```bash
python main.py --serve
# or: uvicorn app.api:app --reload
```

The API will be available at `http://localhost:8000`

Interactive documentation: `http://localhost:8000/docs`

## API Endpoints

### Risk Assessment

**POST** `/api/v1/risk/assess`

Assess the risk of a transaction in real-time.

**Request:**
```json
{
  "account_id": "ACC-12345678",
  "amount": 5000.00,
  "transaction_type": "wire_transfer",
  "timestamp": "2026-02-17T14:30:00",
  "location": "Singapore"
}
```

**Response:**
```json
{
  "account_id": "ACC-12345678",
  "risk_score": 78,
  "risk_level": "CRITICAL",
  "explanation": "CRITICAL risk (score: 78/100). Account dormant for 245 days; Amount $5000.00 is 12.5x the historical average; First-ever 'wire_transfer' transaction for this account",
  "factors": [
    {
      "factor_name": "dormancy",
      "score_contribution": 31.5,
      "description": "Account dormant for 245 days"
    },
    {
      "factor_name": "amount_anomaly",
      "score_contribution": 27.0,
      "description": "Amount $5000.00 is 12.5x the historical average (extreme anomaly)"
    },
    {
      "factor_name": "type_anomaly",
      "score_contribution": 14.0,
      "description": "First-ever 'wire_transfer' transaction for this account"
    },
    {
      "factor_name": "velocity",
      "score_contribution": 0.0,
      "description": "No rapid-fire transactions detected"
    }
  ],
  "is_dormant_account": true,
  "days_dormant": 245,
  "recommendation": "BLOCK - Manual review required before approval"
}
```

### Account Profile

**GET** `/api/v1/accounts/{account_id}/profile`

Get the behavioral profile for an account.

### List Dormant Accounts

**GET** `/api/v1/accounts/dormant?min_days=180`

List all accounts that have been inactive for 180+ days.

### Account Statistics

**GET** `/api/v1/accounts/stats`

Get aggregate statistics about accounts.

### Update Scoring Weights

**PUT** `/api/v1/config/weights?dormancy=0.35&amount_anomaly=0.30&type_anomaly=0.20&velocity=0.15`

Adjust the risk scoring weights (must sum to 1.0).

## Risk Scoring Algorithm

### Factor Weights (Default)

| Factor | Weight | Description |
|--------|--------|-------------|
| Dormancy | 35% | Risk based on days since last transaction |
| Amount Anomaly | 30% | Deviation from historical average amount |
| Type Anomaly | 20% | Unusualness of transaction type |
| Velocity | 15% | Rapid transactions after dormancy |

### Risk Levels

| Score Range | Level | Action |
|-------------|-------|--------|
| 0-25 | LOW | Allow transaction |
| 26-50 | MEDIUM | Flag for post-transaction review |
| 51-75 | HIGH | Require step-up authentication (SMS/email OTP) |
| 76-100 | CRITICAL | Block and require manual review |

### Scoring Details

#### Dormancy Score
- < 180 days: 0 points
- 180-270 days: 40-70 points (scales linearly)
- 270-365 days: 70-90 points
- 365+ days: 90-100 points

#### Amount Anomaly Score
- ≤ 1.5x average: 0 points
- 1.5-3x average: 30-60 points
- 3-5x average: 60-80 points
- 5-10x average: 80-90 points
- > 10x average: 90-100 points

#### Type Anomaly Score
- Common type (>20% of history): 0 points
- Uncommon type (5-20%): 25 points
- Rare type (<5%): 50 points
- First-ever type: 70 points
- High-risk types (wire/international) get 1.3-1.5x multiplier

#### Velocity Score
- No rapid transactions: 0 points
- 1-2 transactions in 60 minutes: 15-30 points
- 3+ transactions in 60 minutes: 45+ points

## Test Data

The test data generator (`data/generate_test_data.py`) creates realistic transaction patterns:

### Accounts
- **55 total accounts** with UUID-based IDs
- **36 active accounts** (regular transactions in last 180 days)
- **19 dormant accounts** (no activity for 180-400 days)

### Transactions
- **2,800+ historical transactions** spanning 12 months
- **Transaction types**: ATM withdrawal, online purchase, wire transfer, bill payment, peer-to-peer, POS purchase, international wire
- **Amounts**: Varied by account tier (low: $5-50, medium: $50-500, high: $500+)
- **Locations**: Southeast Asian cities (Singapore, Jakarta, Bangkok, etc.)

### Suspicious Test Cases
The generator creates 17 suspicious transactions designed to trigger high risk scores:

1. **Large amounts on dormant accounts** (8-15x historical average)
2. **First-ever international wires** to foreign locations
3. **Velocity spikes** (4 rapid transactions after dormancy)
4. **Geographic anomalies** (transactions in unusual locations)
5. **Sparse history accounts** (minimal transaction history)

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- Data store operations
- Account profiling (active/dormant detection)
- Risk scoring (all factors)
- Integration with generated test data

## Project Structure

```
fraud_detection/
├── main.py                  # Main entry point (demo + server)
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── api.py               # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── data_store.py        # In-memory data storage
│   ├── account_profiler.py  # Account behavior profiling
│   └── risk_scorer.py       # Risk scoring engine
├── data/
│   ├── generate_test_data.py    # Test data generator
│   └── test_transactions.json   # Generated test data
└── tests/
    ├── __init__.py
    └── test_risk_scoring.py     # Unit tests
```

## Example Usage with curl

```bash
# Health check
curl http://localhost:8000/health

# Assess a transaction
curl -X POST http://localhost:8000/api/v1/risk/assess \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-12345678",
    "amount": 5000,
    "transaction_type": "international_wire",
    "location": "London"
  }'

# Get account profile
curl http://localhost:8000/api/v1/accounts/ACC-12345678/profile

# List dormant accounts
curl http://localhost:8000/api/v1/accounts/dormant

# Get statistics
curl http://localhost:8000/api/v1/accounts/stats
```

## Performance

The service is designed for real-time authorization with sub-second response times:
- Risk assessment: < 10ms (in-memory)
- Account profile lookup: < 5ms
- No external dependencies for scoring

## Future Enhancements

Potential improvements for production deployment:
- Persistent database (PostgreSQL, Redis)
- ML-based scoring models
- Geographic distance calculation
- Device fingerprinting
- Historical fraud feedback loop
- Batch profile refresh jobs
- Distributed caching
