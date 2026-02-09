-- Snowcore Expected-Cost Maintenance Decision Framework
-- Implements: If P(fail in H) x C_unplanned > C_PM -> Recommend PM

USE DATABASE SNOWCORE_PDM;
USE SCHEMA PDM;

-- ============================================================================
-- 1. FAILURE PROBABILITY TABLE
-- ============================================================================
-- Stores P(failure in next H hours) per asset, fed by anomaly detection models

CREATE OR REPLACE TABLE PDM.FAILURE_PROBABILITY (
    PROBABILITY_ID VARCHAR DEFAULT UUID_STRING(),
    ASSET_ID VARCHAR,
    TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    P_FAIL_24H FLOAT,
    P_FAIL_7D FLOAT,
    CONFIDENCE FLOAT,
    ANOMALY_FEATURES VARIANT,
    MODEL_VERSION VARCHAR DEFAULT 'v1.0'
);

-- ============================================================================
-- 2. ASSET ECONOMICS TABLE
-- ============================================================================
-- Cost parameters per asset: C_unplanned and C_PM

CREATE OR REPLACE TABLE CONFIG.ASSET_ECONOMICS (
    ASSET_ID VARCHAR,
    ASSET_TYPE VARCHAR,
    UNPLANNED_DOWNTIME_HOURS_AVG FLOAT,
    COST_PER_DOWNTIME_HOUR_USD FLOAT,
    REPAIR_COST_AVG_USD FLOAT,
    SCRAP_RISK_USD FLOAT,
    PM_DOWNTIME_HOURS_AVG FLOAT,
    PM_LABOR_COST_USD FLOAT,
    PM_PARTS_COST_USD FLOAT,
    UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO CONFIG.ASSET_ECONOMICS 
    (ASSET_ID, ASSET_TYPE, UNPLANNED_DOWNTIME_HOURS_AVG, COST_PER_DOWNTIME_HOUR_USD, 
     REPAIR_COST_AVG_USD, SCRAP_RISK_USD, PM_DOWNTIME_HOURS_AVG, PM_LABOR_COST_USD, PM_PARTS_COST_USD)
VALUES
    ('AUTOCLAVE_01', 'AUTOCLAVE', 10, 15000, 20000, 50000, 2, 8000, 10000),
    ('AUTOCLAVE_02', 'AUTOCLAVE', 10, 15000, 20000, 50000, 2, 8000, 10000),
    ('CNC_MILL_01', 'CNC', 4, 8000, 5000, 10000, 1, 3000, 2000),
    ('CNC_MILL_02', 'CNC', 4, 8000, 5000, 10000, 1, 3000, 2000),
    ('LAYUP_BOT_01', 'ROBOT', 3, 5000, 3000, 5000, 0.5, 2000, 1500),
    ('LAYUP_BOT_02', 'ROBOT', 3, 5000, 3000, 5000, 0.5, 2000, 1500),
    ('LAYUP_ROOM', 'ENVIRONMENT', 0, 15000, 2000, 150000, 0.5, 500, 500),
    ('QC_STATION_01', 'QC', 2, 5000, 2000, 5000, 0.5, 1000, 500),
    ('QC_STATION_02', 'QC', 2, 5000, 2000, 5000, 0.5, 1000, 500);

-- ============================================================================
-- 3. VIEW FOR COMPUTED COSTS
-- ============================================================================
-- Calculates C_unplanned and C_PM from component costs

CREATE OR REPLACE VIEW CONFIG.V_ASSET_ECONOMICS AS
SELECT 
    ASSET_ID,
    ASSET_TYPE,
    UNPLANNED_DOWNTIME_HOURS_AVG,
    COST_PER_DOWNTIME_HOUR_USD,
    REPAIR_COST_AVG_USD,
    SCRAP_RISK_USD,
    (UNPLANNED_DOWNTIME_HOURS_AVG * COST_PER_DOWNTIME_HOUR_USD + REPAIR_COST_AVG_USD + SCRAP_RISK_USD) AS C_UNPLANNED_USD,
    PM_DOWNTIME_HOURS_AVG,
    PM_LABOR_COST_USD,
    PM_PARTS_COST_USD,
    (PM_DOWNTIME_HOURS_AVG * COST_PER_DOWNTIME_HOUR_USD + PM_LABOR_COST_USD + PM_PARTS_COST_USD) AS C_PM_USD,
    UPDATED_AT
FROM CONFIG.ASSET_ECONOMICS;

-- ============================================================================
-- 4. FAILURE PROBABILITY UDTF
-- ============================================================================
-- Converts anomaly patterns to P(failure in next H)

CREATE OR REPLACE FUNCTION PDM.CALCULATE_FAILURE_PROBABILITY(
    asset_id VARCHAR,
    anomaly_count_90min INTEGER,
    max_anomaly_score FLOAT,
    anomaly_duration_min FLOAT,
    hours_since_maintenance FLOAT,
    asset_type VARCHAR
)
RETURNS TABLE (
    ASSET_ID VARCHAR,
    P_FAIL_24H FLOAT,
    P_FAIL_7D FLOAT,
    CONFIDENCE FLOAT,
    KEY_DRIVERS ARRAY
)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'FailureProbabilityCalculator'
AS $$
class FailureProbabilityCalculator:
    """
    Simple logistic-regression-style failure probability model.
    Maps anomaly features to P(failure in horizon H).
    """
    
    def process(self, asset_id, anomaly_count_90min, max_anomaly_score, 
                anomaly_duration_min, hours_since_maintenance, asset_type):
        
        anomaly_count = anomaly_count_90min or 0
        max_score = max_anomaly_score or 0.0
        duration = anomaly_duration_min or 0.0
        hours_since = hours_since_maintenance or 1000
        atype = asset_type or 'UNKNOWN'
        
        base_risk = {
            'AUTOCLAVE': 0.05,
            'CNC': 0.03,
            'ROBOT': 0.02,
            'ENVIRONMENT': 0.01,
            'QC': 0.01
        }.get(atype, 0.02)
        
        anomaly_factor = min(1.0, anomaly_count * 0.15)
        score_factor = max_score * 0.6
        duration_factor = min(0.3, duration / 100.0)
        
        age_factor = 0.0
        maintenance_threshold = {
            'AUTOCLAVE': 3000,
            'CNC': 2000,
            'ROBOT': 4000,
            'ENVIRONMENT': 8760,
            'QC': 5000
        }.get(atype, 3000)
        
        if hours_since > maintenance_threshold:
            age_factor = min(0.3, (hours_since - maintenance_threshold) / maintenance_threshold * 0.3)
        
        p_24h = min(0.95, base_risk + anomaly_factor + score_factor * 0.5 + duration_factor * 0.5 + age_factor * 0.3)
        p_7d = min(0.95, p_24h * 2.5 + age_factor * 0.5)
        p_7d = min(0.95, max(p_7d, p_24h))
        
        confidence = 0.7 + (0.2 if anomaly_count > 0 else 0) + (0.1 if max_score > 0.5 else 0)
        confidence = min(0.95, confidence)
        
        key_drivers = []
        if anomaly_count > 0:
            key_drivers.append(f"{anomaly_count} anomalies in last 90 minutes (normal: 0-1)")
        if max_score > 0.5:
            key_drivers.append(f"Max anomaly score: {max_score:.2f} (threshold: 0.5)")
        if duration > 30:
            key_drivers.append(f"Anomaly duration: {duration:.0f} min (extended pattern)")
        if hours_since > maintenance_threshold:
            key_drivers.append(f"{hours_since:.0f}h since last maintenance (recommended: {maintenance_threshold}h)")
        if not key_drivers:
            key_drivers.append("Operating within normal parameters")
        
        yield (asset_id, round(p_24h, 3), round(p_7d, 3), round(confidence, 2), key_drivers)
$$;

-- ============================================================================
-- 5. SCHEDULED TASK TO UPDATE FAILURE PROBABILITIES
-- ============================================================================

CREATE OR REPLACE TASK PDM.FAILURE_PROBABILITY_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '5 MINUTE'
AS
INSERT INTO PDM.FAILURE_PROBABILITY (ASSET_ID, P_FAIL_24H, P_FAIL_7D, CONFIDENCE, ANOMALY_FEATURES)
WITH anomaly_stats AS (
    SELECT
        ae.ASSET_ID,
        COUNT(*) AS anomaly_count_90min,
        MAX(ae.ANOMALY_SCORE) AS max_anomaly_score,
        SUM(TIMESTAMPDIFF('minute', ae.TIMESTAMP, COALESCE(ae.RESOLUTION_TIMESTAMP, CURRENT_TIMESTAMP()))) AS anomaly_duration_min
    FROM PDM.ANOMALY_EVENTS ae
    WHERE ae.TIMESTAMP > DATEADD('minute', -90, CURRENT_TIMESTAMP())
      AND ae.RESOLVED = FALSE
    GROUP BY ae.ASSET_ID
),
last_maintenance AS (
    SELECT
        ASSET_ID,
        MAX(TIMESTAMP) AS last_maint_time,
        TIMESTAMPDIFF('hour', MAX(TIMESTAMP), CURRENT_TIMESTAMP()) AS hours_since_maintenance
    FROM ATOMIC.MAINTENANCE_LOGS
    GROUP BY ASSET_ID
),
all_assets AS (
    SELECT DISTINCT ASSET_ID, ASSET_TYPE FROM CONFIG.ASSET_ECONOMICS
)
SELECT
    fp.ASSET_ID,
    fp.P_FAIL_24H,
    fp.P_FAIL_7D,
    fp.CONFIDENCE,
    OBJECT_CONSTRUCT(
        'anomaly_count', COALESCE(ast.anomaly_count_90min, 0),
        'max_score', COALESCE(ast.max_anomaly_score, 0),
        'duration_min', COALESCE(ast.anomaly_duration_min, 0),
        'hours_since_maint', COALESCE(lm.hours_since_maintenance, 1000),
        'key_drivers', fp.KEY_DRIVERS
    ) AS ANOMALY_FEATURES
FROM all_assets aa
LEFT JOIN anomaly_stats ast ON aa.ASSET_ID = ast.ASSET_ID
LEFT JOIN last_maintenance lm ON aa.ASSET_ID = lm.ASSET_ID
CROSS JOIN TABLE(PDM.CALCULATE_FAILURE_PROBABILITY(
    aa.ASSET_ID,
    COALESCE(ast.anomaly_count_90min, 0)::INTEGER,
    COALESCE(ast.max_anomaly_score, 0.0)::FLOAT,
    COALESCE(ast.anomaly_duration_min, 0.0)::FLOAT,
    COALESCE(lm.hours_since_maintenance, 1000.0)::FLOAT,
    aa.ASSET_TYPE
)) fp;

-- ============================================================================
-- 6. MAINTENANCE DECISIONS DYNAMIC TABLE
-- ============================================================================
-- Applies the expected-cost rule: If P_fail * C_unplanned > C_PM -> Recommend PM

CREATE OR REPLACE DYNAMIC TABLE PDM.MAINTENANCE_DECISIONS_LIVE
TARGET_LAG = '1 minute'
WAREHOUSE = COMPUTE_WH
AS
WITH latest_probabilities AS (
    SELECT 
        ASSET_ID,
        P_FAIL_24H,
        P_FAIL_7D,
        CONFIDENCE,
        ANOMALY_FEATURES,
        TIMESTAMP
    FROM PDM.FAILURE_PROBABILITY
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ASSET_ID ORDER BY TIMESTAMP DESC) = 1
),
with_economics AS (
    SELECT
        lp.ASSET_ID,
        lp.P_FAIL_24H,
        lp.P_FAIL_7D,
        lp.CONFIDENCE,
        lp.ANOMALY_FEATURES,
        ae.ASSET_TYPE,
        ae.C_UNPLANNED_USD,
        ae.C_PM_USD,
        ae.UNPLANNED_DOWNTIME_HOURS_AVG,
        ae.COST_PER_DOWNTIME_HOUR_USD,
        ae.REPAIR_COST_AVG_USD,
        ae.SCRAP_RISK_USD,
        ae.PM_DOWNTIME_HOURS_AVG,
        ae.PM_LABOR_COST_USD,
        ae.PM_PARTS_COST_USD,
        lp.P_FAIL_7D * ae.C_UNPLANNED_USD AS EXPECTED_UNPLANNED_COST,
        (lp.P_FAIL_7D * ae.C_UNPLANNED_USD) - ae.C_PM_USD AS NET_BENEFIT
    FROM latest_probabilities lp
    JOIN CONFIG.V_ASSET_ECONOMICS ae ON lp.ASSET_ID = ae.ASSET_ID
)
SELECT
    ASSET_ID,
    ASSET_TYPE,
    CURRENT_TIMESTAMP() AS DECISION_TIMESTAMP,
    P_FAIL_24H,
    P_FAIL_7D,
    P_FAIL_7D AS P_FAIL_H,
    CONFIDENCE,
    C_UNPLANNED_USD,
    C_PM_USD,
    ROUND(EXPECTED_UNPLANNED_COST, 0) AS EXPECTED_UNPLANNED_COST,
    ROUND(NET_BENEFIT, 0) AS NET_BENEFIT,
    CASE
        WHEN P_FAIL_7D > 0.6 OR NET_BENEFIT > C_PM_USD * 2 THEN 'URGENT'
        WHEN NET_BENEFIT > 0 THEN 'PLAN_PM'
        ELSE 'MONITOR'
    END AS RECOMMENDATION,
    CASE
        WHEN P_FAIL_7D > 0.6 THEN 'THIS_SHIFT'
        WHEN NET_BENEFIT > C_PM_USD THEN 'NEXT_STOP'
        ELSE 'WITHIN_7D'
    END AS TARGET_WINDOW,
    ANOMALY_FEATURES,
    UNPLANNED_DOWNTIME_HOURS_AVG,
    COST_PER_DOWNTIME_HOUR_USD,
    REPAIR_COST_AVG_USD,
    SCRAP_RISK_USD,
    PM_DOWNTIME_HOURS_AVG,
    PM_LABOR_COST_USD,
    PM_PARTS_COST_USD
FROM with_economics;

-- ============================================================================
-- 7. SEED INITIAL FAILURE PROBABILITIES
-- ============================================================================
-- Insert initial probability data so the dynamic table has data immediately

INSERT INTO PDM.FAILURE_PROBABILITY (ASSET_ID, P_FAIL_24H, P_FAIL_7D, CONFIDENCE, ANOMALY_FEATURES)
SELECT
    fp.ASSET_ID,
    fp.P_FAIL_24H,
    fp.P_FAIL_7D,
    fp.CONFIDENCE,
    OBJECT_CONSTRUCT(
        'anomaly_count', 0,
        'max_score', 0,
        'duration_min', 0,
        'hours_since_maint', 1000,
        'key_drivers', fp.KEY_DRIVERS
    )
FROM CONFIG.ASSET_ECONOMICS ae
CROSS JOIN TABLE(PDM.CALCULATE_FAILURE_PROBABILITY(
    ae.ASSET_ID,
    0,
    0.0,
    0.0,
    1000.0,
    ae.ASSET_TYPE
)) fp;

-- Insert some elevated risk for demo purposes on specific assets
UPDATE PDM.FAILURE_PROBABILITY
SET P_FAIL_24H = 0.15, 
    P_FAIL_7D = 0.32,
    ANOMALY_FEATURES = OBJECT_CONSTRUCT(
        'anomaly_count', 3,
        'max_score', 0.78,
        'duration_min', 45,
        'hours_since_maint', 3500,
        'key_drivers', ARRAY_CONSTRUCT(
            '3 anomalies in last 90 minutes (normal: 0-1)',
            'Vacuum decay rate accelerating',
            '3,500h since last maintenance (recommended: 3,000h)'
        )
    )
WHERE ASSET_ID = 'AUTOCLAVE_01';

UPDATE PDM.FAILURE_PROBABILITY
SET P_FAIL_24H = 0.08, 
    P_FAIL_7D = 0.18,
    ANOMALY_FEATURES = OBJECT_CONSTRUCT(
        'anomaly_count', 2,
        'max_score', 0.62,
        'duration_min', 120,
        'hours_since_maint', 2000,
        'key_drivers', ARRAY_CONSTRUCT(
            '2 humidity excursions in last 90 minutes',
            'Peak humidity 68% (threshold: 65%)',
            'Downstream batches at elevated scrap risk'
        )
    )
WHERE ASSET_ID = 'LAYUP_ROOM';

-- ============================================================================
-- 8. GRANTS AND VERIFICATION
-- ============================================================================

GRANT SELECT ON TABLE PDM.FAILURE_PROBABILITY TO ROLE PUBLIC;
GRANT SELECT ON TABLE CONFIG.ASSET_ECONOMICS TO ROLE PUBLIC;
GRANT SELECT ON VIEW CONFIG.V_ASSET_ECONOMICS TO ROLE PUBLIC;
GRANT SELECT ON DYNAMIC TABLE PDM.MAINTENANCE_DECISIONS_LIVE TO ROLE PUBLIC;
GRANT USAGE ON FUNCTION PDM.CALCULATE_FAILURE_PROBABILITY(VARCHAR, INTEGER, FLOAT, FLOAT, FLOAT, VARCHAR) TO ROLE PUBLIC;

SELECT 'FAILURE_PROBABILITY_TABLE' AS component, 'PDM.FAILURE_PROBABILITY' AS name, 'READY' AS status
UNION ALL
SELECT 'ECONOMICS_TABLE', 'CONFIG.ASSET_ECONOMICS', 'READY'
UNION ALL
SELECT 'ECONOMICS_VIEW', 'CONFIG.V_ASSET_ECONOMICS', 'READY'
UNION ALL
SELECT 'PROBABILITY_UDTF', 'PDM.CALCULATE_FAILURE_PROBABILITY', 'READY'
UNION ALL
SELECT 'PROBABILITY_TASK', 'PDM.FAILURE_PROBABILITY_TASK', 'SUSPENDED (run ALTER TASK ... RESUME to start)'
UNION ALL
SELECT 'DECISIONS_DT', 'PDM.MAINTENANCE_DECISIONS_LIVE', 'READY';
