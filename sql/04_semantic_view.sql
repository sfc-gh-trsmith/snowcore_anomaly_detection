-- Semantic View for Cortex Analyst
-- Creates a semantic view for predictive maintenance analytics

USE DATABASE SNOWCORE_PDM;
USE SCHEMA PDM;

CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  'SNOWCORE_PDM.PDM',
  $$
name: SNOWCORE_PDM_SEMANTIC_VIEW
description: |
  Semantic model for Snowcore Industries Predictive Maintenance analytics.
  Enables natural language queries about asset health, maintenance costs,
  and production quality metrics.

tables:
  - name: FINANCIAL_SUMMARY
    base_table:
      database: SNOWCORE_PDM
      schema: DATA_MART
      table: FINANCIAL_SUMMARY
    description: Monthly aggregated financial metrics for downtime, quality, and maintenance costs
    
    dimensions:
      - name: month
        expr: MONTH
        description: Calendar month of the metrics
        data_type: DATE
        
      - name: scenario
        expr: SCENARIO
        description: Before or After implementation of anomaly detection system
        data_type: TEXT
        sample_values:
          - BEFORE
          - AFTER
    
    measures:
      - name: downtime_hours
        expr: DOWNTIME_HOURS
        description: Total unplanned downtime hours
        data_type: NUMBER
        default_aggregation: sum
        
      - name: downtime_cost_usd
        expr: DOWNTIME_COST_USD
        description: Financial cost of unplanned downtime in USD
        data_type: NUMBER
        default_aggregation: sum
        
      - name: scrap_count
        expr: SCRAP_COUNT
        description: Number of scrapped units
        data_type: NUMBER
        default_aggregation: sum
        
      - name: scrap_cost_usd
        expr: SCRAP_COST_USD
        description: Financial cost of scrapped units in USD
        data_type: NUMBER
        default_aggregation: sum
        
      - name: oee_pct
        expr: OEE_PCT
        description: Overall Equipment Effectiveness percentage
        data_type: NUMBER
        default_aggregation: avg

  - name: MAINTENANCE_LOGS
    base_table:
      database: SNOWCORE_PDM
      schema: ATOMIC
      table: MAINTENANCE_LOGS
    description: Historical maintenance work orders and resolutions
    
    dimensions:
      - name: asset_id
        expr: ASSET_ID
        description: Unique identifier for the asset
        data_type: TEXT
          
      - name: failure_reason
        expr: FAILURE_REASON
        description: Category of failure or maintenance trigger
        data_type: TEXT
        
      - name: work_order_id
        expr: WORK_ORDER_ID
        description: Work order reference number
        data_type: TEXT
        
      - name: timestamp
        expr: TIMESTAMP
        description: Date and time of maintenance event
        data_type: TIMESTAMP
    
    measures:
      - name: downtime_minutes
        expr: DOWNTIME_MINUTES
        description: Duration of downtime in minutes
        data_type: NUMBER
        default_aggregation: sum

  - name: ANOMALY_EVENTS
    base_table:
      database: SNOWCORE_PDM
      schema: PDM
      table: ANOMALY_EVENTS
    description: Detected anomalies from ML models with severity and root cause
    
    dimensions:
      - name: asset_id
        expr: ASSET_ID
        description: Asset where anomaly was detected
        data_type: TEXT
        
      - name: anomaly_type
        expr: ANOMALY_TYPE
        description: Category of anomaly
        data_type: TEXT
          
      - name: severity
        expr: SEVERITY
        description: Severity level of the anomaly
        data_type: TEXT
        
      - name: root_cause
        expr: ROOT_CAUSE
        description: Identified or suspected root cause
        data_type: TEXT
        
      - name: resolved
        expr: RESOLVED
        description: Whether the anomaly has been resolved
        data_type: BOOLEAN
        
      - name: timestamp
        expr: TIMESTAMP
        description: Time when anomaly was detected
        data_type: TIMESTAMP
    
    measures:
      - name: anomaly_score
        expr: ANOMALY_SCORE
        description: Confidence score of anomaly detection (0-1)
        data_type: NUMBER
        default_aggregation: avg

  - name: CURE_RESULTS
    base_table:
      database: SNOWCORE_PDM
      schema: PDM
      table: CURE_RESULTS
    description: Autoclave cure results with humidity correlation data
    
    dimensions:
      - name: batch_id
        expr: BATCH_ID
        description: Production batch identifier
        data_type: TEXT
        
      - name: autoclave_id
        expr: AUTOCLAVE_ID
        description: Which autoclave processed the batch
        data_type: TEXT
          
      - name: scrap_flag
        expr: SCRAP_FLAG
        description: Whether the batch was scrapped
        data_type: BOOLEAN
          
      - name: cure_timestamp
        expr: CURE_TIMESTAMP
        description: Timestamp when cure cycle completed
        data_type: TIMESTAMP
    
    measures:
      - name: layup_humidity_avg
        expr: LAYUP_HUMIDITY_AVG
        description: Average humidity during layup phase
        data_type: NUMBER
        default_aggregation: avg
        
      - name: layup_humidity_peak
        expr: LAYUP_HUMIDITY_PEAK
        description: Peak humidity during layup phase
        data_type: NUMBER
        default_aggregation: max
        
      - name: delamination_score
        expr: DELAMINATION_SCORE
        description: Delamination severity score (0-100)
        data_type: NUMBER
        default_aggregation: avg
  $$
);

GRANT SELECT ON SEMANTIC VIEW SNOWCORE_PDM.PDM.SNOWCORE_PDM_SEMANTIC_VIEW TO ROLE PUBLIC;
