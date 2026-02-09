from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os

from services.snowflake_service import get_snowflake_service, close_snowflake_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_snowflake_service()
    logger.info("Snowflake connection initialized")
    yield
    close_snowflake_service()
    logger.info("Snowflake connection closed")


app = FastAPI(title="Snowcore Copilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ToggleSimulationRequest(BaseModel):
    enable: bool


class InjectAnomalyRequest(BaseModel):
    asset_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []
    context: Optional[Dict[str, Any]] = None


class DecisionsResponse(BaseModel):
    decisions: List[Dict[str, Any]]


@app.get("/")
async def health():
    return {"status": "healthy", "service": "snowcore-copilot"}


@app.get("/api/decisions", response_model=DecisionsResponse)
async def get_decisions():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT 
                ASSET_ID,
                P_FAIL_7D,
                EXPECTED_UNPLANNED_COST,
                C_PM_USD,
                NET_BENEFIT,
                RECOMMENDATION,
                TARGET_WINDOW,
                CONFIDENCE
            FROM SNOWCORE_PDM.PDM.MAINTENANCE_DECISIONS_LIVE
            ORDER BY NET_BENEFIT DESC
            """,
            timeout=30,
        )
        return {"decisions": data}
    except Exception as e:
        logger.error(f"Failed to fetch decisions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch maintenance decisions")


@app.get("/api/anomalies")
async def get_anomalies():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT * FROM SNOWCORE_PDM.PDM.ANOMALY_EVENTS
            WHERE EVENT_TIME > DATEADD(hour, -24, CURRENT_TIMESTAMP())
            ORDER BY EVENT_TIME DESC
            LIMIT 20
            """,
            timeout=30,
        )
        return {"anomalies": data}
    except Exception as e:
        logger.error(f"Failed to fetch anomalies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch anomalies")


@app.get("/api/failure-probability")
async def get_failure_probability():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT * FROM SNOWCORE_PDM.PDM.FAILURE_PROBABILITY
            ORDER BY ASSET_ID
            """,
            timeout=30,
        )
        return {"probabilities": data}
    except Exception as e:
        logger.error(f"Failed to fetch failure probabilities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch failure probabilities")


@app.get("/api/anomaly-events")
async def get_anomaly_events():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT 
                EVENT_ID,
                ASSET_ID,
                TIMESTAMP,
                ANOMALY_TYPE,
                ANOMALY_SCORE,
                SEVERITY,
                ROOT_CAUSE,
                SUGGESTED_FIX,
                RESOLVED
            FROM SNOWCORE_PDM.PDM.ANOMALY_EVENTS
            ORDER BY TIMESTAMP DESC
            LIMIT 50
            """,
            timeout=30,
        )
        return {"events": data}
    except Exception as e:
        logger.error(f"Failed to fetch anomaly events: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch anomaly events")


@app.get("/api/live-sensors")
async def get_live_sensors():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            WITH parsed AS (
                SELECT 
                    TO_TIMESTAMP(RECORD_CONTENT:timestamp::NUMBER / 1000) AS EVENT_TIME,
                    m.value:name::STRING AS METRIC_NAME,
                    m.value:value::FLOAT AS METRIC_VALUE,
                    INGESTION_TIME
                FROM SNOWCORE_PDM.RAW.IOT_STREAMING_LIVE,
                LATERAL FLATTEN(input => RECORD_CONTENT:metrics) m
                WHERE INGESTION_TIME > DATEADD('second', -30, CURRENT_TIMESTAMP())
            )
            SELECT 
                EVENT_TIME,
                MAX(CASE WHEN METRIC_NAME = 'Temperature' THEN METRIC_VALUE END) AS TEMPERATURE_C,
                MAX(CASE WHEN METRIC_NAME = 'Humidity' THEN METRIC_VALUE END) AS HUMIDITY_PCT,
                MAX(CASE WHEN METRIC_NAME = 'Pressure' THEN METRIC_VALUE END) AS PRESSURE_PSI,
                MAX(CASE WHEN METRIC_NAME = 'Vibration' THEN METRIC_VALUE END) AS VIBRATION_G,
                MAX(CASE WHEN METRIC_NAME = 'VacuumLevel' THEN METRIC_VALUE END) AS VACUUM_MBAR,
                MAX(INGESTION_TIME) AS INGESTION_TIME
            FROM parsed
            GROUP BY EVENT_TIME
            ORDER BY EVENT_TIME DESC
            LIMIT 50
            """,
            timeout=10,
        )
        return {"sensors": data, "timestamp": str(data[0]["INGESTION_TIME"]) if data else None}
    except Exception as e:
        logger.error(f"Failed to fetch live sensors: {e}")
        return {"sensors": [], "timestamp": None}


@app.get("/api/live-sensors-by-asset")
async def get_live_sensors_by_asset():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            WITH parsed AS (
                SELECT 
                    SPLIT_PART(RECORD_METADATA:topic::STRING, '/', -1) AS ASSET_ID,
                    TO_TIMESTAMP(RECORD_CONTENT:timestamp::NUMBER / 1000) AS EVENT_TIME,
                    m.value:name::STRING AS METRIC_NAME,
                    m.value:value::FLOAT AS METRIC_VALUE,
                    INGESTION_TIME
                FROM SNOWCORE_PDM.RAW.IOT_STREAMING_LIVE,
                LATERAL FLATTEN(input => RECORD_CONTENT:metrics) m
                WHERE INGESTION_TIME > DATEADD('second', -30, CURRENT_TIMESTAMP())
            )
            SELECT 
                ASSET_ID,
                EVENT_TIME,
                MAX(CASE WHEN METRIC_NAME = 'Temperature' THEN METRIC_VALUE END) AS TEMPERATURE_C,
                MAX(CASE WHEN METRIC_NAME = 'Humidity' THEN METRIC_VALUE END) AS HUMIDITY_PCT,
                MAX(CASE WHEN METRIC_NAME = 'Pressure' THEN METRIC_VALUE END) AS PRESSURE_PSI,
                MAX(CASE WHEN METRIC_NAME = 'Vibration' THEN METRIC_VALUE END) AS VIBRATION_G,
                MAX(CASE WHEN METRIC_NAME = 'VacuumLevel' THEN METRIC_VALUE END) AS VACUUM_MBAR,
                MAX(INGESTION_TIME) AS INGESTION_TIME
            FROM parsed
            GROUP BY ASSET_ID, EVENT_TIME
            ORDER BY ASSET_ID, EVENT_TIME DESC
            """,
            timeout=10,
        )
        return {"sensors": data, "timestamp": str(data[0]["INGESTION_TIME"]) if data else None}
    except Exception as e:
        logger.error(f"Failed to fetch live sensors by asset: {e}")
        return {"sensors": [], "timestamp": None}


@app.get("/api/cure-results")
async def get_cure_results():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT 
                BATCH_ID,
                AUTOCLAVE_ID,
                CURE_TIMESTAMP,
                LAYUP_HUMIDITY_AVG,
                LAYUP_HUMIDITY_PEAK,
                SCRAP_FLAG,
                DELAMINATION_SCORE,
                FAILURE_MODE
            FROM SNOWCORE_PDM.PDM.CURE_RESULTS
            ORDER BY CURE_TIMESTAMP DESC
            LIMIT 100
            """,
            timeout=30,
        )
        return {"results": data}
    except Exception as e:
        logger.error(f"Failed to fetch cure results: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cure results")


@app.get("/api/gnn-propagation")
async def get_gnn_propagation():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT 
                SOURCE_ASSET,
                TARGET_ASSET,
                PROPAGATION_SCORE,
                PROPAGATION_TYPE,
                EDGE_TYPE,
                HOP_DISTANCE,
                CONFIDENCE
            FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES
            WHERE RUN_TIMESTAMP = (SELECT MAX(RUN_TIMESTAMP) FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES)
            ORDER BY PROPAGATION_SCORE DESC
            """,
            timeout=30,
        )
        nodes_data = service.execute_query(
            """
            SELECT SOURCE_ASSET AS ASSET, MAX(CONFIDENCE) AS SCORE
            FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES
            WHERE RUN_TIMESTAMP = (SELECT MAX(RUN_TIMESTAMP) FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES)
            GROUP BY SOURCE_ASSET
            ORDER BY SOURCE_ASSET
            """,
            timeout=30,
        )
        return {"propagation": data, "nodes": nodes_data}
    except Exception as e:
        logger.error(f"Failed to fetch GNN propagation: {e}")
        return {"propagation": [], "nodes": []}


@app.get("/api/task-status")
async def get_task_status():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SHOW TASKS IN SCHEMA SNOWCORE_PDM.PDM
            """,
            timeout=10,
        )
        tasks = []
        for row in data:
            tasks.append({
                "name": row.get("name"),
                "state": row.get("state"),
                "schedule": row.get("schedule"),
                "warehouse": row.get("warehouse"),
                "last_run": None,
            })
        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"Failed to fetch task status: {e}")
        return {"tasks": []}


@app.get("/api/anomaly-triggers")
async def get_anomaly_triggers():
    service = get_snowflake_service()
    try:
        data = service.execute_query(
            """
            SELECT 
                ASSET_ID,
                TRIGGER_ACTIVE,
                TRIGGERED_AT,
                TRIGGERED_BY
            FROM SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS
            ORDER BY ASSET_ID
            """,
            timeout=10,
        )
        triggers = [
            {
                "asset_id": row["ASSET_ID"],
                "trigger_active": row["TRIGGER_ACTIVE"],
                "triggered_at": str(row["TRIGGERED_AT"]) if row["TRIGGERED_AT"] else None,
                "triggered_by": row["TRIGGERED_BY"],
            }
            for row in data
        ]
        return {"triggers": triggers}
    except Exception as e:
        logger.error(f"Failed to fetch anomaly triggers: {e}")
        return {"triggers": []}


@app.post("/api/toggle-simulation")
async def toggle_simulation(request: ToggleSimulationRequest):
    service = get_snowflake_service()
    try:
        action = "RESUME" if request.enable else "SUSPEND"
        service.execute_query(
            f"ALTER TASK SNOWCORE_PDM.PDM.SENSOR_GENERATION_TASK {action}",
            timeout=10,
        )
        service.execute_query(
            f"ALTER TASK SNOWCORE_PDM.PDM.SENSOR_CLEANUP_TASK {action}",
            timeout=10,
        )
        if request.enable:
            service.execute_query(
                """
                INSERT INTO SNOWCORE_PDM.RAW.IOT_STREAMING_LIVE (RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME)
                SELECT RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME 
                FROM TABLE(SNOWCORE_PDM.PDM.GENERATE_SENSOR_READINGS(
                    60, 
                    COALESCE((SELECT ASSET_ID FROM SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS WHERE TRIGGER_ACTIVE = TRUE LIMIT 1), ''::VARCHAR)
                ))
                """,
                timeout=30,
            )
        return {"success": True, "state": "started" if request.enable else "suspended"}
    except Exception as e:
        logger.error(f"Failed to toggle simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle simulation: {str(e)}")


@app.post("/api/inject-anomaly")
async def inject_anomaly(request: InjectAnomalyRequest):
    service = get_snowflake_service()
    try:
        service.execute_query(
            "UPDATE SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS SET TRIGGER_ACTIVE = FALSE",
            timeout=10,
        )
        if request.asset_id:
            service.execute_query(
                f"""
                UPDATE SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS
                SET TRIGGER_ACTIVE = TRUE,
                    TRIGGERED_AT = CURRENT_TIMESTAMP(),
                    TRIGGERED_BY = 'REACT_DASHBOARD'
                WHERE ASSET_ID = '{request.asset_id}'
                """,
                timeout=10,
            )
        return {"success": True, "asset_id": request.asset_id}
    except Exception as e:
        logger.error(f"Failed to inject anomaly: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to inject anomaly: {str(e)}")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    service = get_snowflake_service()

    try:
        result = service.call_cortex_agent(message.message)

        return ChatResponse(
            response=result.get("response", "I couldn't process that request."),
            sources=result.get("sources", []),
            tool_calls=result.get("tool_calls", []),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            response=f"I encountered an error connecting to the Cortex Agent: {str(e)}. Please ensure the RELIABILITY_COPILOT agent is deployed in SNOWCORE_PDM.PDM.",
            sources=[],
            tool_calls=[],
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
