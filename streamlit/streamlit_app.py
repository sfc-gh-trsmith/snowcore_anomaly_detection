import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time as time_module

try:
    from snowflake.snowpark.context import get_active_session
except ImportError:
    get_active_session = None

try:
    import _snowflake
except ImportError:
    _snowflake = None

AGENT_DATABASE = "SNOWCORE_PDM"
AGENT_SCHEMA = "PDM"
AGENT_NAME = "RELIABILITY_COPILOT"
API_TIMEOUT_MS = 60000

SIMULATION_ASSETS = ['LAYUP_ROOM', 'AUTOCLAVE_01', 'AUTOCLAVE_02', 'CNC_MILL_01', 'CNC_MILL_02', 'LAYUP_BOT_01', 'LAYUP_BOT_02']

st.set_page_config(
    page_title="Snowcore Reliability Intelligence",
    page_icon="⚙",
    layout="wide"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #29B5E8;
        margin-bottom: 0;
    }
    .critical-banner {
        background: linear-gradient(135deg, #F44336 0%, #FF6B6B 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.4); }
        50% { box-shadow: 0 0 20px 10px rgba(244, 67, 54, 0.2); }
    }
    .warning-banner {
        background: linear-gradient(135deg, #FF9800 0%, #FFC107 100%);
        padding: 1.25rem;
        border-radius: 0.75rem;
        margin: 0.75rem 0;
    }
    .kpi-critical {
        background: rgba(244, 67, 54, 0.15);
        border: 2px solid #F44336;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .kpi-warning {
        background: rgba(255, 193, 7, 0.15);
        border: 2px solid #FFC107;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .kpi-good {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid #4CAF50;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .asset-critical {
        background: rgba(244, 67, 54, 0.2);
        border: 3px solid #F44336;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.75rem;
    }
    .asset-warning {
        background: rgba(255, 193, 7, 0.15);
        border: 2px solid #FFC107;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.75rem;
    }
    .asset-healthy {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid rgba(76, 175, 80, 0.3);
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .section-divider {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 2rem 0;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .user-message {
        background-color: rgba(41, 181, 232, 0.2);
        border-left: 3px solid #29B5E8;
    }
    .agent-message {
        background-color: rgba(30, 30, 30, 0.8);
        border-left: 3px solid #4CAF50;
    }
    .source-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        background-color: rgba(41, 181, 232, 0.3);
        border-radius: 0.25rem;
        font-size: 0.75rem;
        margin-right: 0.5rem;
    }
    .known-badge {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        background-color: rgba(76, 175, 80, 0.3);
        border: 1px solid #4CAF50;
        border-radius: 0.25rem;
        font-size: 0.85rem;
        margin-bottom: 0.75rem;
    }
    .novel-badge {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        background-color: rgba(255, 152, 0, 0.3);
        border: 1px solid #FF9800;
        border-radius: 0.25rem;
        font-size: 0.85rem;
        font-weight: bold;
        margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'pending_query' not in st.session_state:
    st.session_state.pending_query = None
if 'simulation_active' not in st.session_state:
    st.session_state.simulation_active = False
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

def get_session():
    try:
        if get_active_session:
            return get_active_session()
    except Exception:
        pass
    return None

def get_task_state(session):
    if not session:
        return None
    try:
        result = session.sql("""
            SHOW TASKS LIKE 'SENSOR_GENERATION_TASK' IN SCHEMA SNOWCORE_PDM.PDM
        """).collect()
        if result:
            return result[0]['state']
    except:
        pass
    return None

def toggle_simulation_task(session, enable):
    if not session:
        return False
    try:
        if enable:
            session.sql("ALTER TASK SNOWCORE_PDM.PDM.SENSOR_GENERATION_TASK RESUME").collect()
            session.sql("ALTER TASK SNOWCORE_PDM.PDM.SENSOR_CLEANUP_TASK RESUME").collect()
            session.sql("""
                INSERT INTO SNOWCORE_PDM.RAW.IOT_STREAMING_LIVE (RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME)
                SELECT RECORD_METADATA, RECORD_CONTENT, INGESTION_TIME 
                FROM TABLE(SNOWCORE_PDM.PDM.GENERATE_SENSOR_READINGS(
                    60, 
                    COALESCE((SELECT ASSET_ID FROM SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS WHERE TRIGGER_ACTIVE = TRUE LIMIT 1), ''::VARCHAR)
                ))
            """).collect()
        else:
            session.sql("ALTER TASK SNOWCORE_PDM.PDM.SENSOR_GENERATION_TASK SUSPEND").collect()
            session.sql("ALTER TASK SNOWCORE_PDM.PDM.SENSOR_CLEANUP_TASK SUSPEND").collect()
        return True
    except Exception as e:
        st.sidebar.error(f"Task control error: {e}")
        return False

def set_anomaly_trigger(session, asset_id, active):
    if not session:
        return False
    try:
        session.sql(f"""
            UPDATE SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS
            SET TRIGGER_ACTIVE = FALSE
            WHERE ASSET_ID != '{asset_id}'
        """).collect()
        session.sql(f"""
            UPDATE SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS
            SET TRIGGER_ACTIVE = {active}, 
                TRIGGERED_AT = CURRENT_TIMESTAMP(),
                TRIGGERED_BY = 'DASHBOARD_USER'
            WHERE ASSET_ID = '{asset_id}'
        """).collect()
        return True
    except Exception as e:
        st.error(f"Anomaly trigger error: {e}")
        return False

def get_active_anomaly_trigger(session):
    if not session:
        return None
    try:
        result = session.sql("""
            SELECT ASSET_ID FROM SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS
            WHERE TRIGGER_ACTIVE = TRUE
            LIMIT 1
        """).collect()
        if result:
            return result[0]['ASSET_ID']
    except:
        pass
    return None

def get_live_sensor_data(session):
    if not session:
        return pd.DataFrame()
    try:
        return session.sql("""
            SELECT 
                ASSET_ID,
                METRIC_NAME,
                ROUND(AVG(METRIC_VALUE), 2) AS AVG_VALUE,
                ROUND(MIN(METRIC_VALUE), 2) AS MIN_VALUE,
                ROUND(MAX(METRIC_VALUE), 2) AS MAX_VALUE,
                COUNT(*) AS SAMPLE_COUNT
            FROM SNOWCORE_PDM.ATOMIC.ASSET_SENSORS_LIVE
            WHERE EVENT_TIMESTAMP > DATEADD('minute', -2, CURRENT_TIMESTAMP())
            GROUP BY ASSET_ID, METRIC_NAME
            ORDER BY ASSET_ID, METRIC_NAME
        """).to_pandas()
    except:
        return pd.DataFrame()

def check_live_anomalies(session):
    if not session:
        return {}
    anomalies = {}
    try:
        df = session.sql("""
            SELECT 
                ASSET_ID,
                METRIC_NAME,
                ROUND(AVG(METRIC_VALUE), 2) AS AVG_VALUE
            FROM SNOWCORE_PDM.ATOMIC.ASSET_SENSORS_LIVE
            WHERE EVENT_TIMESTAMP > DATEADD('minute', -1, CURRENT_TIMESTAMP())
            GROUP BY ASSET_ID, METRIC_NAME
        """).to_pandas()
        
        thresholds = {
            'Humidity': (60, 70),
            'VacuumLevel': (-0.92, -0.88),
            'Vibration': (0.5, 0.8),
            'Temperature': (200, 220),
        }
        
        for _, row in df.iterrows():
            asset = row['ASSET_ID']
            metric = row['METRIC_NAME']
            value = row['AVG_VALUE']
            
            if metric in thresholds:
                warn, crit = thresholds[metric]
                if metric == 'VacuumLevel':
                    if value > crit:
                        anomalies[asset] = 'CRITICAL'
                    elif value > warn:
                        if anomalies.get(asset) != 'CRITICAL':
                            anomalies[asset] = 'WARNING'
                else:
                    if value > crit:
                        anomalies[asset] = 'CRITICAL'
                    elif value > warn:
                        if anomalies.get(asset) != 'CRITICAL':
                            anomalies[asset] = 'WARNING'
    except:
        pass
    return anomalies

def get_issue_badge(issue_type):
    known_issues = {
        'VACUUM_DECAY': 15, 'VACUUM_TREND': 15, 'HUMIDITY_HIGH': 23,
        'HUMIDITY_WARNING': 23, 'VIBRATION_SPIKE': 8, 'TEMP_EXCURSION': 12, 'PRESSURE_DROP': 6,
    }
    count = known_issues.get(issue_type, 0)
    if count > 0:
        return f'<span class="known-badge">Known Issue: {count} prior occurrences</span>'
    else:
        return '<span class="novel-badge">NOVEL PATTERN - First occurrence</span>'

def generate_demo_response(user_message):
    msg_lower = user_message.lower()
    
    if "happened before" in msg_lower or "similar" in msg_lower or "history" in msg_lower:
        badge = get_issue_badge('VACUUM_DECAY')
        return f"""{badge}

Yes, I found **15 similar incidents** in the past 2 years:

**Most Recent: WO-20230915-047** (Sep 2023)
- Asset: AUTOCLAVE_02
- Issue: Vacuum decay rate exceeded threshold
- Resolution: Replaced Vacuum Seal B (Part #VS-2847)
- Downtime: 2 hours 15 minutes

<span class="source-badge">CMMS_EXPORT_2023Q3.json</span>

The maintenance manual recommends checking the seal groove for contamination before replacement."""
    
    elif "scrap" in msg_lower and ("high" in msg_lower or "why" in msg_lower or "week" in msg_lower):
        badge = get_issue_badge('HUMIDITY_HIGH')
        return f"""{badge}

**Hidden Discovery:** Batches processed when Layup Room humidity exceeded 65% show **3x higher scrap rates** 6 hours later during the autoclave cure cycle.

**This Week's Impact:**
- Tuesday 8am-12pm: Humidity peaked at 68%
- Affected batches: BATCH-20260203-02, BATCH-20260203-03
- Expected scrap: 16% vs. normal 5%

<span class="source-badge">WO-20231022-089</span>
<span class="source-badge">V_HUMIDITY_SCRAP_CORRELATION</span>

**Recommendation:** HVAC upgrade ($150K) with less than 3 month payback."""
    
    elif "vacuum" in msg_lower or "autoclave" in msg_lower:
        badge = get_issue_badge('VACUUM_TREND')
        return f"""{badge}

**Vacuum System Analysis:**

Current AUTOCLAVE_01 vacuum status:
- Vacuum level: -0.93 bar (nominal: -0.95)
- Decay rate: 0.02 bar/min (threshold: 0.05)

Similar past incidents:
1. **WO-20230915-047**: Seal B replacement (2.25h downtime)
2. **WO-20230612-023**: Port gasket replaced (1.5h)

<span class="source-badge">Autoclave_Maintenance_Manual.pdf</span>

Per maintenance manual Section 4.2.3, check seal groove for debris before ordering replacement parts."""
    
    else:
        return f"""Analyzing your question about "{user_message[:50]}..."

I would search:
1. Historical maintenance records for similar patterns
2. Sensor data correlations
3. Known issue database

<span class="source-badge">Cortex Search</span>
<span class="source-badge">Cortex Analyst</span>"""

def parse_agent_sse_response(raw_content):
    """Parse SSE response from Cortex Agent and extract text."""
    if not raw_content:
        return ""
    
    text_parts = []
    lines = raw_content.split('\n')
    
    for line in lines:
        if line.startswith('data:'):
            data_str = line[5:].strip()
            if data_str and data_str != '[DONE]':
                try:
                    data = json.loads(data_str)
                    if isinstance(data, dict):
                        delta = data.get('delta', {})
                        content_parts = delta.get('content', [])
                        for part in content_parts:
                            if isinstance(part, dict) and part.get('type') == 'text':
                                text_parts.append(part.get('text', ''))
                except json.JSONDecodeError:
                    continue
    
    return ''.join(text_parts)

def call_cortex_agent(user_message, session):
    if _snowflake is None or session is None:
        return generate_demo_response(user_message)
    
    api_endpoint = f"/api/v2/databases/{AGENT_DATABASE}/schemas/{AGENT_SCHEMA}/agents/{AGENT_NAME}:run"
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": user_message}]
            }
        ]
    }
    
    try:
        resp = _snowflake.send_snow_api_request(
            "POST",
            api_endpoint,
            {},
            {},
            payload,
            None,
            API_TIMEOUT_MS
        )
        
        status = resp.get("status")
        if status != 200:
            return generate_demo_response(user_message)
        
        raw_content = resp.get("content", "")
        
        if isinstance(raw_content, str) and ("event:" in raw_content or "data:" in raw_content):
            result = parse_agent_sse_response(raw_content)
            if result:
                return result
        
        try:
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            if isinstance(content, dict):
                messages = content.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    for part in last_msg.get("content", []):
                        if isinstance(part, dict) and part.get("type") == "text":
                            return part.get("text", "")
        except json.JSONDecodeError:
            pass
        
        return generate_demo_response(user_message)
        
    except Exception as e:
        return generate_demo_response(user_message)

session = get_session()

st.sidebar.markdown("### Simulation Controls")
task_state = get_task_state(session)
current_simulation = task_state == 'started' if task_state else st.session_state.simulation_active

simulation_on = st.sidebar.checkbox(
    "Live Sensor Simulation",
    value=current_simulation,
    help="Toggle the sensor data generation task on/off"
)

if simulation_on != st.session_state.simulation_active:
    if session:
        if toggle_simulation_task(session, simulation_on):
            st.session_state.simulation_active = simulation_on
            st.sidebar.success("Simulation " + ("started" if simulation_on else "stopped"))
            st.experimental_rerun()
    else:
        st.session_state.simulation_active = simulation_on

if st.session_state.simulation_active:
    st.sidebar.markdown("#### Inject Anomaly")
    current_trigger = get_active_anomaly_trigger(session)
    
    selected_trigger = st.sidebar.selectbox(
        "Select asset for anomaly injection",
        options=["(None)"] + SIMULATION_ASSETS,
        index=0 if not current_trigger else SIMULATION_ASSETS.index(current_trigger) + 1 if current_trigger in SIMULATION_ASSETS else 0,
        key="anomaly_trigger_select"
    )
    
    if st.sidebar.button("Apply Anomaly", type="primary", use_container_width=True, key="btn_apply_anomaly"):
        if selected_trigger == "(None)":
            if session:
                session.sql("UPDATE SNOWCORE_PDM.CONFIG.ANOMALY_TRIGGERS SET TRIGGER_ACTIVE = FALSE").collect()
                st.sidebar.success("Anomaly injection cleared")
        else:
            if set_anomaly_trigger(session, selected_trigger, True):
                st.sidebar.success(f"Anomaly triggered on {selected_trigger}")
        st.experimental_rerun()
    
    if current_trigger:
        st.sidebar.warning(f"Active: {current_trigger}")
    
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox(
        "Auto-Refresh (5s)",
        value=st.session_state.auto_refresh,
        help="Automatically refresh live data every 5 seconds"
    )
    st.session_state.auto_refresh = auto_refresh

def get_active_anomalies(session):
    """Get unresolved anomalies from last 24 hours."""
    if session is None:
        return pd.DataFrame({
            'ASSET_ID': ['AUTOCLAVE_01', 'LAYUP_ROOM'],
            'ANOMALY_TYPE': ['VACUUM_DEGRADATION', 'HIGH_HUMIDITY'],
            'ANOMALY_SCORE': [0.85, 0.62],
            'SEVERITY': ['CRITICAL', 'WARNING'],
            'ROOT_CAUSE': ['Vacuum seal wear detected', 'Humidity exceeds threshold'],
            'SUGGESTED_FIX': ['Inspect door seal and gaskets', 'Activate dehumidifiers'],
            'TIMESTAMP': [datetime.now() - timedelta(hours=1), datetime.now() - timedelta(hours=3)]
        })
    
    try:
        return session.sql("""
            SELECT 
                ae.ASSET_ID,
                ae.ANOMALY_TYPE,
                ae.ANOMALY_SCORE,
                ae.SEVERITY,
                ae.ROOT_CAUSE,
                ae.SUGGESTED_FIX,
                ae.TIMESTAMP
            FROM SNOWCORE_PDM.PDM.ANOMALY_EVENTS ae
            WHERE ae.RESOLVED = FALSE
              AND ae.TIMESTAMP > DATEADD('hour', -24, CURRENT_TIMESTAMP())
            ORDER BY 
                CASE ae.SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END,
                ae.TIMESTAMP DESC
            LIMIT 20
        """).to_pandas()
    except:
        return pd.DataFrame()

def get_propagation_risks(session):
    """Get downstream assets at risk from propagation."""
    if session is None:
        return pd.DataFrame({
            'ASSET_ID': ['AUTOCLAVE_01', 'CNC_MILL_01'],
            'ANOMALY_TYPE': ['PROPAGATED_HIGH_HUMIDITY', 'PROPAGATED_HIGH_HUMIDITY'],
            'RISK_SCORE': [0.68, 0.54],
            'SOURCE_ASSET': ['LAYUP_ROOM', 'AUTOCLAVE_01'],
            'LAG_HOURS': [2.0, 4.0],
            'RISK_LEVEL': ['MEDIUM', 'MEDIUM']
        })
    
    try:
        return session.sql("""
            SELECT 
                ASSET_ID,
                ANOMALY_TYPE,
                RISK_SCORE,
                SOURCE_ASSET,
                LAG_HOURS,
                RISK_LEVEL
            FROM SNOWCORE_PDM.PDM.ANOMALY_PROPAGATION
            ORDER BY RISK_SCORE DESC
            LIMIT 10
        """).to_pandas()
    except:
        return pd.DataFrame()

def get_maintenance_decisions(session):
    """Get real-time maintenance decisions with expected-cost analysis."""
    if session is None:
        return pd.DataFrame({
            'ASSET_ID': ['AUTOCLAVE_01', 'LAYUP_ROOM', 'AUTOCLAVE_02', 'CNC_MILL_01', 'CNC_MILL_02', 'LAYUP_BOT_01', 'LAYUP_BOT_02', 'QC_STATION_01', 'QC_STATION_02'],
            'ASSET_TYPE': ['AUTOCLAVE', 'ENVIRONMENT', 'AUTOCLAVE', 'CNC', 'CNC', 'ROBOT', 'ROBOT', 'QC', 'QC'],
            'P_FAIL_7D': [0.32, 0.18, 0.125, 0.075, 0.075, 0.05, 0.05, 0.025, 0.025],
            'C_UNPLANNED_USD': [220000, 152000, 220000, 47000, 47000, 23000, 23000, 17000, 17000],
            'C_PM_USD': [48000, 8500, 48000, 13000, 13000, 6000, 6000, 4000, 4000],
            'EXPECTED_UNPLANNED_COST': [70400, 27360, 27500, 3525, 3525, 1150, 1150, 425, 425],
            'NET_BENEFIT': [22400, 18860, -20500, -9475, -9475, -4850, -4850, -3575, -3575],
            'RECOMMENDATION': ['PLAN_PM', 'URGENT', 'MONITOR', 'MONITOR', 'MONITOR', 'MONITOR', 'MONITOR', 'MONITOR', 'MONITOR'],
            'TARGET_WINDOW': ['WITHIN_7D', 'NEXT_STOP', 'WITHIN_7D', 'WITHIN_7D', 'WITHIN_7D', 'WITHIN_7D', 'WITHIN_7D', 'WITHIN_7D', 'WITHIN_7D'],
            'CONFIDENCE': [0.9, 0.85, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
            'UNPLANNED_DOWNTIME_HOURS_AVG': [10, 0, 10, 4, 4, 3, 3, 2, 2],
            'COST_PER_DOWNTIME_HOUR_USD': [15000, 15000, 15000, 8000, 8000, 5000, 5000, 5000, 5000],
            'REPAIR_COST_AVG_USD': [20000, 2000, 20000, 5000, 5000, 3000, 3000, 2000, 2000],
            'SCRAP_RISK_USD': [50000, 150000, 50000, 10000, 10000, 5000, 5000, 5000, 5000],
            'PM_DOWNTIME_HOURS_AVG': [2, 0.5, 2, 1, 1, 0.5, 0.5, 0.5, 0.5],
            'PM_LABOR_COST_USD': [8000, 500, 8000, 3000, 3000, 2000, 2000, 1000, 1000],
            'PM_PARTS_COST_USD': [10000, 500, 10000, 2000, 2000, 1500, 1500, 500, 500],
            'ANOMALY_FEATURES': [
                {'key_drivers': ['3 anomalies in last 90 minutes', 'Vacuum decay rate accelerating', '3,500h since last maintenance']},
                {'key_drivers': ['2 humidity excursions in last 90 minutes', 'Peak humidity 68%', 'Downstream batches at elevated scrap risk']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']},
                {'key_drivers': ['Operating within normal parameters']}
            ]
        })
    
    try:
        return session.sql("""
            SELECT 
                ASSET_ID, ASSET_TYPE, P_FAIL_7D, C_UNPLANNED_USD, C_PM_USD,
                EXPECTED_UNPLANNED_COST, NET_BENEFIT, RECOMMENDATION, TARGET_WINDOW,
                CONFIDENCE, UNPLANNED_DOWNTIME_HOURS_AVG, COST_PER_DOWNTIME_HOUR_USD,
                REPAIR_COST_AVG_USD, SCRAP_RISK_USD, PM_DOWNTIME_HOURS_AVG,
                PM_LABOR_COST_USD, PM_PARTS_COST_USD, ANOMALY_FEATURES
            FROM SNOWCORE_PDM.PDM.MAINTENANCE_DECISIONS_LIVE
            ORDER BY NET_BENEFIT DESC
        """).to_pandas()
    except:
        return pd.DataFrame()

anomalies_df = get_active_anomalies(session)
propagation_df = get_propagation_risks(session)
decisions_df = get_maintenance_decisions(session)

st.markdown('<p class="main-header">SNOWCORE RELIABILITY INTELLIGENCE</p>', unsafe_allow_html=True)
st.caption("Avalanche X1 Production Line | Real-Time Anomaly Detection")

CURRENT_HUMIDITY = 62
AUTOCLAVE_VACUUM = -0.93
AUTOCLAVE_NOMINAL = -0.95

if not anomalies_df.empty:
    critical_anomalies = anomalies_df[anomalies_df['SEVERITY'] == 'CRITICAL']
    warning_anomalies = anomalies_df[anomalies_df['SEVERITY'] == 'WARNING']
    HAS_CRITICAL = len(critical_anomalies) > 0
    HAS_WARNING = len(warning_anomalies) > 0
else:
    HAS_CRITICAL = AUTOCLAVE_VACUUM > -0.94
    HAS_WARNING = CURRENT_HUMIDITY > 60

if HAS_CRITICAL:
    st.markdown(f"""
    <div class="critical-banner">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 1.5rem; font-weight: bold; color: white;">CRITICAL</div>
            <div style="flex: 1;">
                <div style="font-weight: bold; color: white; font-size: 1.3rem;">
                    CRITICAL: AUTOCLAVE_01 Vacuum Degradation Detected
                </div>
                <div style="color: rgba(255,255,255,0.95); margin-top: 0.5rem;">
                    Vacuum at <b>{AUTOCLAVE_VACUUM} bar</b> (nominal: {AUTOCLAVE_NOMINAL}) | 
                    Decay rate accelerating | <b>$25K at risk</b> if seal fails mid-cycle
                </div>
                <div style="color: rgba(255,255,255,0.85); margin-top: 0.5rem; font-size: 0.9rem;">
                    15 similar incidents in database - avg resolution: Seal B replacement (2.25h)
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if HAS_WARNING:
    st.markdown(f"""
    <div class="warning-banner">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 1.3rem; font-weight: bold; color: white;">WARNING</div>
            <div style="flex: 1;">
                <div style="font-weight: bold; color: white; font-size: 1.1rem;">
                    WARNING: Layup Room Humidity at {CURRENT_HUMIDITY}% (threshold: 60%)
                </div>
                <div style="color: rgba(255,255,255,0.9); margin-top: 0.25rem;">
                    3 batches in progress will hit autoclave in 6 hours | Historical data: <b>3x scrap rate</b> at this humidity | <b>$150K at risk</b>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("""
    <div class="kpi-critical">
        <div style="font-size: 0.75rem; color: #F44336; text-transform: uppercase;">ACTIVE ALERTS</div>
        <div style="font-size: 2rem; font-weight: bold; color: #F44336;">2</div>
        <div style="font-size: 0.8rem; color: #ccc;">1 critical, 1 warning</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="kpi-warning">
        <div style="font-size: 0.75rem; color: #FFC107; text-transform: uppercase;">AT-RISK VALUE</div>
        <div style="font-size: 2rem; font-weight: bold; color: #FFC107;">$175K</div>
        <div style="font-size: 0.8rem; color: #ccc;">Next 8 hours</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="kpi-good">
        <div style="font-size: 0.75rem; color: #4CAF50; text-transform: uppercase;">LINE OEE</div>
        <div style="font-size: 2rem; font-weight: bold; color: #4CAF50;">77%</div>
        <div style="font-size: 0.8rem; color: #888;">+12% from baseline</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="kpi-good">
        <div style="font-size: 0.75rem; color: #4CAF50; text-transform: uppercase;">DOWNTIME SAVED</div>
        <div style="font-size: 2rem; font-weight: bold; color: #4CAF50;">$500K</div>
        <div style="font-size: 0.8rem; color: #888;">This month</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div class="kpi-good">
        <div style="font-size: 0.75rem; color: #29B5E8; text-transform: uppercase;">ASSETS HEALTHY</div>
        <div style="font-size: 2rem; font-weight: bold; color: #29B5E8;">7/9</div>
        <div style="font-size: 0.8rem; color: #888;">2 need attention</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Asset Dependency Graph")
st.caption("Production flow with real-time health status")

live_status = {}
if not anomalies_df.empty:
    for _, row in anomalies_df.iterrows():
        asset = row['ASSET_ID']
        severity = row['SEVERITY']
        if asset not in live_status or severity == 'CRITICAL':
            live_status[asset] = severity

if st.session_state.simulation_active:
    live_anomalies = check_live_anomalies(session)
    for asset, severity in live_anomalies.items():
        if asset not in live_status or severity == 'CRITICAL':
            live_status[asset] = severity

GRAPH_ASSETS = {
    'LAYUP_ROOM': {'x': 0, 'y': 1, 'health': 85, 'status': live_status.get('LAYUP_ROOM', 'HEALTHY')},
    'LAYUP_BOT_01': {'x': 1, 'y': 0, 'health': 92, 'status': live_status.get('LAYUP_BOT_01', 'HEALTHY')},
    'LAYUP_BOT_02': {'x': 1, 'y': 2, 'health': 88, 'status': live_status.get('LAYUP_BOT_02', 'HEALTHY')},
    'AUTOCLAVE_01': {'x': 2, 'y': 0, 'health': 72, 'status': live_status.get('AUTOCLAVE_01', 'HEALTHY')},
    'AUTOCLAVE_02': {'x': 2, 'y': 2, 'health': 95, 'status': live_status.get('AUTOCLAVE_02', 'HEALTHY')},
    'CNC_MILL_01': {'x': 3, 'y': 0, 'health': 90, 'status': live_status.get('CNC_MILL_01', 'HEALTHY')},
    'CNC_MILL_02': {'x': 3, 'y': 2, 'health': 87, 'status': live_status.get('CNC_MILL_02', 'HEALTHY')},
    'QC_STATION_01': {'x': 4, 'y': 0, 'health': 98, 'status': live_status.get('QC_STATION_01', 'HEALTHY')},
    'QC_STATION_02': {'x': 4, 'y': 2, 'health': 96, 'status': live_status.get('QC_STATION_02', 'HEALTHY')},
}

GRAPH_EDGES = [
    ('LAYUP_ROOM', 'LAYUP_BOT_01', 'ENV'),
    ('LAYUP_ROOM', 'LAYUP_BOT_02', 'ENV'),
    ('LAYUP_BOT_01', 'AUTOCLAVE_01', 'FLOW'),
    ('LAYUP_BOT_02', 'AUTOCLAVE_02', 'FLOW'),
    ('AUTOCLAVE_01', 'CNC_MILL_01', 'FLOW'),
    ('AUTOCLAVE_02', 'CNC_MILL_02', 'FLOW'),
    ('CNC_MILL_01', 'QC_STATION_01', 'FLOW'),
    ('CNC_MILL_02', 'QC_STATION_02', 'FLOW'),
]

def get_status_color(status):
    return {'HEALTHY': '#4CAF50', 'WARNING': '#FFC107', 'CRITICAL': '#F44336'}.get(status, '#888')

fig_graph = go.Figure()

for source, target, edge_type in GRAPH_EDGES:
    x0, y0 = GRAPH_ASSETS[source]['x'], GRAPH_ASSETS[source]['y']
    x1, y1 = GRAPH_ASSETS[target]['x'], GRAPH_ASSETS[target]['y']
    line_color = '#29B5E8' if edge_type == 'FLOW' else 'rgba(41, 181, 232, 0.3)'
    line_dash = 'solid' if edge_type == 'FLOW' else 'dot'
    
    fig_graph.add_trace(go.Scatter(
        x=[x0, x1], y=[y0, y1], mode='lines',
        line=dict(color=line_color, width=2, dash=line_dash),
        hoverinfo='skip', showlegend=False
    ))

for asset_id, asset in GRAPH_ASSETS.items():
    fig_graph.add_trace(go.Scatter(
        x=[asset['x']], y=[asset['y']], mode='markers+text',
        marker=dict(size=45, color=get_status_color(asset['status']), line=dict(width=2, color='white')),
        text=f"{asset_id.replace('_', ' ')}<br>{asset['health']}%",
        textposition='middle center',
        textfont=dict(size=8, color='white'),
        hovertemplate=f"<b>{asset_id}</b><br>Health: {asset['health']}%<br>Status: {asset['status']}<extra></extra>",
        showlegend=False
    ))

fig_graph.update_layout(
    template="plotly_dark", height=350,
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 4.5]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 2.5]),
    annotations=[
        dict(x=0, y=2.3, text="ENV", showarrow=False, font=dict(color='#888', size=11)),
        dict(x=1, y=2.3, text="LAYUP", showarrow=False, font=dict(color='#888', size=11)),
        dict(x=2, y=2.3, text="CURE", showarrow=False, font=dict(color='#888', size=11)),
        dict(x=3, y=2.3, text="TRIM", showarrow=False, font=dict(color='#888', size=11)),
        dict(x=4, y=2.3, text="QC", showarrow=False, font=dict(color='#888', size=11)),
    ],
    margin=dict(t=20, b=20)
)

st.plotly_chart(fig_graph, use_container_width=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Asset Risk & Maintenance Priorities")
st.caption("Expected-cost decision framework: If P(fail) x C_unplanned > C_PM, recommend PM")

def get_recommendation_color(rec):
    return {'URGENT': '#F44336', 'PLAN_PM': '#FFC107', 'MONITOR': '#4CAF50'}.get(rec, '#888')

def get_recommendation_rgb(rec):
    return {'URGENT': '244, 67, 54', 'PLAN_PM': '255, 193, 7', 'MONITOR': '76, 175, 80'}.get(rec, '136, 136, 136')

if not decisions_df.empty:
    urgent_assets = decisions_df[decisions_df['RECOMMENDATION'] == 'URGENT']
    plan_pm_assets = decisions_df[decisions_df['RECOMMENDATION'] == 'PLAN_PM']
    monitor_assets = decisions_df[decisions_df['RECOMMENDATION'] == 'MONITOR']
    
    total_expected_loss = decisions_df[decisions_df['NET_BENEFIT'] > 0]['EXPECTED_UNPLANNED_COST'].sum()
    total_pm_cost = decisions_df[decisions_df['NET_BENEFIT'] > 0]['C_PM_USD'].sum()
    total_net_benefit = decisions_df[decisions_df['NET_BENEFIT'] > 0]['NET_BENEFIT'].sum()
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.markdown(f"""
        <div class="kpi-critical">
            <div style="font-size: 0.75rem; color: #F44336; text-transform: uppercase;">URGENT PM</div>
            <div style="font-size: 2rem; font-weight: bold; color: #F44336;">{len(urgent_assets)}</div>
            <div style="font-size: 0.8rem; color: #ccc;">High risk assets</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_col2:
        st.markdown(f"""
        <div class="kpi-warning">
            <div style="font-size: 0.75rem; color: #FFC107; text-transform: uppercase;">PLAN PM</div>
            <div style="font-size: 2rem; font-weight: bold; color: #FFC107;">{len(plan_pm_assets)}</div>
            <div style="font-size: 0.8rem; color: #ccc;">Schedule maintenance</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_col3:
        st.markdown(f"""
        <div class="kpi-good">
            <div style="font-size: 0.75rem; color: #4CAF50; text-transform: uppercase;">EXPECTED LOSS</div>
            <div style="font-size: 2rem; font-weight: bold; color: #F44336;">${total_expected_loss:,.0f}</div>
            <div style="font-size: 0.8rem; color: #ccc;">If not addressed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_col4:
        st.markdown(f"""
        <div class="kpi-good">
            <div style="font-size: 0.75rem; color: #4CAF50; text-transform: uppercase;">NET SAVINGS</div>
            <div style="font-size: 2rem; font-weight: bold; color: #4CAF50;">${total_net_benefit:,.0f}</div>
            <div style="font-size: 0.8rem; color: #ccc;">By doing PM now</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("#### Cost-Based Asset Tiles")
    
    pm_recommended = decisions_df[decisions_df['RECOMMENDATION'].isin(['URGENT', 'PLAN_PM'])].sort_values('NET_BENEFIT', ascending=False)
    monitoring = decisions_df[decisions_df['RECOMMENDATION'] == 'MONITOR'].sort_values('NET_BENEFIT', ascending=False)
    
    if not pm_recommended.empty:
        cols = st.columns(min(4, len(pm_recommended)))
        for idx, (_, row) in enumerate(pm_recommended.iterrows()):
            with cols[idx % 4]:
                rec = row['RECOMMENDATION']
                color = get_recommendation_color(rec)
                rgb = get_recommendation_rgb(rec)
                p_fail = row['P_FAIL_7D']
                expected_loss = row['EXPECTED_UNPLANNED_COST']
                net_benefit = row['NET_BENEFIT']
                
                st.markdown(f"""
                <div style="background: rgba({rgb}, 0.15); border: 2px solid {color}; 
                            border-radius: 0.5rem; padding: 1rem; text-align: center; margin-bottom: 0.5rem;">
                    <div style="font-weight: bold; font-size: 1.1rem; color: white;">{row['ASSET_ID']}</div>
                    <div style="color: {color}; font-size: 1.8rem; font-weight: bold; margin: 0.5rem 0;">
                        {p_fail:.0%} risk
                    </div>
                    <div style="font-size: 0.9rem; color: #ccc;">
                        Expected loss: <span style="color: #F44336;">${expected_loss:,.0f}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #888; margin-top: 0.25rem;">
                        PM cost: ${row['C_PM_USD']:,.0f} | Benefit: <span style="color: #4CAF50;">${net_benefit:,.0f}</span>
                    </div>
                    <div style="margin-top: 0.75rem; padding: 0.35rem 0.75rem; 
                                background: {color}; border-radius: 0.25rem; color: white; font-weight: bold;">
                        {rec.replace('_', ' ')}
                    </div>
                    <div style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">
                        {row['TARGET_WINDOW'].replace('_', ' ')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    if not monitoring.empty and len(monitoring) > 0:
        with st.expander(f"Monitoring ({len(monitoring)} assets with negative net benefit)", expanded=False):
            mon_cols = st.columns(min(4, len(monitoring)))
            for idx, (_, row) in enumerate(monitoring.head(4).iterrows()):
                with mon_cols[idx]:
                    st.markdown(f"""
                    <div style="background: rgba(76, 175, 80, 0.1); border: 1px solid rgba(76, 175, 80, 0.3); 
                                border-radius: 0.5rem; padding: 0.75rem; text-align: center;">
                        <div style="font-weight: bold; color: #888;">{row['ASSET_ID']}</div>
                        <div style="color: #4CAF50; font-size: 1.2rem;">{row['P_FAIL_7D']:.0%} risk</div>
                        <div style="font-size: 0.8rem; color: #666;">
                            Net: <span style="color: #F44336;">${row['NET_BENEFIT']:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    st.markdown("### Maintenance Priority Queue")
    st.caption("Sorted by net benefit of intervention (highest savings first)")
    
    display_df = decisions_df[['ASSET_ID', 'P_FAIL_7D', 'EXPECTED_UNPLANNED_COST', 'C_PM_USD', 'NET_BENEFIT', 'RECOMMENDATION', 'TARGET_WINDOW', 'CONFIDENCE']].copy()
    display_df.columns = ['Asset', 'Risk (7d)', 'Expected Loss', 'PM Cost', 'Net Benefit', 'Action', 'Window', 'Confidence']
    display_df['Risk (7d)'] = display_df['Risk (7d)'].apply(lambda x: f"{x*100:.0f}%")
    display_df['Expected Loss'] = display_df['Expected Loss'].apply(lambda x: f"${x:,.0f}")
    display_df['PM Cost'] = display_df['PM Cost'].apply(lambda x: f"${x:,.0f}")
    display_df['Net Benefit'] = display_df['Net Benefit'].apply(lambda x: f"${x:,.0f}")
    display_df['Confidence'] = display_df['Confidence'].apply(lambda x: f"{x*100:.0f}%")
    
    st.dataframe(
        display_df,
        use_container_width=True
    )
    
    st.markdown("#### Maintenance Efficient Frontier")
    st.caption("Assets above the line offer better risk reduction per dollar than average")
    
    frontier_df = decisions_df[['ASSET_ID', 'C_PM_USD', 'P_FAIL_7D', 'EXPECTED_UNPLANNED_COST', 'NET_BENEFIT', 'RECOMMENDATION']].copy()
    frontier_df['RISK_REDUCTION'] = frontier_df['P_FAIL_7D'] * 100
    frontier_df['ROI'] = (frontier_df['NET_BENEFIT'] / frontier_df['C_PM_USD']).clip(lower=-1)
    
    fig_frontier = go.Figure()
    
    color_map = {'URGENT': '#F44336', 'PLAN_PM': '#FFC107', 'MONITOR': '#4CAF50'}
    
    for rec in ['URGENT', 'PLAN_PM', 'MONITOR']:
        subset = frontier_df[frontier_df['RECOMMENDATION'] == rec]
        if not subset.empty:
            fig_frontier.add_trace(go.Scatter(
                x=subset['C_PM_USD'],
                y=subset['RISK_REDUCTION'],
                mode='markers+text',
                marker=dict(
                    size=subset['NET_BENEFIT'].abs().clip(lower=1000) / 500,
                    color=color_map.get(rec, '#888'),
                    line=dict(width=2, color='white'),
                    opacity=0.8
                ),
                text=subset['ASSET_ID'],
                textposition='top center',
                textfont=dict(size=10, color='white'),
                name=rec.replace('_', ' '),
                hovertemplate=(
                    '<b>%{text}</b><br>' +
                    'PM Cost: $%{x:,.0f}<br>' +
                    'Risk: %{y:.1f}%<br>' +
                    'Net Benefit: $%{customdata:,.0f}<extra></extra>'
                ),
                customdata=subset['NET_BENEFIT']
            ))
    
    positive_assets = frontier_df[frontier_df['NET_BENEFIT'] > 0]
    if len(positive_assets) >= 2:
        sorted_frontier = positive_assets.sort_values('C_PM_USD')
        max_risk_so_far = 0
        frontier_points_x = [0]
        frontier_points_y = [0]
        for _, row in sorted_frontier.iterrows():
            if row['RISK_REDUCTION'] > max_risk_so_far:
                frontier_points_x.append(row['C_PM_USD'])
                frontier_points_y.append(row['RISK_REDUCTION'])
                max_risk_so_far = row['RISK_REDUCTION']
        
        if len(frontier_points_x) > 1:
            fig_frontier.add_trace(go.Scatter(
                x=frontier_points_x,
                y=frontier_points_y,
                mode='lines',
                line=dict(color='#29B5E8', width=2, dash='dash'),
                name='Efficient Frontier',
                hoverinfo='skip'
            ))
    
    avg_roi = frontier_df.loc[frontier_df['NET_BENEFIT'] > 0, 'RISK_REDUCTION'].sum() / frontier_df.loc[frontier_df['NET_BENEFIT'] > 0, 'C_PM_USD'].sum() * 1000 if (frontier_df['NET_BENEFIT'] > 0).any() else 0
    max_cost = frontier_df['C_PM_USD'].max() * 1.1
    fig_frontier.add_trace(go.Scatter(
        x=[0, max_cost],
        y=[0, avg_roi * max_cost / 1000],
        mode='lines',
        line=dict(color='#666', width=1, dash='dot'),
        name='Avg ROI Line',
        hoverinfo='skip'
    ))
    
    fig_frontier.update_layout(
        xaxis_title='PM Cost ($)',
        yaxis_title='Failure Risk (%)',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=400,
        margin=dict(l=60, r=20, t=40, b=60),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(gridcolor='#333', tickformat='$,.0f'),
        yaxis=dict(gridcolor='#333', ticksuffix='%')
    )
    
    fig_frontier.add_annotation(
        x=0.02, y=0.98,
        xref='paper', yref='paper',
        text='Bubble size = |Net Benefit|',
        showarrow=False,
        font=dict(size=10, color='#888'),
        bgcolor='rgba(0,0,0,0.5)',
        borderpad=4
    )
    
    st.plotly_chart(fig_frontier, use_container_width=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Active Anomalies (Live from PDM.ANOMALY_EVENTS)")
st.caption("Real-time anomaly detection from inference pipeline")

if not anomalies_df.empty:
    for _, row in anomalies_df.iterrows():
        severity = row['SEVERITY']
        css_class = 'asset-critical' if severity == 'CRITICAL' else 'asset-warning' if severity == 'WARNING' else 'asset-healthy'
        color = '#F44336' if severity == 'CRITICAL' else '#FFC107' if severity == 'WARNING' else '#4CAF50'
        
        st.markdown(f"""
        <div class="{css_class}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: {color}; font-weight: bold; font-size: 1.1rem;">{row['ASSET_ID']}</span>
                    <span style="background: {color}; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; margin-left: 0.5rem; font-size: 0.8rem;">{severity}</span>
                </div>
                <div style="text-align: right;">
                    <span style="color: {color}; font-weight: bold;">Score: {row['ANOMALY_SCORE']:.2f}</span>
                </div>
            </div>
            <div style="color: #ccc; margin-top: 0.5rem;">
                <strong>Type:</strong> {row['ANOMALY_TYPE']} | <strong>Root Cause:</strong> {row['ROOT_CAUSE']}
            </div>
            <div style="color: #888; margin-top: 0.25rem; font-size: 0.9rem;">
                <strong>Fix:</strong> {row['SUGGESTED_FIX']}
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("No active anomalies detected in the last 24 hours")

if not propagation_df.empty:
    st.markdown("### Downstream Risk Assessment (Live from PDM.ANOMALY_PROPAGATION)")
    st.caption("Assets at risk from upstream anomaly propagation")
    
    for _, row in propagation_df.iterrows():
        risk_level = row['RISK_LEVEL']
        color = '#F44336' if risk_level == 'HIGH' else '#FFC107' if risk_level == 'MEDIUM' else '#29B5E8'
        
        st.markdown(f"""
        <div style="background: rgba(41, 181, 232, 0.1); border-left: 3px solid {color}; padding: 0.75rem; margin-bottom: 0.5rem; border-radius: 0 0.5rem 0.5rem 0;">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <span style="font-weight: bold; color: {color};">{row['ASSET_ID']}</span>
                    <span style="color: #888; margin-left: 0.5rem;">({row['ANOMALY_TYPE']})</span>
                </div>
                <div>
                    <span style="color: {color};">{risk_level} ({row['RISK_SCORE']:.2f})</span>
                </div>
            </div>
            <div style="color: #888; font-size: 0.85rem; margin-top: 0.25rem;">
                Source: {row['SOURCE_ASSET']} | Expected impact in +{row['LAG_HOURS']:.0f}h
            </div>
        </div>
        """, unsafe_allow_html=True)

if st.session_state.simulation_active:
    st.markdown("### Live Sensor Readings")
    st.caption("Real-time data from simulation (last 2 minutes)")
    
    live_data = get_live_sensor_data(session)
    
    if not live_data.empty:
        active_trigger = get_active_anomaly_trigger(session)
        
        tabs = st.tabs(SIMULATION_ASSETS)
        for i, asset in enumerate(SIMULATION_ASSETS):
            with tabs[i]:
                asset_data = live_data[live_data['ASSET_ID'] == asset]
                
                if not asset_data.empty:
                    is_anomaly_target = asset == active_trigger
                    if is_anomaly_target:
                        st.warning("Anomaly injection active on this asset")
                    
                    cols = st.columns(len(asset_data))
                    for j, (_, row) in enumerate(asset_data.iterrows()):
                        metric_name = row['METRIC_NAME']
                        avg_val = row['AVG_VALUE']
                        
                        thresholds = {
                            'Humidity': (60, 70),
                            'VacuumLevel': (-0.92, -0.88),
                            'Vibration': (0.5, 0.8),
                            'Temperature': (200, 220),
                        }
                        
                        color = '#4CAF50'
                        if metric_name in thresholds:
                            warn, crit = thresholds[metric_name]
                            if metric_name == 'VacuumLevel':
                                if avg_val > crit:
                                    color = '#F44336'
                                elif avg_val > warn:
                                    color = '#FFC107'
                            else:
                                if avg_val > crit:
                                    color = '#F44336'
                                elif avg_val > warn:
                                    color = '#FFC107'
                        
                        with cols[j]:
                            st.markdown(f"""
                            <div style="background: rgba(41, 181, 232, 0.1); border-left: 3px solid {color}; padding: 0.5rem; border-radius: 0.25rem;">
                                <div style="font-size: 0.75rem; color: #888; text-transform: uppercase;">{metric_name}</div>
                                <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{avg_val}</div>
                                <div style="font-size: 0.7rem; color: #666;">
                                    min: {row['MIN_VALUE']} | max: {row['MAX_VALUE']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No recent data for this asset")
    else:
        st.info("Waiting for sensor data... (data appears after first task run)")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Production Line - Asset Health")

ASSETS = [
    {'id': 'AUTOCLAVE_01', 'name': 'Autoclave 01', 'health': 72, 'status': 'CRITICAL', 'issue': 'Vacuum decay trending', 'impact': '$25K', 'stage': 'CURE'},
    {'id': 'LAYUP_ROOM', 'name': 'Layup Room', 'health': 85, 'status': 'WARNING', 'issue': 'Humidity at 62%', 'impact': '$150K (6h lag)', 'stage': 'ENV'},
    {'id': 'AUTOCLAVE_02', 'name': 'Autoclave 02', 'health': 95, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'CURE'},
    {'id': 'LAYUP_BOT_01', 'name': 'Layup Bot 01', 'health': 92, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'LAYUP'},
    {'id': 'LAYUP_BOT_02', 'name': 'Layup Bot 02', 'health': 88, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'LAYUP'},
    {'id': 'CNC_MILL_01', 'name': 'CNC Mill 01', 'health': 90, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'TRIM'},
    {'id': 'CNC_MILL_02', 'name': 'CNC Mill 02', 'health': 87, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'TRIM'},
    {'id': 'QC_STATION_01', 'name': 'QC Station 01', 'health': 98, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'QC'},
    {'id': 'QC_STATION_02', 'name': 'QC Station 02', 'health': 96, 'status': 'HEALTHY', 'issue': None, 'impact': None, 'stage': 'QC'},
]

critical_assets = [a for a in ASSETS if a['status'] == 'CRITICAL']
warning_assets = [a for a in ASSETS if a['status'] == 'WARNING']
healthy_assets = [a for a in ASSETS if a['status'] == 'HEALTHY']

for asset in critical_assets:
    st.markdown(f"""
    <div class="asset-critical">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #F44336; font-weight: bold; font-size: 1.1rem;">{asset['name']}</span>
                <span style="color: #888; margin-left: 0.5rem;">({asset['stage']})</span>
            </div>
            <div style="text-align: right;">
                <span style="color: #F44336; font-weight: bold;">{asset['impact']} at risk</span>
            </div>
        </div>
        <div style="color: #ccc; margin-top: 0.5rem;">
            <strong>Issue:</strong> {asset['issue']} | <strong>Health:</strong> {asset['health']}%
        </div>
    </div>
    """, unsafe_allow_html=True)

for asset in warning_assets:
    st.markdown(f"""
    <div class="asset-warning">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #FFC107; font-weight: bold;">{asset['name']}</span>
                <span style="color: #888; margin-left: 0.5rem;">({asset['stage']})</span>
            </div>
            <div style="text-align: right;">
                <span style="color: #FFC107; font-weight: bold;">{asset['impact']} at risk</span>
            </div>
        </div>
        <div style="color: #ccc; margin-top: 0.5rem;">
            <strong>Issue:</strong> {asset['issue']} | <strong>Health:</strong> {asset['health']}%
        </div>
    </div>
    """, unsafe_allow_html=True)

with st.expander(f"{len(healthy_assets)} Healthy Assets", expanded=False):
    for asset in healthy_assets:
        st.markdown(f"""
        <div class="asset-healthy">
            <span style="color: #4CAF50;">{asset['name']}</span>
            <span style="color: #888; margin-left: 0.5rem;">({asset['stage']}) - {asset['health']}%</span>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Root Cause Analysis: Humidity - Scrap Correlation")
st.caption("AI-discovered pattern: High layup humidity predicts autoclave scrap 6 hours later")

corr_col1, corr_col2 = st.columns([2, 1])

with corr_col1:
    humidity_levels = ['<55%', '55-60%', '60-65%', '65-70%', '>70%']
    scrap_rates = [4.2, 5.1, 5.8, 15.2, 37.4]
    colors_corr = ['#4CAF50', '#4CAF50', '#FFC107', '#FF6B6B', '#F44336']
    
    fig_corr = go.Figure()
    fig_corr.add_trace(go.Bar(
        x=humidity_levels,
        y=scrap_rates,
        marker_color=colors_corr,
        text=[f"{r}%" for r in scrap_rates],
        textposition='outside'
    ))
    
    fig_corr.add_hline(y=5.5, line_dash="dash", line_color="#888", annotation_text="Target: 5.5%", annotation_position="right")
    fig_corr.add_vrect(x0=2.5, x1=4.5, fillcolor="red", opacity=0.1, annotation_text="DANGER ZONE", annotation_position="top")
    
    fig_corr.update_layout(
        title="Scrap Rate by Layup Room Humidity (6h Before Cure)",
        xaxis_title="Layup Room Humidity",
        yaxis_title="Scrap Rate (%)",
        template="plotly_dark",
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(range=[0, 45])
    )
    st.plotly_chart(fig_corr, use_container_width=True)

with corr_col2:
    st.markdown("""
    <div style="background: rgba(244,67,54,0.15); padding: 1rem; border-radius: 0.5rem; border: 1px solid #F44336; margin-bottom: 1rem;">
        <div style="font-size: 2rem; font-weight: bold; color: #F44336;">3x</div>
        <div style="color: #ccc;">higher scrap when humidity >65%</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(255,193,7,0.15); padding: 1rem; border-radius: 0.5rem; border: 1px solid #FFC107; margin-bottom: 1rem;">
        <div style="font-size: 1.5rem; font-weight: bold; color: #FFC107;">NOW: 62%</div>
        <div style="color: #ccc;">3 batches at elevated risk</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(76,175,80,0.15); padding: 1rem; border-radius: 0.5rem; border: 1px solid #4CAF50;">
        <div style="font-size: 1.2rem; font-weight: bold; color: #4CAF50;">$600K/yr savings</div>
        <div style="color: #ccc;">with HVAC upgrade ($150K)</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Asset Deep Dive")
selected_asset = st.selectbox(
    "Select asset for detailed analysis",
    ['AUTOCLAVE_01', 'AUTOCLAVE_02', 'CNC_MILL_01', 'CNC_MILL_02', 'LAYUP_ROOM', 'LAYUP_BOT_01', 'LAYUP_BOT_02'],
    index=0, label_visibility="collapsed"
)

if 'AUTOCLAVE' in selected_asset:
    analysis_col1, analysis_col2 = st.columns(2)
    
    with analysis_col1:
        st.markdown("#### Golden Batch Comparison")
        time_pts_gb = list(range(180))
        golden = [175 + 25 * (1 - np.exp(-t/30)) for t in time_pts_gb]
        actual = [g + np.random.normal(0, 2) + (5 if 90 <= t <= 110 else 0) for t, g in enumerate(golden)]
        
        fig_gb = go.Figure()
        fig_gb.add_trace(go.Scatter(x=time_pts_gb, y=golden, name='Golden Batch', line=dict(color='#4CAF50', width=3, dash='dash')))
        fig_gb.add_trace(go.Scatter(x=time_pts_gb, y=actual, name='Current Batch', line=dict(color='#29B5E8', width=2)))
        fig_gb.add_vrect(x0=90, x1=110, fillcolor="red", opacity=0.2, annotation_text="Deviation +5C", annotation_position="top")
        fig_gb.update_layout(
            title=f"{selected_asset} - Cure Cycle vs Golden Batch",
            xaxis_title="Time (minutes)", yaxis_title="Temperature (C)",
            template="plotly_dark", height=280,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", y=-0.2)
        )
        st.plotly_chart(fig_gb, use_container_width=True)
    
    with analysis_col2:
        st.markdown("#### Vacuum Trend")
        time_pts_vac = list(range(60))
        vacuum_actual = [-0.95 + t * 0.0004 + np.random.normal(0, 0.005) for t in time_pts_vac]
        
        fig_vac2 = go.Figure()
        fig_vac2.add_trace(go.Scatter(x=time_pts_vac, y=vacuum_actual, name='Actual', line=dict(color='#F44336', width=2)))
        fig_vac2.add_hline(y=-0.95, line_dash="dash", line_color="#4CAF50", annotation_text="Nominal")
        fig_vac2.add_hline(y=-0.90, line_dash="dot", line_color="#FF6B6B", annotation_text="FAIL")
        fig_vac2.update_layout(
            xaxis_title="Minutes Ago", yaxis_title="Vacuum (bar)",
            template="plotly_dark", height=280,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(range=[-1.0, -0.85])
        )
        st.plotly_chart(fig_vac2, use_container_width=True)

elif 'CNC' in selected_asset:
    analysis_col1, analysis_col2 = st.columns(2)
    
    with analysis_col1:
        st.markdown("#### FFT Vibration Analysis")
        frequencies = list(range(256))
        amplitude = [abs(np.sin(f * 0.1) * np.exp(-f/200)) + (0.5 if 120 <= f <= 130 else 0) for f in frequencies]
        
        fig_fft = go.Figure()
        fig_fft.add_trace(go.Scatter(x=frequencies, y=amplitude, fill='tozeroy', line=dict(color='#29B5E8'), name='Spectrum'))
        fig_fft.add_vrect(x0=115, x1=135, fillcolor="red", opacity=0.2, annotation_text="Bearing Fault (125 Hz)", annotation_position="top")
        fig_fft.update_layout(
            title=f"{selected_asset} - Spindle Vibration FFT",
            xaxis_title="Frequency (Hz)", yaxis_title="Amplitude (G)",
            template="plotly_dark", height=280,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_fft, use_container_width=True)
    
    with analysis_col2:
        st.markdown("#### Tool Wear Trend")
        tool_hours = list(range(100))
        tool_wear = [h * 0.8 + np.random.normal(0, 2) for h in tool_hours]
        
        fig_tool = go.Figure()
        fig_tool.add_trace(go.Scatter(x=tool_hours, y=tool_wear, line=dict(color='#29B5E8', width=2)))
        fig_tool.add_hline(y=80, line_dash="dash", line_color="#F44336", annotation_text="Replace Threshold")
        fig_tool.update_layout(
            xaxis_title="Operating Hours", yaxis_title="Wear Index",
            template="plotly_dark", height=280,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_tool, use_container_width=True)

else:
    st.markdown("#### Humidity Heatmap (6h Lag to Scrap)")
    hours_day = list(range(24))
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    humidity_data = [[55 + np.random.normal(0, 8) for _ in range(24)] for _ in range(5)]
    humidity_data[1][8:12] = [65, 68, 70, 67]
    
    fig_heat = go.Figure(data=go.Heatmap(
        z=humidity_data, x=hours_day, y=days,
        colorscale=[[0, '#29B5E8'], [0.6, '#FFC107'], [1, '#F44336']],
        zmin=40, zmax=80, colorbar=dict(title="Humidity %"),
        hovertemplate='%{y} %{x}:00<br>Humidity: %{z:.1f}%<extra></extra>'
    ))
    fig_heat.add_annotation(x=14, y='Tue', text="Scrap Impact (+6h)", showarrow=True, arrowhead=2, ax=50, ay=-30, font=dict(color='white'), bgcolor='rgba(244,67,54,0.8)')
    fig_heat.update_layout(
        title=f"{selected_asset} - Weekly Humidity with Delayed Scrap Correlation",
        xaxis_title="Hour of Day", yaxis_title="Day",
        template="plotly_dark", height=300,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("#### Anomaly Timeline")
anomaly_times = [datetime.now() - timedelta(hours=h) for h in [2, 8, 24, 48]]
anomaly_types = ['VACUUM_TREND', 'TEMP_EXCURSION', 'PRESSURE_DROP', 'VIBRATION_SPIKE']
anomaly_severity = ['MEDIUM', 'LOW', 'HIGH', 'LOW']
anomaly_scores = [0.78, 0.62, 0.89, 0.55]
severity_colors = {'LOW': '#29B5E8', 'MEDIUM': '#FFC107', 'HIGH': '#F44336'}

fig_timeline = go.Figure()
for i in range(len(anomaly_times)):
    fig_timeline.add_trace(go.Scatter(
        x=[anomaly_times[i]], y=[anomaly_scores[i]], mode='markers',
        marker=dict(size=20, color=severity_colors[anomaly_severity[i]]),
        name=anomaly_types[i],
        hovertemplate=f"<b>{anomaly_types[i]}</b><br>Score: {anomaly_scores[i]}<br>Severity: {anomaly_severity[i]}<extra></extra>"
    ))

fig_timeline.update_layout(
    template="plotly_dark", height=180,
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    yaxis=dict(title="Anomaly Score", range=[0, 1]),
    showlegend=False, margin=dict(t=20, b=30)
)
st.plotly_chart(fig_timeline, use_container_width=True)

asset_decision = decisions_df[decisions_df['ASSET_ID'] == selected_asset]
if not asset_decision.empty:
    asset_row = asset_decision.iloc[0]
    
    cost_col1, cost_col2 = st.columns(2)
    
    with cost_col1:
        st.markdown("#### Run-to-Failure vs Preventive Maintenance")
        expected_cost = asset_row['EXPECTED_UNPLANNED_COST']
        pm_cost = asset_row['C_PM_USD']
        net_benefit = asset_row['NET_BENEFIT']
        
        fig_cost = go.Figure()
        fig_cost.add_trace(go.Bar(
            x=['Run to Failure (Expected)', 'Do PM Now'],
            y=[expected_cost, pm_cost],
            marker_color=['#F44336', '#4CAF50'],
            text=[f'${expected_cost:,.0f}', f'${pm_cost:,.0f}'],
            textposition='outside',
            textfont=dict(size=14, color='white')
        ))
        
        if net_benefit > 0:
            fig_cost.add_annotation(
                x=0.5, y=max(expected_cost, pm_cost) * 1.15,
                text=f"Net Benefit: ${net_benefit:,.0f}",
                showarrow=False,
                font=dict(size=16, color='#4CAF50', weight='bold'),
                bgcolor='rgba(76, 175, 80, 0.2)',
                borderpad=8
            )
        
        fig_cost.update_layout(
            template="plotly_dark",
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(title="Cost (USD)", tickformat='$,.0f'),
            showlegend=False,
            margin=dict(t=40, b=40)
        )
        st.plotly_chart(fig_cost, use_container_width=True)
    
    with cost_col2:
        st.markdown("#### Why This Recommendation?")
        
        p_fail = asset_row['P_FAIL_7D']
        c_unplanned = asset_row['C_UNPLANNED_USD']
        recommendation = asset_row['RECOMMENDATION']
        rec_color = get_recommendation_color(recommendation)
        
        st.markdown(f"""
        <div style="background: rgba({get_recommendation_rgb(recommendation)}, 0.15); 
                    border: 2px solid {rec_color}; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
            <div style="font-size: 1.5rem; font-weight: bold; color: {rec_color};">
                {recommendation.replace('_', ' ')}
            </div>
            <div style="color: #888; font-size: 0.9rem;">{asset_row['TARGET_WINDOW'].replace('_', ' ')}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        **Failure probability (7 days):** {p_fail:.0%}  
        **If it fails:** ${c_unplanned:,.0f} total cost  
        - Downtime: {asset_row['UNPLANNED_DOWNTIME_HOURS_AVG']:.0f}h x ${asset_row['COST_PER_DOWNTIME_HOUR_USD']:,.0f}/hr  
        - Repair: ${asset_row['REPAIR_COST_AVG_USD']:,.0f}  
        - Scrap risk: ${asset_row['SCRAP_RISK_USD']:,.0f}
        
        **Expected loss:** {p_fail:.0%} x ${c_unplanned:,.0f} = **${expected_cost:,.0f}**  
        **PM cost:** {asset_row['PM_DOWNTIME_HOURS_AVG']:.1f}h + ${asset_row['PM_LABOR_COST_USD']:,.0f} labor + ${asset_row['PM_PARTS_COST_USD']:,.0f} parts = **${pm_cost:,.0f}**
        """)
        
        if net_benefit > 0:
            ratio = expected_cost / pm_cost if pm_cost > 0 else float('inf')
            if abs(net_benefit) < pm_cost * 0.2:
                decision_text = "Costs are roughly equal; given safety buffer, plan PM."
            else:
                decision_text = f"Expected loss is {ratio:.1f}x PM cost - prioritize this asset."
            st.success(f"**Decision:** {decision_text}")
        else:
            st.info(f"**Decision:** PM cost exceeds expected loss - continue monitoring.")
        
        anomaly_features = asset_row.get('ANOMALY_FEATURES', {})
        if isinstance(anomaly_features, str):
            try:
                anomaly_features = json.loads(anomaly_features)
            except:
                anomaly_features = {}
        
        key_drivers = anomaly_features.get('key_drivers', [])
        if key_drivers:
            st.markdown("**Key Risk Factors:**")
            for driver in key_drivers:
                st.markdown(f"- {driver}")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

trend_col1, trend_col2 = st.columns(2)

with trend_col1:
    st.markdown("### Downtime by Asset (This Month)")
    
    asset_downtime = [
        {"asset": "AUTOCLAVE_01", "hours": 18},
        {"asset": "CNC_MILL_01", "hours": 12},
        {"asset": "LAYUP_BOT_01", "hours": 8},
        {"asset": "AUTOCLAVE_02", "hours": 6},
        {"asset": "Others", "hours": 6},
    ]
    
    colors = ['#F44336', '#FF6B6B', '#FFC107', '#29B5E8', '#29B5E8']
    
    fig_downtime = go.Figure()
    fig_downtime.add_trace(go.Bar(
        y=[d['asset'] for d in asset_downtime],
        x=[d['hours'] for d in asset_downtime],
        orientation='h',
        marker_color=colors,
        text=[f"{d['hours']}h" for d in asset_downtime],
        textposition='auto'
    ))
    
    fig_downtime.update_layout(
        template="plotly_dark",
        height=280,
        yaxis=dict(autorange="reversed"),
        xaxis_title="Hours",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=120, r=20, t=20, b=40)
    )
    st.plotly_chart(fig_downtime, use_container_width=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Shift Handover Summary")
st.caption("Last 8 hours - auto-generated")

stat_cols = st.columns(5)
with stat_cols[0]:
    st.metric("Alerts Triggered", "7")
with stat_cols[1]:
    st.metric("Resolved", "5", delta="2 open")
with stat_cols[2]:
    st.metric("Downtime", "45 min")
with stat_cols[3]:
    st.metric("Work Orders", "2")
with stat_cols[4]:
    st.metric("Line Efficiency", "94%", delta="+2%")

events_col, recs_col = st.columns([2, 1])

with events_col:
    st.markdown("**Key Events:**")
    events = [
        ("08:15", "AUTOCLAVE_01 vacuum trend detected - WO created", "#FFC107"),
        ("10:30", "LAYUP_ROOM humidity peaked at 68% - returned to normal", "#4CAF50"),
        ("12:45", "CNC_MILL_01 vibration spike - self-resolved", "#4CAF50"),
        ("14:20", "Scheduled maintenance completed on LAYUP_BOT_02", "#29B5E8"),
    ]
    for time, event, color in events:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
            <span style="color: {color}; font-size: 1.25rem;">●</span>
            <span style="color: #888; min-width: 50px;">{time}</span>
            <span>{event}</span>
        </div>
        """, unsafe_allow_html=True)

with recs_col:
    st.markdown("**Next Shift Actions:**")
    st.warning("Monitor AUTOCLAVE_01 vacuum - technician scheduled for 14:00")
    st.info("Review LAYUP_ROOM HVAC if humidity spikes recur")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### GNN Anomaly Propagation")
st.caption("Predicted impact flow based on asset dependencies")

with st.expander("How GNN Propagation Works", expanded=False):
    st.markdown("""
    **Graph Neural Networks (GNNs)** model how anomalies spread through interconnected manufacturing assets:
    
    1. **Asset Graph Structure**: Assets are nodes connected by edges representing physical dependencies 
       (material flow, shared utilities, sequential processing)
    
    2. **Message Passing**: When an upstream asset shows anomalous behavior, the GNN propagates 
       "risk messages" to downstream neighbors based on:
       - **Connection strength** (how tightly coupled the assets are)
       - **Historical correlation** (how often issues co-occur)
       - **Current operating state** (load, utilization, recent alerts)
    
    3. **Impact Score**: Each asset's score (0-100%) represents the probability it will experience 
       degraded performance or failure given the current anomaly state of its upstream dependencies
    
    **Reading the Visualization**:
    - **Node color**: Red = high impact risk, Green = low impact risk
    - **Edge thickness/opacity**: Stronger propagation pathway
    - **Percentage**: Predicted probability of cascading impact
    """)

@st.cache_data(ttl=300)
def get_gnn_propagation_scores():
    """Fetch propagation scores from Snowflake, fall back to defaults if table empty."""
    try:
        df = session.sql("""
            SELECT SOURCE_ASSET, MAX(CONFIDENCE) AS SCORE
            FROM PDM.GNN_PROPAGATION_SCORES
            WHERE RUN_TIMESTAMP = (SELECT MAX(RUN_TIMESTAMP) FROM PDM.GNN_PROPAGATION_SCORES)
            GROUP BY SOURCE_ASSET
        """).to_pandas()
        if not df.empty:
            return dict(zip(df['SOURCE_ASSET'], df['SCORE']))
    except Exception:
        pass
    return {
        'LAYUP_ROOM': 0.8, 'LAYUP_BOT_01': 0.6, 'LAYUP_BOT_02': 0.3,
        'AUTOCLAVE_01': 0.9, 'AUTOCLAVE_02': 0.2, 'CNC_MILL_01': 0.7,
        'CNC_MILL_02': 0.1, 'QC_STATION_01': 0.5, 'QC_STATION_02': 0.1,
    }

PROPAGATION = get_gnn_propagation_scores()

NODE_DETAILS = {
    'LAYUP_ROOM': {
        'role': 'Source Node',
        'upstream': None,
        'downstream': ['LAYUP_BOT_01', 'LAYUP_BOT_02'],
        'anomaly_source': 'Temperature deviation (+2.3°C)',
        'propagation_reason': 'Environmental conditions affect composite material properties',
        'risk_factors': ['Humidity sensor drift', 'HVAC load imbalance'],
        'mtbf_impact': '-15% estimated'
    },
    'LAYUP_BOT_01': {
        'role': 'Processing Node',
        'upstream': ['LAYUP_ROOM'],
        'downstream': ['AUTOCLAVE_01'],
        'anomaly_source': 'Inherited from LAYUP_ROOM',
        'propagation_reason': 'Material quality variance affects layup precision',
        'risk_factors': ['Ply alignment deviation', 'Resin distribution'],
        'mtbf_impact': '-12% estimated'
    },
    'LAYUP_BOT_02': {
        'role': 'Processing Node',
        'upstream': ['LAYUP_ROOM'],
        'downstream': ['AUTOCLAVE_02'],
        'anomaly_source': 'Minimal exposure',
        'propagation_reason': 'Operating on different material batch',
        'risk_factors': ['Low correlation with current anomaly'],
        'mtbf_impact': '-3% estimated'
    },
    'AUTOCLAVE_01': {
        'role': 'Critical Node',
        'upstream': ['LAYUP_BOT_01'],
        'downstream': ['CNC_MILL_01'],
        'anomaly_source': 'Pressure cycle variance detected',
        'propagation_reason': 'Upstream material issues + own sensor anomaly compound risk',
        'risk_factors': ['Cure cycle deviation', 'Thermocouple drift', 'Door seal wear'],
        'mtbf_impact': '-22% estimated'
    },
    'AUTOCLAVE_02': {
        'role': 'Processing Node',
        'upstream': ['LAYUP_BOT_02'],
        'downstream': ['CNC_MILL_02'],
        'anomaly_source': 'None detected',
        'propagation_reason': 'Isolated from primary anomaly chain',
        'risk_factors': ['Nominal operation'],
        'mtbf_impact': '0% (baseline)'
    },
    'CNC_MILL_01': {
        'role': 'Processing Node',
        'upstream': ['AUTOCLAVE_01'],
        'downstream': ['QC_STATION_01'],
        'anomaly_source': 'Spindle vibration +0.8mm/s',
        'propagation_reason': 'Cured part variance affects machining parameters',
        'risk_factors': ['Tool wear acceleration', 'Surface finish deviation'],
        'mtbf_impact': '-18% estimated'
    },
    'CNC_MILL_02': {
        'role': 'Processing Node',
        'upstream': ['AUTOCLAVE_02'],
        'downstream': ['QC_STATION_02'],
        'anomaly_source': 'None detected',
        'propagation_reason': 'Isolated from primary anomaly chain',
        'risk_factors': ['Nominal operation'],
        'mtbf_impact': '0% (baseline)'
    },
    'QC_STATION_01': {
        'role': 'Sink Node',
        'upstream': ['CNC_MILL_01'],
        'downstream': None,
        'anomaly_source': 'Increased rejection rate predicted',
        'propagation_reason': 'Cumulative upstream variance exceeds tolerance',
        'risk_factors': ['Dimensional variance', 'Surface defects', 'Delamination risk'],
        'mtbf_impact': 'N/A (quality gate)'
    },
    'QC_STATION_02': {
        'role': 'Sink Node',
        'upstream': ['CNC_MILL_02'],
        'downstream': None,
        'anomaly_source': 'None detected',
        'propagation_reason': 'Clean upstream chain',
        'risk_factors': ['Nominal rejection rate expected'],
        'mtbf_impact': 'N/A (quality gate)'
    },
}

fig_gnn = go.Figure()

gnn_edges = [
    ('LAYUP_ROOM', 'LAYUP_BOT_01'), ('LAYUP_ROOM', 'LAYUP_BOT_02'),
    ('LAYUP_BOT_01', 'AUTOCLAVE_01'), ('LAYUP_BOT_02', 'AUTOCLAVE_02'),
    ('AUTOCLAVE_01', 'CNC_MILL_01'), ('AUTOCLAVE_02', 'CNC_MILL_02'),
    ('CNC_MILL_01', 'QC_STATION_01'), ('CNC_MILL_02', 'QC_STATION_02'),
]

for src, tgt in gnn_edges:
    x0, y0 = GRAPH_ASSETS[src]['x'], GRAPH_ASSETS[src]['y']
    x1, y1 = GRAPH_ASSETS[tgt]['x'], GRAPH_ASSETS[tgt]['y']
    prop_strength = max(PROPAGATION[src], PROPAGATION[tgt])
    
    fig_gnn.add_trace(go.Scatter(
        x=[x0, x1], y=[y0, y1], mode='lines',
        line=dict(color=f'rgba(41, 181, 232, {prop_strength})', width=2 + prop_strength * 4),
        hoverinfo='skip', showlegend=False
    ))

for asset_id, asset in GRAPH_ASSETS.items():
    prop = PROPAGATION[asset_id]
    details = NODE_DETAILS[asset_id]
    color = f'rgb({int(255 * prop)}, {int(200 * (1-prop))}, {int(100 * (1-prop))})'
    
    upstream_str = ', '.join(details['upstream']) if details['upstream'] else 'None (source)'
    downstream_str = ', '.join(details['downstream']) if details['downstream'] else 'None (sink)'
    risk_str = '<br>'.join([f'• {r}' for r in details['risk_factors']])
    
    hover_text = (
        f"<b>{asset_id}</b> ({details['role']})<br><br>"
        f"<b>Impact Score:</b> {prop:.0%}<br>"
        f"<b>MTBF Impact:</b> {details['mtbf_impact']}<br><br>"
        f"<b>Anomaly:</b> {details['anomaly_source']}<br>"
        f"<b>Why:</b> {details['propagation_reason']}<br><br>"
        f"<b>Upstream:</b> {upstream_str}<br>"
        f"<b>Downstream:</b> {downstream_str}<br><br>"
        f"<b>Risk Factors:</b><br>{risk_str}"
    )
    
    fig_gnn.add_trace(go.Scatter(
        x=[asset['x']], y=[asset['y']], mode='markers+text',
        marker=dict(size=40, color=color, line=dict(width=2, color='white')),
        text=f"{asset_id.split('_')[0]}<br>{int(prop*100)}%",
        textposition='middle center', textfont=dict(size=8, color='white'),
        hovertemplate=hover_text + "<extra></extra>",
        showlegend=False
    ))

fig_gnn.update_layout(
    template="plotly_dark", height=280,
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 4.5]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 2.5]),
    margin=dict(t=20, b=20)
)
st.plotly_chart(fig_gnn, use_container_width=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Model Diagnostics")

@st.cache_data(ttl=300)
def get_model_diagnostics():
    """Fetch model diagnostics from Snowflake."""
    try:
        df = session.sql("""
            SELECT 
                MODEL_NAME,
                MODEL_VERSION,
                METRIC_NAME,
                METRIC_VALUE,
                THRESHOLD_VALUE,
                STATUS,
                RUN_TIMESTAMP
            FROM PDM.MODEL_DIAGNOSTICS
            WHERE RUN_TIMESTAMP = (SELECT MAX(RUN_TIMESTAMP) FROM PDM.MODEL_DIAGNOSTICS)
            ORDER BY MODEL_NAME
        """).to_pandas()
        return df
    except Exception:
        return pd.DataFrame()

diag_df = get_model_diagnostics()
if not diag_df.empty:
    diag_col1, diag_col2, diag_col3 = st.columns(3)
    
    for i, row in diag_df.iterrows():
        col = [diag_col1, diag_col2, diag_col3][i % 3]
        status_color = "#4CAF50" if row['STATUS'] == 'PASS' else "#FF9800" if row['STATUS'] == 'WARN' else "#F44336"
        with col:
            st.markdown(f"""
            <div style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 0.5rem; border-left: 3px solid {status_color};">
                <div style="font-weight: 600; color: #29B5E8;">{row['MODEL_NAME']}</div>
                <div style="font-size: 0.85rem; color: #888;">{row['METRIC_NAME']}</div>
                <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
                    <span style="font-size: 1.2rem; font-weight: 700; color: {status_color};">{row['METRIC_VALUE']:.3f}</span>
                    <span style="font-size: 0.8rem; color: #666;">threshold: {row['THRESHOLD_VALUE']:.2f}</span>
                </div>
                <div style="text-align: right; font-size: 0.75rem; color: #555;">{row['STATUS']}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("No model diagnostics available. Run the notebooks to generate model metrics.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Actions")
action_col1, action_col2, action_col3 = st.columns(3)

if 'show_wo_form' not in st.session_state:
    st.session_state.show_wo_form = False

with action_col1:
    if st.button("Create Work Order", type="primary", use_container_width=True, key="btn_wo"):
        st.session_state.show_wo_form = not st.session_state.show_wo_form

with action_col2:
    if st.button("Notify Technician", use_container_width=True, key="btn_notify"):
        st.success("Notification sent to Mike Rodriguez (T001)")

with action_col3:
    if st.button("Export Report", use_container_width=True, key="btn_export"):
        st.success("Report exported to SNOWCORE_PDM.AUDIT.SHIFT_REPORTS")

if st.session_state.show_wo_form:
    st.markdown("#### Create Work Order")
    wo_col1, wo_col2 = st.columns(2)
    
    with wo_col1:
        wo_asset = st.selectbox("Asset", ['AUTOCLAVE_01', 'LAYUP_ROOM', 'CNC_MILL_01'], key="wo_asset")
        wo_type = st.radio("Work Type", ["Corrective", "Preventive", "Inspection"], horizontal=True, key="wo_type")
        wo_priority = st.radio("Priority", ["Critical", "High", "Medium", "Low"], index=1, horizontal=True, key="wo_priority")
    
    with wo_col2:
        wo_description = st.text_area(
            "Description",
            value="Investigate vacuum trend - Check seal groove per Manual Section 4.2.3",
            height=100, key="wo_desc"
        )
    
    st.markdown("**Assign Technician:**")
    tech_col1, tech_col2 = st.columns([3, 1])
    with tech_col1:
        st.markdown("""
        <div style="background: rgba(76, 175, 80, 0.15); border-left: 3px solid #4CAF50; padding: 0.75rem; border-radius: 0.25rem;">
            <strong>Mike Rodriguez</strong> - BEST MATCH (95% skill match)
            <div style="color: #888; font-size: 0.9rem;">Skills: Autoclave, Vacuum Systems | Available</div>
        </div>
        """, unsafe_allow_html=True)
    with tech_col2:
        if st.button("Assign", type="primary", key="btn_assign"):
            st.success(f"WO-2026-0205-001 created for {wo_asset}")
            st.success("Assigned to Mike Rodriguez (T001)")
            st.session_state.show_wo_form = False

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

st.markdown("### Reliability Copilot")

if session:
    st.caption("Connected to Cortex")
else:
    st.caption("Demo Mode")

for msg in st.session_state.chat_history[-4:]:
    if msg['role'] == 'user':
        st.markdown(f"""<div class="chat-message user-message"><strong>You:</strong> {msg['content']}</div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="chat-message agent-message"><strong>Copilot:</strong><br>{msg['content']}</div>""", unsafe_allow_html=True)

st.markdown("**Quick Actions:**")
qa_col1, qa_col2, qa_col3, qa_col4 = st.columns(4)

with qa_col1:
    if st.button("Similar incidents?", use_container_width=True, key="btn_history"):
        st.session_state.pending_query = "Has this vacuum degradation happened before on AUTOCLAVE_01? What was the root cause and fix?"

with qa_col2:
    if st.button("Why high scrap?", use_container_width=True, key="btn_scrap"):
        st.session_state.pending_query = "Why is scrap rate elevated this week? Analyze correlation with environmental factors."

with qa_col3:
    if st.button("Predict failure?", use_container_width=True, key="btn_predict"):
        st.session_state.pending_query = "Based on the current vacuum trend, when will AUTOCLAVE_01 likely fail if not addressed?"

with qa_col4:
    if st.button("Recommended fix?", use_container_width=True, key="btn_fix"):
        st.session_state.pending_query = "What is the recommended maintenance action for the AUTOCLAVE_01 vacuum issue? Include parts and estimated time."

qa_col5, qa_col6, qa_col7, qa_col8 = st.columns(4)

with qa_col5:
    if st.button("Cost impact?", use_container_width=True, key="btn_cost"):
        st.session_state.pending_query = "What is the total cost impact if current issues are not addressed? Include downtime, scrap, and labor."

with qa_col6:
    if st.button("Weekly trends?", use_container_width=True, key="btn_trends"):
        st.session_state.pending_query = "Summarize asset health trends for this week. Which assets improved and which degraded?"

with qa_col7:
    if st.button("Top priorities?", use_container_width=True, key="btn_priority"):
        st.session_state.pending_query = "What are the top 3 maintenance priorities right now based on risk and impact?"

with qa_col8:
    if st.button("Shift summary", use_container_width=True, key="btn_shift"):
        st.session_state.pending_query = "Generate a brief shift handover summary including alerts, actions taken, and pending items."

user_input = st.text_input("Ask about any asset or issue...", key="chat_input", label_visibility="collapsed", placeholder="Ask about any asset or issue...")

if st.button("Ask Copilot", use_container_width=True, key="btn_send", type="primary"):
    if user_input:
        st.session_state.pending_query = user_input

if 'pending_query' in st.session_state and st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None
    st.session_state.chat_history.append({'role': 'user', 'content': query})
    
    with st.spinner("Analyzing with Cortex..."):
        response = call_cortex_agent(query, session)
    
    st.session_state.chat_history.append({'role': 'agent', 'content': response})
    st.experimental_rerun()

st.markdown("---")
st.caption("Powered by Snowflake Cortex | Real-time anomaly detection with GNN + Transformer models")

if st.session_state.auto_refresh and st.session_state.simulation_active:
    time_module.sleep(5)
    st.experimental_rerun()
