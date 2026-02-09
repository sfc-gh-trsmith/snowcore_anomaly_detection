# Demo Requirements Document (DRD): Snowcore Anomaly Detection

GITHUB REPO NAME: `snowcore_anomaly_detection`
GITHUB REPO DESCRIPTION: End-to-end predictive maintenance pipeline for the "Avalanche X1" production line using Cortex Agents to correlate telemetry with unstructured CMMS logs and manuals.

## 1. Strategic Overview

* **Problem Statement:** Snowcore Industries faces intermittent quality yield issues on the high-performance "Avalanche X1" Bobsled line. While sensor alerts exist, they lack context; operators cannot quickly determine if a pressure drop is a novel failure or a recurring issue documented in historical maintenance logs. This disconnect leads to unnecessary cycle aborts and extended downtime.

* **Target Business Goals (KPIs):**

| Metric Category | Operational Metric | Financial Metric | Target Improvement |
|----------------|-------------------|------------------|-------------------|
| **Uptime** | Unplanned Downtime Hours | Revenue Opportunity Cost ($) | ↓40% |
| **Quality** | First Pass Yield (FPY) % | Cost of Goods Sold (COGS) | ↓10% |
| **Maintenance** | Overtime Hours % | Labor Cost Variance ($) | ↓50% |
| **Inventory** | Spare Parts Stockout Rate | Working Capital (Inventory) ($) | ↓15% |
| **Asset Life** | Mean Time Between Failures (MTBF) | Return on Assets (ROA) % | ↑12% |

* **The "Wow" Moment:** An anomaly triggers on `Autoclave_02`. The user asks the Cortex Agent, "Has this happened before?" The Agent searches 5 years of unstructured CMMS logs to find a similar incident from 2022, summarizes the resolution ("Replaced Vacuum Seal B"), and pulls the exact replacement procedure from the PDF Maintenance Manual side-by-side.

### Hidden Discovery Moment

The most compelling insight is NOT obvious from raw data:

| Element | Description |
|---------|-------------|
| **Surface Appearance** | Layup Room humidity readings above 65% appear within normal operating range. No alarms trigger. Operators see green status. |
| **Revealed Reality** | 6 hours later during autoclave cure cycle, parts with high-humidity layup show **3x higher scrap rates** due to moisture-induced delamination. |
| **Business Impact** | $50K+ per batch in scrap costs. Root cause invisible without cross-process time-lagged correlation. |
| **Demo Trigger** | When user investigates "Why is scrap high this week?", the system reveals the humidity correlation automatically. |

## 2. User Personas & Stories

### Persona Matrix

| Persona Level | Role Title | Key User Story (Demo Flow) | Entry Point |
|---------------|-----------|---------------------------|-------------|
| **Strategic** | **Plant Manager** | "As a Manager, I want to see the correlation between 'Layup Room Humidity' and 'Autoclave Scrap Rates' to justify HVAC upgrades." | Financial Dashboard (Primary) |
| **Operational** | **Line Operator** | "As an Operator, I want to monitor `Layup_Bot`, `Autoclave_01`, and `CNC_Mill` simultaneously and receive a single, prioritized alert list." | Line Overview (Subway Map) |
| **Technical** | **Maintenance Lead** | "As a Technician, I want to search through thousands of unstructured shift notes and PDF manuals instantly to find how to calibrate the 'Spindle Vibration' sensor." | Investigation Deck (Agent Chat) |

### STAR Journey: Plant Manager

| STAR Element | Implementation |
|--------------|----------------|
| **Situation** | KPI cards showing current downtime cost ($1.25M/mo), scrap rate (5%), maintenance overtime (200 hrs) |
| **Task** | Header: "Identify root causes of Q4 yield decline" |
| **Action** | Filters for date range, asset type; drill-down buttons; "Ask Agent" natural language input |
| **Result** | Before/After comparison showing projected $625K monthly savings with anomaly detection enabled |

### Self-Guided UX Requirements

This demo must appear production-ready, NOT demo-looking:
- No explicit "demo mode" or walkthrough toggles
- Graceful contextual guidance embedded in well-designed UI
- Tooltips on hover for complex metrics
- Progressive disclosure (summary → detail on click)
- Callout badges for "AI-generated" insights

## 3. Data Architecture & Snowpark ML (Backend)

### Structured Data (Schemas)

| Layer | Table | Description | Grain |
|-------|-------|-------------|-------|
| RAW | `RAW.IOT_STREAMING` | Landing table for Sparkplug B JSON payloads | 1 message per row |
| ATOMIC | `ATOMIC.ASSET_SENSORS` | Normalized, time-aligned sensor readings | 1 metric per asset per timestamp |
| ATOMIC | `ATOMIC.ASSET_SENSORS_WIDE` | Pivoted sensor readings | 1 row per asset per timestamp |
| PDM | `PDM.FEATURE_STORE` | Rolling windows, lags, drift metrics | 1 feature vector per asset per window |
| PDM | `PDM.ANOMALY_EVENTS` | Detected anomalies with severity and root cause | 1 event per anomaly |
| DATA_MART | `DATA_MART.FINANCIAL_SUMMARY` | Aggregated cost metrics | 1 row per month |

### Unified Namespace (UNS) / Sparkplug B Architecture

Topic structure:
```
spBv1.0/{group_id}/{message_type}/{edge_node_id}/{device_id}
spBv1.0/SNOWCORE/DDATA/LINE_01/AUTOCLAVE_01
```

Vendor-agnostic approach: All OT systems (Rockwell, Siemens, Honeywell, OSIsoft) mapped to Sparkplug B via generic "Industrial Gateway" references.

### Unstructured Data (Tribal Knowledge)

| Source | Type | Indexing Strategy |
|--------|------|-------------------|
| OEM Maintenance Manuals | PDF | By `Asset_Model`, `Component_Section` |
| CMMS Logs (Work Orders, Shift Handovers) | Text/JSON | By `Error_Code`, `Natural_Language_Description` |

### ML Notebook Specification

| Component | Specification |
|-----------|---------------|
| **Objective** | Multi-Asset Anomaly Detection (Sequential Logic) |
| **Target Variable** | `Process_Health_Score` (Composite metric) |
| **Model A (Layup)** | Linear Regression (Tension vs. Humidity) |
| **Model B (Autoclave)** | Autoencoder (Reconstruction Error of Cure Cycle) |
| **Model C (Cross-Asset)** | Graph Neural Network for dependency propagation |
| **Inference Output** | Writes to `PDM.ANOMALY_EVENTS` |

### GNN Cross-Asset Correlation

Reference implementation: `/Users/trsmith/Desktop/dev/mfg/gnn_process_traceability/`

Graph structure:
```
LAYUP_ROOM (ENV) ──────────────────────────────────────────→
       │
LAYUP_BOT_01 → AUTOCLAVE_01 → CNC_MILL_01 → QC_STATION_01
LAYUP_BOT_02 → AUTOCLAVE_02 → CNC_MILL_02 → QC_STATION_02
```

Purpose: Propagate anomaly signals across asset dependency graph to predict downstream failures before they occur.

## 4. Cortex Intelligence Specifications

### Cortex Analyst (Structured Data / SQL)

* **Semantic Model Scope:**

| Type | Fields |
|------|--------|
| **Measures** | `Downtime_Minutes`, `Scrap_Count`, `Maintenance_Cost_YTD`, `Downtime_Cost_USD`, `OEE_Pct` |
| **Dimensions** | `Asset_ID`, `Failure_Code`, `Technician_ID`, `Shift`, `Product_Line` |

* **Golden Query (Verification):**
  * *User Prompt:* "Which asset had the highest downtime due to 'Vacuum Leak' last quarter?"
  * *Expected SQL:* `SELECT Asset_ID, SUM(Downtime_Minutes) FROM ATOMIC.MAINTENANCE_LOGS WHERE Failure_Reason = 'Vacuum Leak' GROUP BY Asset_ID ORDER BY 2 DESC`

### Cortex Search (Unstructured Data / RAG)

* **Service Name:** `PDM.KNOWLEDGE_BASE_SEARCH`
* **Indexing Strategy:**

| Collection | Content | Index Fields |
|------------|---------|--------------|
| Manuals | OEM PDFs, SOPs, calibration guides | `Asset_Model`, `Component_Section` |
| CMMS Logs | Work orders, shift handovers, technician notes | `Error_Code`, `Natural_Language_Description` |

* **Sample RAG Prompt:** "Find me all maintenance logs from 2023 related to 'pressure drop' on Autoclave 2 and summarize the fix."

### Cortex Agents (Orchestration)

* **Agent Name:** "Reliability Copilot"
* **Autonomy Model:** Configurable (Reactive → Proactive → Automated)

| Level | Behavior | Use Case |
|-------|----------|----------|
| **Reactive** | Responds only to explicit queries | New users, audit environments |
| **Proactive** | Surfaces suggestions, requires approval | Standard operations |
| **Automated** | Executes trusted playbooks automatically | Mature environments, night shifts |

* **Proactive Trigger:** When anomaly detected in `PDM.ANOMALY_EVENTS`, Agent queries `PDM.KNOWLEDGE_BASE_SEARCH` to attach "Suggested Fix" before operator sees alert.

## 5. Streamlit Application UX/UI

### Layout Strategy

| Page | Purpose | Primary Persona |
|------|---------|-----------------|
| **Page 1: Financial Dashboard** | ROI metrics, before/after comparison | Plant Manager |
| **Page 2: Line Overview** | "Subway Map" of production flow, real-time status | Line Operator |
| **Page 3: Investigation Deck** | Asset detail + Agent chat | Maintenance Lead |

### Page 1: Financial Dashboard (Strategic Entry Point)

```
┌─────────────────────────────────────────────────────────────┐
│  SNOWCORE INDUSTRIES - Reliability Intelligence Dashboard   │
├─────────────────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│ │ DOWNTIME  │ │   COPQ    │ │ MAINT EFF │ │    OEE    │    │
│ │  -$500K   │ │  -$50K    │ │  -$75K    │ │   +12%    │    │
│ │   ▼40%    │ │   ▼10%    │ │   ▼50%    │ │   ▲12%    │    │
│ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐ ┌─────────────────────────────┐│
│ │   TOTAL VALUE CREATED   │ │    BEFORE / AFTER TRENDS    ││
│ │      $6.7M / YEAR       │ │    [Line Chart]             ││
│ └─────────────────────────┘ └─────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Page 2: Line Overview

* "Subway Map" visualization: `Layup` → `Cure` → `Trim`
* Assets color-coded: Green (healthy) → Yellow (warning) → Red (critical)
* Click asset → navigate to Investigation Deck

### Page 3: Investigation Deck

| Panel | Content |
|-------|---------|
| **Left** | Live Sensor Chart (Altair), anomaly timeline |
| **Right** | Cortex Agent Chat (RAG over Manuals + Logs) |
| **Bottom** | Asset dependency graph (GNN visualization) |

### Component Logic

| Asset | Visualization |
|-------|---------------|
| CNC Spindle | FFT Frequency chart (vibration analysis) |
| Autoclave | "Golden Batch" overlay chart |
| Layup Room | Humidity heatmap with 6-hour lag indicator |

### Interaction

* **Alert Mode:** UI-only (no external integrations)
* **Work Order:** "Create Work Order" button takes Agent summary and displays confirmation (mocked)
* **Agent Toggle:** Slider to switch autonomy level (Reactive/Proactive/Automated)

## 6. Competitive Positioning

### Core Narrative: "Stop Moving the Data"

| Competitor | Their Approach | Snowflake Advantage |
|------------|----------------|---------------------|
| **AWS/Azure/GCP** | Lambda Architecture: 7+ services (IoT Hub → Kinesis → S3 → Glue → Redshift → SageMaker) | Kappa Architecture: Ingest once, everything runs on same data |
| **C3.ai / Palantir** | Black box ontology, vendor lock-in | Glass box (Python/SQL), you own the IP |
| **OSIsoft PI / Seeq** | OT island, no business context | Context Engine: OT meets IT (sensors + ERP) |

### Demo Narrative Arc

1. **Act 1 (Speed):** Show Snowpipe Streaming landing data in < 1 second
2. **Act 2 (Convergence):** Join OT sensors to ERP maintenance schedule in single query
3. **Act 3 (AI):** Run anomaly detection + RAG in SQL without exporting data

### CFO Hook

> "Competitors charge for storage, then compute to move it, then compute to train, then compute to host the API. In Snowflake, you eliminate the 'Data Movement Tax.' For a plant this size, that's $2-3M in infrastructure savings before operational improvements."

## 7. Industry Extensibility

This demo pattern applies to:

| Industry | "Autoclave" Equivalent | Primary Sensors | Strategic Value |
|----------|------------------------|-----------------|-----------------|
| **Semiconductor** | Etch/CVD Chamber | Gas Flow, RF Power, Wafer Temp | Yield Optimization |
| **Aerospace** | Large-Scale Autoclave | Heat, Vacuum, Resin Flow | Safety & Certification |
| **HVAC** | Centrifugal Chiller | Refrigerant Pressure, Vibration | Energy Efficiency |
| **Heavy Equipment** | Engine/Drivetrain | Oil Pressure, Vibration, Load | Uptime (PdM) |

Position as "Industrial Reasoning Engine" - not just storing or seeing data, but reasoning over it to make financial decisions.

## 8. Success Criteria

| Type | Criterion |
|------|-----------|
| **Technical** | Cortex Search retrieves and blends PDF manual + text log in single answer |
| **Technical** | GNN propagates anomaly signal from Layup Room to Autoclave prediction |
| **Technical** | Agent autonomy toggle switches behavior without code changes |
| **Business** | Demo reveals humidity→scrap correlation (Hidden Discovery) |
| **Business** | Solution distinguishes "known issue" vs. "new issue" automatically |
| **Business** | Financial dashboard shows credible ROI calculation |

## 9. Implementation References

Detailed implementation notes available in `scratch/implementation_notes/`:

| File | Topic |
|------|-------|
| `01_hidden_discovery.md` | Data engineering for humidity-scrap correlation |
| `02_gnn_cross_asset.md` | Graph Neural Network architecture |
| `03_financial_metrics.md` | CFO dashboard specifications |
| `04_competitive_positioning.md` | Sales narrative and competitor kill sheet |
| `05_uns_sparkplug_b.md` | Unified Namespace / Sparkplug B architecture |
| `06_agent_autonomy.md` | Configurable autonomy implementation |
| `07_industry_extensibility.md` | Vertical market translations |
