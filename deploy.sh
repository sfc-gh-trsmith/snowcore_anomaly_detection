#!/bin/bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

CONNECTION="demo"
DATABASE="SNOWCORE_PDM"
SNOWFLAKE_WAREHOUSE="${SNOWFLAKE_WAREHOUSE:-COMPUTE_WH}"
SNOWFLAKE_ROLE="${SNOWFLAKE_ROLE:-ACCOUNTADMIN}"
ONLY_COMPONENT=""

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error_exit() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

check_snow_cli() {
    if ! command -v snow &> /dev/null; then
        error_exit "Snowflake CLI (snow) not found. Install with: pip install snowflake-cli-labs"
    fi
}

should_run_step() {
    local step_name="$1"
    [ -z "$ONLY_COMPONENT" ] && return 0
    case "$ONLY_COMPONENT" in
        ddl) [[ "$step_name" == "ddl" ]] ;;
        data) [[ "$step_name" == "data" ]] ;;
        cortex) [[ "$step_name" =~ ^cortex ]] ;;
        streamlit) [[ "$step_name" == "streamlit" ]] ;;
        notebooks) [[ "$step_name" == "notebooks" ]] ;;
        *) return 1 ;;
    esac
}

snow_sql() {
    if [[ -n "$CONNECTION" ]]; then
        snow sql -c "$CONNECTION" "$@"
    else
        snow sql "$@"
    fi
}

snow_stage_create() {
    if [[ -n "$CONNECTION" ]]; then
        snow stage create -c "$CONNECTION" "$@"
    else
        snow stage create "$@"
    fi
}

snow_stage_copy() {
    if [[ -n "$CONNECTION" ]]; then
        snow stage copy -c "$CONNECTION" "$@"
    else
        snow stage copy "$@"
    fi
}

snow_streamlit_deploy() {
    if [[ -n "$CONNECTION" ]]; then
        snow streamlit deploy -c "$CONNECTION" "$@"
    else
        snow streamlit deploy "$@"
    fi
}

run_sql_file() {
    local file="$1"
    local description="$2"
    log "Executing: $description"
    snow_sql -f "$file" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
}

deploy_ddl() {
    log "=== Deploying DDL ==="
    run_sql_file "$PROJECT_ROOT/sql/01_ddl.sql" "Database schemas and tables"
}

deploy_cortex_search() {
    log "=== Deploying Cortex Search ==="
    run_sql_file "$PROJECT_ROOT/sql/02_cortex_search.sql" "Cortex Search service"
}

deploy_semantic_model() {
    log "=== Deploying Semantic Model ==="
    snow_stage_create @SNOWCORE_PDM.PDM.MODELS || true
    snow_stage_copy "$PROJECT_ROOT/cortex/semantic_model.yaml" @SNOWCORE_PDM.PDM.MODELS/
    log "Semantic model uploaded to stage"
}

deploy_semantic_view() {
    log "=== Deploying Semantic View ==="
    run_sql_file "$PROJECT_ROOT/sql/04_semantic_view.sql" "Semantic View for Cortex Analyst"
}

deploy_cortex_agent() {
    log "=== Deploying Cortex Agent ==="
    run_sql_file "$PROJECT_ROOT/sql/05_cortex_agent.sql" "Reliability Copilot Agent"
}

deploy_streaming_simulation() {
    log "=== Deploying Streaming Simulation ==="
    run_sql_file "$PROJECT_ROOT/sql/06_streaming_simulation.sql" "Live sensor simulation infrastructure"
}

deploy_external_access() {
    log "=== Deploying External Access Integration ==="
    snow_sql -q "
    CREATE OR REPLACE NETWORK RULE SNOWCORE_PDM.PDM.PYPI_NETWORK_RULE
        MODE = EGRESS
        TYPE = HOST_PORT
        VALUE_LIST = (
            'pypi.org:443',
            'files.pythonhosted.org:443',
            'download.pytorch.org:443',
            'data.pyg.org:443'
        );
    
    CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION SNOWCORE_PDM_PYPI_ACCESS
        ALLOWED_NETWORK_RULES = (SNOWCORE_PDM.PDM.PYPI_NETWORK_RULE)
        ENABLED = TRUE;
    
    GRANT USAGE ON INTEGRATION SNOWCORE_PDM_PYPI_ACCESS TO ROLE $SNOWFLAKE_ROLE;
    " --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
    log "External access integration created for PyPI"
}

deploy_gpu_compute_pool() {
    log "=== Deploying GPU Compute Pool ==="
    snow_sql -q "
    CREATE COMPUTE POOL IF NOT EXISTS SNOWCORE_PDM_GPU_POOL
        MIN_NODES = 1
        MAX_NODES = 1
        INSTANCE_FAMILY = GPU_NV_S
        AUTO_SUSPEND_SECS = 600
        AUTO_RESUME = TRUE
        COMMENT = 'GPU compute pool for Snowcore PDM GNN notebooks with PyTorch';
    
    GRANT USAGE, OPERATE ON COMPUTE POOL SNOWCORE_PDM_GPU_POOL TO ROLE $SNOWFLAKE_ROLE;
    " --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
    log "GPU compute pool created: SNOWCORE_PDM_GPU_POOL"
}

deploy_notebooks() {
    log "=== Deploying Notebooks ==="
    
    snow_stage_create @SNOWCORE_PDM.PDM.NOTEBOOKS_STAGE || true
    
    for notebook in "$PROJECT_ROOT/notebooks/"*.ipynb; do
        if [[ -f "$notebook" ]]; then
            snow_stage_copy "$notebook" @SNOWCORE_PDM.PDM.NOTEBOOKS_STAGE/
            log "Uploaded: $(basename "$notebook")"
        fi
    done
    
    snow_sql -q "
    CREATE OR REPLACE NOTEBOOK SNOWCORE_PDM.PDM.ANOMALY_DETECTION_TRAINING
        FROM '@SNOWCORE_PDM.PDM.NOTEBOOKS_STAGE'
        MAIN_FILE = 'anomaly_detection_training.ipynb'
        QUERY_WAREHOUSE = '$SNOWFLAKE_WAREHOUSE';
    
    CREATE OR REPLACE NOTEBOOK SNOWCORE_PDM.PDM.GNN_CROSS_ASSET
        FROM '@SNOWCORE_PDM.PDM.NOTEBOOKS_STAGE'
        MAIN_FILE = 'gnn_cross_asset.ipynb'
        RUNTIME_NAME = 'SYSTEM\$GPU_RUNTIME'
        COMPUTE_POOL = 'SNOWCORE_PDM_GPU_POOL'
        QUERY_WAREHOUSE = '$SNOWFLAKE_WAREHOUSE'
        EXTERNAL_ACCESS_INTEGRATIONS = (SNOWCORE_PDM_PYPI_ACCESS)
        IDLE_AUTO_SHUTDOWN_TIME_SECONDS = 1800
        COMMENT = 'GNN cross-asset anomaly detection with PyTorch Geometric';
    
    ALTER NOTEBOOK SNOWCORE_PDM.PDM.ANOMALY_DETECTION_TRAINING ADD LIVE VERSION FROM LAST;
    ALTER NOTEBOOK SNOWCORE_PDM.PDM.GNN_CROSS_ASSET ADD LIVE VERSION FROM LAST;
    " --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
    
    log "Notebooks deployed to Snowflake"
}

deploy_streamlit() {
    log "=== Deploying Streamlit App ==="
    cd "$PROJECT_ROOT/streamlit"
    snow_streamlit_deploy --database "$DATABASE" --schema "PDM" --role "$SNOWFLAKE_ROLE" --replace
    cd "$PROJECT_ROOT"
}

generate_data() {
    log "=== Generating Synthetic Data ==="
    python3 "$PROJECT_ROOT/data/generate_data.py"
    log "Data generation complete"
}

upload_data() {
    log "=== Uploading Data ==="
    snow_stage_create @SNOWCORE_PDM.RAW.DATA_STAGE || true
    
    for file in "$PROJECT_ROOT/data/generated/"*.csv; do
        if [[ -f "$file" ]]; then
            snow_stage_copy "$file" @SNOWCORE_PDM.RAW.DATA_STAGE/
            log "Uploaded: $(basename "$file")"
        fi
    done
    
    run_sql_file "$PROJECT_ROOT/sql/03_load_data.sql" "Loading data from stage"
}

main() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c)
                CONNECTION="$2"
                shift 2
                ;;
            --only-ddl)
                ONLY_COMPONENT="ddl"
                shift
                ;;
            --only-data)
                ONLY_COMPONENT="data"
                shift
                ;;
            --only-cortex)
                ONLY_COMPONENT="cortex"
                shift
                ;;
            --only-streamlit)
                ONLY_COMPONENT="streamlit"
                shift
                ;;
            --only-notebooks)
                ONLY_COMPONENT="notebooks"
                shift
                ;;
            *)
                echo "Usage: $0 [-c CONNECTION] [--only-ddl|--only-data|--only-cortex|--only-streamlit|--only-notebooks]"
                exit 1
                ;;
        esac
    done

    log "=========================================="
    log "Snowcore Anomaly Detection - Deployment"
    log "=========================================="
    
    check_snow_cli
    
    if should_run_step "ddl"; then deploy_ddl; fi
    if should_run_step "data"; then generate_data; upload_data; fi
    if should_run_step "cortex_search"; then deploy_cortex_search; fi
    if should_run_step "cortex_model"; then deploy_semantic_model; fi
    if should_run_step "cortex_view"; then deploy_semantic_view; fi
    if should_run_step "cortex_agent"; then deploy_cortex_agent; fi
    if should_run_step "streaming"; then deploy_streaming_simulation; fi
    if should_run_step "notebooks"; then deploy_external_access; deploy_gpu_compute_pool; deploy_notebooks; fi
    if should_run_step "streamlit"; then deploy_streamlit; fi
    
    log "=========================================="
    log "Deployment complete!"
    log "=========================================="
}

main "$@"
