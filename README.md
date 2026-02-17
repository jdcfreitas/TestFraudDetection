# Fraud Detection Service

A real-time fraud detection API for identifying suspicious dormant account reactivation patterns.

## Overview

This service detects fraudulent activity on dormant accounts (inactive for 180+ days) by analyzing transaction patterns and calculating risk scores based on multiple factors:

- **Dormancy Factor**: How long has the account been inactive?
- **Amount Anomaly**: How unusual is the transaction amount compared to history?
- **Transaction Type Anomaly**: Is this transaction type rare for this account?
- **Velocity Spike**: Are there rapid-fire transactions after long dormancy?
- **Location Anomaly**: Is the transaction from an unusual geographic location?

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

Assess the risk of a single transaction in real-time.

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
  "account_status": "reactivating",
  "explanation": "CRITICAL risk (score: 78/100). Account dormant for 245 days; Amount $5000.00 is 12.5x the historical average",
  "factors": [
    {
      "factor_name": "dormancy",
      "score_contribution": 24.0,
      "description": "Account dormant for 245 days"
    },
    {
      "factor_name": "amount_anomaly",
      "score_contribution": 22.5,
      "description": "Amount $5000.00 is 12.5x the historical average (extreme anomaly)"
    },
    {
      "factor_name": "type_anomaly",
      "score_contribution": 12.6,
      "description": "First-ever 'wire_transfer' transaction for this account"
    },
    {
      "factor_name": "velocity",
      "score_contribution": 0.0,
      "description": "No rapid-fire transactions detected"
    },
    {
      "factor_name": "location_anomaly",
      "score_contribution": 9.75,
      "description": "International location 'London' on dormant account that typically transacts domestically"
    }
  ],
  "is_dormant_account": true,
  "days_dormant": 245,
  "recommendation": "BLOCK - Manual review required before approval"
}
```

### Batch Risk Assessment

**POST** `/api/v1/risk/assess/batch`

Assess risk for multiple transactions in a single request (up to 1000).

**Request:**
```json
{
  "transactions": [
    {"account_id": "ACC-001", "amount": 500, "transaction_type": "wire_transfer", "location": "Singapore"},
    {"account_id": "ACC-002", "amount": 100, "transaction_type": "atm_withdrawal", "location": "Jakarta"},
    {"account_id": "ACC-003", "amount": 2500, "transaction_type": "international_wire", "location": "London"}
  ]
}
```

**Response:**
```json
{
  "total_transactions": 3,
  "processed": 3,
  "results": [
    {"transaction_index": 0, "assessment": {...}},
    {"transaction_index": 1, "assessment": {...}},
    {"transaction_index": 2, "assessment": {...}}
  ],
  "summary": {
    "low_risk_count": 1,
    "medium_risk_count": 1,
    "high_risk_count": 0,
    "critical_risk_count": 1,
    "average_risk_score": 52.3,
    "max_risk_score": 85,
    "reactivating_accounts": 1
  }
}
```

### Account Profile

**GET** `/api/v1/accounts/{account_id}/profile`

Get the behavioral profile for a specific account.

**Response:**
```json
{
  "account_id": "ACC-12345678",
  "is_dormant": true,
  "days_since_last_transaction": 245,
  "last_transaction_date": "2025-06-17T14:30:00",
  "total_transactions": 47,
  "average_amount": 125.50,
  "median_amount": 85.00,
  "max_amount": 500.00,
  "min_amount": 15.00,
  "std_dev_amount": 95.20,
  "transaction_type_distribution": {
    "online_purchase": 25,
    "atm_withdrawal": 15,
    "bill_payment": 7
  },
  "common_locations": ["Singapore", "Jakarta", "Bangkok"],
  "typical_transaction_types": ["online_purchase", "atm_withdrawal"],
  "first_transaction_date": "2024-01-15T10:00:00"
}
```

### List Dormant Accounts

**GET** `/api/v1/accounts/dormant?min_days=180`

List all accounts that have been inactive for the specified number of days.

### Health Check

**GET** `/health`

Check service health and data status.

## Account Status

The API tracks account status to identify high-risk reactivation attempts:

| Status | Description |
|--------|-------------|
| `active` | Account has recent transaction activity |
| `dormant` | No transactions for 180+ days |
| `reactivating` | **High-risk** - Dormant account attempting a transaction |
| `new` | Unknown account with no transaction history |

## Risk Scoring Algorithm

### Factor Weights (Default)

| Factor | Weight | Description |
|--------|--------|-------------|
| Dormancy | 30% | Risk based on days since last transaction |
| Amount Anomaly | 25% | Deviation from historical average amount |
| Type Anomaly | 18% | Unusualness of transaction type |
| Location Anomaly | 15% | Geographic anomaly detection |
| Velocity | 12% | Rapid transactions after dormancy |

### Risk Levels

| Score Range | Level | Action |
|-------------|-------|--------|
| 0-25 | LOW | Allow transaction |
| 26-50 | MEDIUM | Flag for post-transaction review |
| 51-75 | HIGH | Require step-up authentication (SMS/email OTP) |
| 76-100 | CRITICAL | Block and require manual review |

### Location Anomaly Scoring

The service detects geographic anomalies based on account history:

**Domestic Locations (Southeast Asia):**
Singapore, Jakarta, Bangkok, Kuala Lumpur, Manila, Ho Chi Minh City, Hanoi, Bali, Phuket, Penang, Cebu, Chiang Mai, Yangon, Phnom Penh, Brunei

**International Locations (Higher Risk):**
London, New York, Dubai, Tokyo, Sydney, Moscow, Lagos, Sao Paulo, Paris, Berlin, Toronto, Mumbai, Beijing, Shanghai, Seoul

| Scenario | Score |
|----------|-------|
| Transaction from common location | 0 points |
| New domestic location | 15-35 points |
| International location (active account) | 40-65 points |
| International location (dormant account) | 90 points |

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

## Configuration

All thresholds and weights are configurable via YAML:

**Config file:** `config/default_config.yaml`

```yaml
# Dormancy threshold
dormancy:
  threshold_days: 180

# Velocity detection
velocity:
  window_minutes: 60
  threshold_count: 3

# Risk scoring weights (must sum to 1.0)
risk_weights:
  dormancy: 0.30
  amount_anomaly: 0.25
  type_anomaly: 0.18
  velocity: 0.12
  location_anomaly: 0.15

# Risk level thresholds
risk_levels:
  low_max: 25
  medium_max: 50
  high_max: 75

# Location classifications
locations:
  domestic:
    - Singapore
    - Jakarta
    # ... more Southeast Asian cities
  international:
    - London
    - New York
    # ... more international cities
```

**Custom config:** Create `config/config.yaml` or set `FRAUD_DETECTION_CONFIG` environment variable.

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
4. **Geographic anomalies** (transactions from international locations)
5. **Sparse history accounts** (minimal transaction history)

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- Data store operations
- Account profiling (active/dormant/borderline detection)
- Risk scoring (all 5 factors)
- Location anomaly detection
- Edge cases (sparse accounts, recently dormant, borderline thresholds)
- Configuration loading and customization
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
│   ├── risk_scorer.py       # Risk scoring engine (5 factors)
│   └── config.py            # Configuration management
├── config/
│   └── default_config.yaml  # Default configuration
├── data/
│   ├── generate_test_data.py    # Test data generator
│   └── test_transactions.json   # Generated test data
└── tests/
    ├── __init__.py
    └── test_risk_scoring.py     # Unit tests (30+ tests)
```

## Example Usage with curl

```bash
# Health check
curl http://localhost:8000/health

# Assess a single transaction
curl -X POST http://localhost:8000/api/v1/risk/assess \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-12345678",
    "amount": 5000,
    "transaction_type": "international_wire",
    "location": "London"
  }'

# Batch assess multiple transactions
curl -X POST http://localhost:8000/api/v1/risk/assess/batch \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {"account_id": "ACC-001", "amount": 100, "transaction_type": "atm_withdrawal", "location": "Singapore"},
      {"account_id": "ACC-002", "amount": 5000, "transaction_type": "wire_transfer", "location": "Dubai"}
    ]
  }'

# Get account profile
curl http://localhost:8000/api/v1/accounts/ACC-12345678/profile

# List dormant accounts
curl http://localhost:8000/api/v1/accounts/dormant
```

## Performance

The service is designed for real-time authorization with sub-second response times:
- Single risk assessment: < 10ms (in-memory)
- Batch assessment (100 transactions): < 100ms
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
- Real-time streaming with Kafka
