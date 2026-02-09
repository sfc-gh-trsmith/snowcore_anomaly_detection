# Snowcore Reliability Copilot - React App

A React + FastAPI application for predictive maintenance powered by Snowflake Cortex.

## Features

- **Asset Dashboard** - KPIs, risk tiles, and maintenance priority queue
- **Analytics** - Efficient frontier, cost comparison charts
- **GNN Visualization** - Interactive anomaly propagation network graph
- **Cortex Copilot** - Chat interface for natural language queries

## Setup

### Frontend

```bash
cd react/frontend
npm install
npm run dev
```

### Backend

```bash
cd react/backend
pip install -r requirements.txt
SNOWFLAKE_CONNECTION_NAME=demo uvicorn api.main:app --reload --port 8000
```

## Architecture

```
react/
├── frontend/              # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Full-page views
│   │   ├── hooks/         # Custom React hooks
│   │   └── styles/        # Global CSS + Tailwind
│   └── package.json
│
├── backend/               # Python FastAPI
│   ├── api/main.py        # REST endpoints
│   └── services/          # Snowflake data access
│
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/decisions` | GET | Maintenance decisions from dynamic table |
| `/api/anomalies` | GET | Recent anomaly events |
| `/api/failure-probability` | GET | Asset failure probabilities |
| `/api/chat` | POST | Chat with Cortex Copilot |

## Data Sources

- `SNOWCORE_PDM.PDM.MAINTENANCE_DECISIONS_LIVE` - Dynamic table with cost-based recommendations
- `SNOWCORE_PDM.PDM.FAILURE_PROBABILITY` - Asset failure probabilities
- `SNOWCORE_PDM.PDM.ANOMALY_EVENTS` - Real-time anomaly detection
