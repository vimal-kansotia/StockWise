# Production Deployment & Frontend Integration Guide

## 1. Staged Deployment Plan

### Stage 1: Core API & Database
- Deploy `inventory-api` container and `inventory-postgres` container to a container runner (e.g. AWS ECS, GCP Cloud Run with Cloud SQL, or a dedicated VM with Docker).
- Run migrations: `alembic upgrade head`.
- Ensure `POSTGRES_PASSWORD`, `API_KEY`, and `JWT_SECRET_KEY` are injected as cloud secrets.

### Stage 2: Connect Streamlit Frontend
The frontend connects cleanly over HTTP without duplicating any ML logic:
```python
import streamlit as st
import requests

API_URL = "http://localhost:8000"
headers = {"Authorization": f"Bearer {st.session_state.token}"}

# Fetch recommendations
recs = requests.get(f"{API_URL}/inventory/recommendations", headers=headers).json()
st.dataframe(recs)
```

### Stage 3: Distributed Spark Cluster & Airflow
- Deploy Spark standalone containers (`spark-master`, `spark-worker-1`, `spark-worker-2`) and Airflow (`airflow-webserver`, `airflow-scheduler`).
- Configure Spark executors to scale according to catalog size.
