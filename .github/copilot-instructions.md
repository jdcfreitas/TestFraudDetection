# Fraud Detection Service

Real-time fraud detection API for identifying suspicious dormant account reactivation patterns.

## Project Structure
- `main.py` - Main entry point (demo + API server)
- `app/api.py` - FastAPI application with REST endpoints
- `app/models.py` - Pydantic models (Transaction, RiskAssessment, etc.)
- `app/data_store.py` - In-memory data storage
- `app/account_profiler.py` - Account behavioral profiling
- `app/risk_scorer.py` - Risk scoring engine with 4 factors
- `data/` - Test data generator and generated transactions
- `tests/` - Unit tests

## Running the Project
```bash
# Run the demo
python main.py

# Start the API server
python main.py --serve
# or: uvicorn app.api:app --reload
```

## Key Features
- Dormant account detection (180+ days inactive)
- Risk scoring (0-100) based on: dormancy, amount anomaly, type anomaly, velocity
- Real-time REST API at /api/v1/risk/assess
