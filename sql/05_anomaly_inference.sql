-- Snowcore Anomaly Detection - Inference Infrastructure
-- Creates UDTF, scheduled task, and propagation dynamic table

USE DATABASE SNOWCORE_PDM;
USE SCHEMA PDM;

-- ============================================================================
-- 1. ANOMALY DETECTION UDTF
-- ============================================================================
-- Threshold-based anomaly detection with model inference logic embedded

CREATE OR REPLACE FUNCTION PDM.DETECT_ANOMALIES(
    asset_id VARCHAR,
    temperature_c FLOAT,
    pressure_psi FLOAT,
    vacuum_mbar FLOAT,
    humidity_pct FLOAT,
    vibration_g FLOAT
)
RETURNS TABLE (
    ASSET_ID VARCHAR,
    ANOMALY_TYPE VARCHAR,
    ANOMALY_SCORE FLOAT,
    SEVERITY VARCHAR,
    ROOT_CAUSE VARCHAR,
    SUGGESTED_FIX VARCHAR
)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'AnomalyDetector'
AS $$
class AnomalyDetector:
    """
    Multi-model anomaly detector combining:
    - Model A: Humidity threshold for layup room
    - Model B: Sensor pattern analysis for autoclave
    - Model C: Threshold detection for CNC mills
    """
    
    def process(self, asset_id, temperature_c, pressure_psi, vacuum_mbar, humidity_pct, vibration_g):
        anomalies = []
        
        if asset_id and 'LAYUP_ROOM' in asset_id:
            humidity = humidity_pct or 50
            if humidity > 65:
                score = min(1.0, (humidity - 65) / 20)
                severity = 'CRITICAL' if humidity > 75 else 'WARNING'
                anomalies.append((
                    asset_id,
                    'HIGH_HUMIDITY',
                    score,
                    severity,
                    'Ambient humidity exceeds threshold - risk of moisture-induced delamination',
                    'Activate dehumidifiers, delay layup operations until humidity < 65%'
                ))
        
        elif asset_id and 'AUTOCLAVE' in asset_id:
            vacuum = vacuum_mbar if vacuum_mbar is not None else -0.95
            temp = temperature_c if temperature_c is not None else 175
            pressure = pressure_psi if pressure_psi is not None else 100
            
            if vacuum > -0.9:
                score = min(1.0, (vacuum + 0.9) / 0.15)
                severity = 'CRITICAL' if vacuum > -0.85 else 'WARNING'
                anomalies.append((
                    asset_id,
                    'VACUUM_DEGRADATION',
                    score,
                    severity,
                    'Vacuum seal wear or leak detected - cure quality at risk',
                    'Inspect door seal and gaskets, check vacuum pump operation'
                ))
            
            if temp > 195:
                score = min(1.0, (temp - 195) / 15)
                anomalies.append((
                    asset_id,
                    'TEMPERATURE_HIGH',
                    score,
                    'WARNING',
                    'Temperature above optimal cure range',
                    'Check heating element calibration and thermocouples'
                ))
            elif temp < 155:
                score = min(1.0, (155 - temp) / 15)
                anomalies.append((
                    asset_id,
                    'TEMPERATURE_LOW',
                    score,
                    'WARNING',
                    'Temperature below optimal cure range',
                    'Verify heating elements and insulation'
                ))
            
            if pressure > 115:
                score = min(1.0, (pressure - 115) / 15)
                anomalies.append((
                    asset_id,
                    'PRESSURE_HIGH',
                    score,
                    'WARNING',
                    'Pressure exceeds optimal range',
                    'Check pressure relief valves and regulators'
                ))
        
        elif asset_id and 'CNC_MILL' in asset_id:
            vibration = vibration_g if vibration_g is not None else 0.3
            if vibration > 0.8:
                score = min(1.0, vibration / 1.2)
                severity = 'CRITICAL' if vibration > 1.0 else 'WARNING'
                anomalies.append((
                    asset_id,
                    'VIBRATION_SPIKE',
                    score,
                    severity,
                    'Spindle bearing wear or tool imbalance detected',
                    'Check spindle alignment, inspect bearings, verify tool condition'
                ))
        
        for anomaly in anomalies:
            yield anomaly
$$;

-- Test the UDTF
-- SELECT * FROM TABLE(PDM.DETECT_ANOMALIES('AUTOCLAVE_01', 180, 100, -0.82, NULL, NULL));
-- SELECT * FROM TABLE(PDM.DETECT_ANOMALIES('LAYUP_ROOM', NULL, NULL, NULL, 72, NULL));
-- SELECT * FROM TABLE(PDM.DETECT_ANOMALIES('CNC_MILL_01', NULL, NULL, NULL, NULL, 0.95));


-- ============================================================================
-- 2. MODEL METRICS TABLE (for tracking model performance)
-- ============================================================================

CREATE TABLE IF NOT EXISTS PDM.MODEL_METRICS (
    METRIC_ID STRING DEFAULT UUID_STRING(),
    MODEL_NAME STRING,
    MODEL_TYPE STRING,
    METRICS VARIANT,
    TRAINED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================================
-- 3. ANOMALY TRIGGERS CONFIG TABLE (for streaming simulation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS CONFIG.ANOMALY_TRIGGERS (
    ASSET_ID VARCHAR,
    TRIGGER_ACTIVE BOOLEAN DEFAULT FALSE,
    TRIGGERED_AT TIMESTAMP_NTZ,
    TRIGGERED_BY VARCHAR
);

MERGE INTO CONFIG.ANOMALY_TRIGGERS t
USING (
    SELECT DISTINCT ASSET_ID 
    FROM DATA_MART.ASSET_STATUS
    WHERE ASSET_ID IS NOT NULL
) s
ON t.ASSET_ID = s.ASSET_ID
WHEN NOT MATCHED THEN
    INSERT (ASSET_ID, TRIGGER_ACTIVE)
    VALUES (s.ASSET_ID, FALSE);


-- ============================================================================
-- 4. SCHEDULED INFERENCE TASK
-- ============================================================================
-- Runs every 5 minutes to detect anomalies from sensor data

CREATE OR REPLACE TASK PDM.ANOMALY_DETECTION_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '5 MINUTE'
AS
INSERT INTO PDM.ANOMALY_EVENTS (
    ASSET_ID, TIMESTAMP, ANOMALY_TYPE, ANOMALY_SCORE,
    SEVERITY, ROOT_CAUSE, SUGGESTED_FIX
)
WITH latest_readings AS (
    SELECT 
        ASSET_ID,
        MAX(EVENT_TIMESTAMP) AS ts,
        AVG(TEMPERATURE_C) AS temp,
        AVG(PRESSURE_PSI) AS pressure,
        AVG(VACUUM_MBAR) AS vacuum,
        AVG(HUMIDITY_PCT) AS humidity,
        AVG(VIBRATION_G) AS vibration
    FROM ATOMIC.ASSET_SENSORS_WIDE
    WHERE EVENT_TIMESTAMP > DATEADD('minute', -5, CURRENT_TIMESTAMP())
    GROUP BY ASSET_ID
)
SELECT 
    d.ASSET_ID,
    lr.ts,
    d.ANOMALY_TYPE,
    d.ANOMALY_SCORE,
    d.SEVERITY,
    d.ROOT_CAUSE,
    d.SUGGESTED_FIX
FROM latest_readings lr,
TABLE(PDM.DETECT_ANOMALIES(
    lr.ASSET_ID, 
    lr.temp, 
    lr.pressure, 
    lr.vacuum, 
    lr.humidity, 
    lr.vibration
)) d
WHERE NOT EXISTS (
    SELECT 1 FROM PDM.ANOMALY_EVENTS ae
    WHERE ae.ASSET_ID = d.ASSET_ID
      AND ae.ANOMALY_TYPE = d.ANOMALY_TYPE
      AND ae.TIMESTAMP > DATEADD('minute', -30, CURRENT_TIMESTAMP())
      AND ae.RESOLVED = FALSE
);


-- ============================================================================
-- 5. ANOMALY PROPAGATION DYNAMIC TABLE
-- ============================================================================
-- Propagates anomalies through the asset dependency graph

CREATE OR REPLACE DYNAMIC TABLE PDM.ANOMALY_PROPAGATION
TARGET_LAG = '1 minute'
WAREHOUSE = COMPUTE_WH
AS
WITH active_anomalies AS (
    SELECT 
        ae.ASSET_ID, 
        ae.ANOMALY_TYPE, 
        ae.ANOMALY_SCORE, 
        ae.TIMESTAMP,
        ae.SEVERITY
    FROM PDM.ANOMALY_EVENTS ae
    WHERE ae.RESOLVED = FALSE
      AND ae.TIMESTAMP > DATEADD('hour', -24, CURRENT_TIMESTAMP())
),
graph_edges AS (
    SELECT 
        SOURCE_ASSET,
        TARGET_ASSET,
        WEIGHT,
        LAG_HOURS,
        EDGE_TYPE
    FROM CONFIG.ASSET_GRAPH
),
propagated AS (
    SELECT
        aa.ASSET_ID AS SOURCE_ASSET,
        ge.TARGET_ASSET,
        aa.ANOMALY_TYPE,
        aa.ANOMALY_SCORE * ge.WEIGHT AS PROPAGATED_SCORE,
        ge.LAG_HOURS,
        aa.TIMESTAMP AS SOURCE_TIMESTAMP,
        DATEADD('hour', ge.LAG_HOURS, aa.TIMESTAMP) AS EXPECTED_IMPACT_TIME,
        ge.EDGE_TYPE
    FROM active_anomalies aa
    JOIN graph_edges ge ON aa.ASSET_ID = ge.SOURCE_ASSET
)
SELECT
    p.TARGET_ASSET AS ASSET_ID,
    'PROPAGATED_' || p.ANOMALY_TYPE AS ANOMALY_TYPE,
    p.PROPAGATED_SCORE AS RISK_SCORE,
    p.SOURCE_ASSET,
    p.LAG_HOURS,
    p.EXPECTED_IMPACT_TIME,
    p.SOURCE_TIMESTAMP,
    CASE 
        WHEN p.PROPAGATED_SCORE > 0.7 THEN 'HIGH'
        WHEN p.PROPAGATED_SCORE > 0.4 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS RISK_LEVEL,
    p.EDGE_TYPE
FROM propagated p
WHERE p.PROPAGATED_SCORE > 0.3;


-- ============================================================================
-- 6. VIEW FOR CURRENT ASSET STATUS WITH ANOMALIES
-- ============================================================================

CREATE OR REPLACE VIEW DATA_MART.V_ASSET_ANOMALY_STATUS AS
WITH current_anomalies AS (
    SELECT 
        ASSET_ID,
        COUNT(*) AS active_anomaly_count,
        MAX(SEVERITY) AS max_severity,
        MAX(ANOMALY_SCORE) AS max_score,
        LISTAGG(DISTINCT ANOMALY_TYPE, ', ') AS anomaly_types
    FROM PDM.ANOMALY_EVENTS
    WHERE RESOLVED = FALSE
      AND TIMESTAMP > DATEADD('hour', -24, CURRENT_TIMESTAMP())
    GROUP BY ASSET_ID
),
propagation_risks AS (
    SELECT 
        ASSET_ID,
        COUNT(*) AS propagation_risk_count,
        MAX(RISK_SCORE) AS max_propagation_risk,
        MAX(RISK_LEVEL) AS max_risk_level
    FROM PDM.ANOMALY_PROPAGATION
    GROUP BY ASSET_ID
)
SELECT
    ast.ASSET_ID,
    ast.ASSET_NAME,
    ast.ASSET_TYPE,
    ast.LINE_ID,
    COALESCE(ca.max_severity, pr.max_risk_level, ast.STATUS) AS CURRENT_STATUS,
    COALESCE(ca.max_score, pr.max_propagation_risk, ast.HEALTH_SCORE) AS HEALTH_SCORE,
    ca.active_anomaly_count,
    ca.anomaly_types,
    pr.propagation_risk_count,
    pr.max_risk_level AS propagation_risk,
    ast.UPDATED_AT
FROM DATA_MART.ASSET_STATUS ast
LEFT JOIN current_anomalies ca ON ast.ASSET_ID = ca.ASSET_ID
LEFT JOIN propagation_risks pr ON ast.ASSET_ID = pr.ASSET_ID;


-- ============================================================================
-- 7. GRANT PERMISSIONS
-- ============================================================================

-- Grant execute on UDTF
GRANT USAGE ON FUNCTION PDM.DETECT_ANOMALIES(VARCHAR, FLOAT, FLOAT, FLOAT, FLOAT, FLOAT) TO ROLE PUBLIC;

-- Note: Task must be resumed manually:
-- ALTER TASK PDM.ANOMALY_DETECTION_TASK RESUME;

-- Verify setup
SELECT 'UDTF' AS component, 'PDM.DETECT_ANOMALIES' AS name, 'READY' AS status
UNION ALL
SELECT 'TABLE', 'CONFIG.ANOMALY_TRIGGERS', 'READY'
UNION ALL
SELECT 'TASK', 'PDM.ANOMALY_DETECTION_TASK', 'SUSPENDED (run ALTER TASK ... RESUME to start)'
UNION ALL
SELECT 'DYNAMIC TABLE', 'PDM.ANOMALY_PROPAGATION', 'READY'
UNION ALL
SELECT 'VIEW', 'DATA_MART.V_ASSET_ANOMALY_STATUS', 'READY';
