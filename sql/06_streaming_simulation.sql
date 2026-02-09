-- Streaming Simulation Infrastructure
-- Creates Python UDTF for sensor generation, live tables, anomaly triggers, and scheduled task

USE DATABASE SNOWCORE_PDM;
USE SCHEMA PDM;

-- 1. Python UDTF to generate sensor readings with optional anomaly injection
CREATE OR REPLACE FUNCTION GENERATE_SENSOR_READINGS(
    num_seconds INT,
    inject_anomaly_asset VARCHAR
)
RETURNS TABLE (
    RECORD_METADATA VARIANT,
    RECORD_CONTENT VARIANT,
    INGESTION_TIME TIMESTAMP_NTZ
)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'SensorGenerator'
AS $$
import random
import json
from datetime import datetime, timedelta

class SensorGenerator:
    ASSETS = {
        'LAYUP_ROOM': {'metrics': [('Humidity', 40, 60), ('Temperature', 20, 25)]},
        'AUTOCLAVE_01': {'metrics': [('Temperature', 150, 200), ('Pressure', 80, 120), ('VacuumLevel', -1.0, -0.92)]},
        'AUTOCLAVE_02': {'metrics': [('Temperature', 150, 200), ('Pressure', 80, 120), ('VacuumLevel', -1.0, -0.92)]},
        'CNC_MILL_01': {'metrics': [('SpindleSpeed', 8000, 12000), ('Vibration', 0.1, 0.5)]},
        'CNC_MILL_02': {'metrics': [('SpindleSpeed', 8000, 12000), ('Vibration', 0.1, 0.5)]},
        'LAYUP_BOT_01': {'metrics': [('TensionN', 80, 120), ('SpeedMPS', 0.8, 1.2)]},
        'LAYUP_BOT_02': {'metrics': [('TensionN', 80, 120), ('SpeedMPS', 0.8, 1.2)]},
    }
    
    def process(self, num_seconds, inject_anomaly_asset):
        base_time = datetime.utcnow()
        
        for sec in range(num_seconds):
            ts = base_time - timedelta(seconds=num_seconds - sec - 1)
            ts_epoch = int(ts.timestamp() * 1000)
            
            for asset_id, config in self.ASSETS.items():
                metrics = []
                for i, (name, low, high) in enumerate(config['metrics']):
                    value = random.uniform(low, high)
                    
                    if asset_id == inject_anomaly_asset:
                        if name == 'VacuumLevel':
                            value = value + 0.15
                        elif name == 'Humidity':
                            value = min(85, value + 25)
                        elif name == 'Vibration':
                            value = value * 2.5
                        elif name == 'Temperature' and 'AUTOCLAVE' in asset_id:
                            value = value + 30
                    
                    metrics.append({
                        'name': name,
                        'alias': i + 1,
                        'timestamp': ts_epoch,
                        'dataType': 'Float',
                        'value': round(value, 2)
                    })
                
                topic = f"spBv1.0/SNOWCORE/DDATA/LINE_01/{asset_id}"
                
                yield (
                    {'topic': topic, 'partition': 0, 'offset': sec},
                    {'timestamp': ts_epoch, 'metrics': metrics, 'seq': sec % 256},
                    ts
                )
$$;

-- 2. Live streaming table (separate from historical data)
CREATE OR REPLACE TABLE RAW.IOT_STREAMING_LIVE (
    RECORD_METADATA VARIANT,
    RECORD_CONTENT VARIANT,
    INGESTION_TIME TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Anomaly trigger configuration table
CREATE TABLE IF NOT EXISTS CONFIG.ANOMALY_TRIGGERS (
    ASSET_ID VARCHAR PRIMARY KEY,
    TRIGGER_ACTIVE BOOLEAN DEFAULT FALSE,
    TRIGGERED_AT TIMESTAMP_NTZ,
    TRIGGERED_BY VARCHAR
);

-- Initialize with all assets
MERGE INTO CONFIG.ANOMALY_TRIGGERS t
USING (
    SELECT column1 as ASSET_ID FROM VALUES 
    ('LAYUP_ROOM'), ('AUTOCLAVE_01'), ('AUTOCLAVE_02'), 
    ('CNC_MILL_01'), ('CNC_MILL_02'), ('LAYUP_BOT_01'), ('LAYUP_BOT_02')
) s
ON t.ASSET_ID = s.ASSET_ID
WHEN NOT MATCHED THEN INSERT (ASSET_ID, TRIGGER_ACTIVE) VALUES (s.ASSET_ID, FALSE);

-- 4. Scheduled task that generates 60 readings per minute
CREATE OR REPLACE TASK SENSOR_GENERATION_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '1 MINUTE'
AS
INSERT INTO RAW.IOT_STREAMING_LIVE (RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME)
SELECT RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME 
FROM TABLE(PDM.GENERATE_SENSOR_READINGS(
    60, 
    COALESCE((SELECT ASSET_ID FROM CONFIG.ANOMALY_TRIGGERS WHERE TRIGGER_ACTIVE = TRUE LIMIT 1), ''::VARCHAR)
));

-- 4b. Cleanup task to remove old data
CREATE OR REPLACE TASK SENSOR_CLEANUP_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '5 MINUTE'
AS
DELETE FROM RAW.IOT_STREAMING_LIVE
WHERE INGESTION_TIME < DATEADD('minute', -10, CURRENT_TIMESTAMP());

-- 5. View for live sensor data (flattened)
CREATE OR REPLACE VIEW ATOMIC.ASSET_SENSORS_LIVE AS
SELECT
    TO_TIMESTAMP_NTZ(RECORD_CONTENT:timestamp::NUMBER / 1000) AS EVENT_TIMESTAMP,
    SPLIT_PART(RECORD_METADATA:topic::STRING, '/', 5) AS ASSET_ID,
    m.value:name::STRING AS METRIC_NAME,
    m.value:value::FLOAT AS METRIC_VALUE
FROM RAW.IOT_STREAMING_LIVE,
LATERAL FLATTEN(input => RECORD_CONTENT:metrics) m
WHERE INGESTION_TIME > DATEADD('minute', -5, CURRENT_TIMESTAMP());

-- Grant permissions
GRANT SELECT ON VIEW ATOMIC.ASSET_SENSORS_LIVE TO ROLE PUBLIC;
GRANT SELECT ON TABLE CONFIG.ANOMALY_TRIGGERS TO ROLE PUBLIC;
GRANT UPDATE ON TABLE CONFIG.ANOMALY_TRIGGERS TO ROLE PUBLIC;
GRANT SELECT ON TABLE RAW.IOT_STREAMING_LIVE TO ROLE PUBLIC;
GRANT INSERT ON TABLE RAW.IOT_STREAMING_LIVE TO ROLE PUBLIC;
GRANT DELETE ON TABLE RAW.IOT_STREAMING_LIVE TO ROLE PUBLIC;
