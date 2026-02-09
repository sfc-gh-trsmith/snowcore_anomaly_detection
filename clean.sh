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
FORCE=false

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error_exit() { echo -e "${RED}[ERROR] $1${NC}" >&2; exit 1; }
warn() { echo -e "${YELLOW}[WARNING] $1${NC}"; }

snow_sql() { snow sql -c "$CONNECTION" "$@"; }

confirm() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    read -p "Are you sure you want to delete all Snowcore PDM objects? (yes/no): " response
    if [[ "$response" != "yes" ]]; then
        log "Cleanup cancelled"
        exit 0
    fi
}

clean_streamlit() {
    log "=== Removing Streamlit App ==="
    snow_sql -q "DROP STREAMLIT IF EXISTS SNOWCORE_PDM.PDM.RELIABILITY_DASHBOARD" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
}

clean_cortex_search() {
    log "=== Removing Cortex Search Service ==="
    snow_sql -q "DROP CORTEX SEARCH SERVICE IF EXISTS SNOWCORE_PDM.PDM.KNOWLEDGE_BASE_SEARCH" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
}

clean_notebooks() {
    log "=== Removing Notebooks ==="
    snow_sql -q "DROP NOTEBOOK IF EXISTS SNOWCORE_PDM.PDM.ANOMALY_DETECTION_TRAINING" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    snow_sql -q "DROP NOTEBOOK IF EXISTS SNOWCORE_PDM.PDM.GNN_CROSS_ASSET" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    snow_sql -q "DROP STAGE IF EXISTS SNOWCORE_PDM.PDM.NOTEBOOKS_STAGE" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    log "Notebooks removed"
}

clean_external_access() {
    log "=== Removing External Access Integration ==="
    snow_sql -q "DROP EXTERNAL ACCESS INTEGRATION IF EXISTS SNOWCORE_PDM_PYPI_ACCESS" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    snow_sql -q "DROP NETWORK RULE IF EXISTS SNOWCORE_PDM.PDM.PYPI_NETWORK_RULE" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    log "External access integration removed"
}

clean_gpu_compute_pool() {
    log "=== Removing GPU Compute Pool ==="
    snow_sql -q "ALTER COMPUTE POOL SNOWCORE_PDM_GPU_POOL STOP ALL" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    snow_sql -q "DROP COMPUTE POOL IF EXISTS SNOWCORE_PDM_GPU_POOL" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    log "GPU compute pool removed"
}

clean_stages() {
    log "=== Removing Stages ==="
    snow_sql -q "DROP STAGE IF EXISTS SNOWCORE_PDM.PDM.MODELS" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
    snow_sql -q "DROP STAGE IF EXISTS SNOWCORE_PDM.RAW.DATA_STAGE" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || true
}

clean_database() {
    log "=== Removing Database ==="
    snow_sql -q "DROP DATABASE IF EXISTS SNOWCORE_PDM CASCADE" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
}

clean_local() {
    log "=== Cleaning Local Generated Data ==="
    rm -rf "$PROJECT_ROOT/data/generated/"
    log "Local data cleaned"
}

main() {
    local action=""
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force|-y)
                FORCE=true
                shift
                ;;
            -c)
                CONNECTION="$2"
                shift 2
                ;;
            streamlit|search|stages|notebooks|database|local|external|gpu|all)
                action="$1"
                shift
                ;;
            *)
                echo "Usage: $0 [--force|-y] [-c CONNECTION] {streamlit|search|stages|notebooks|external|gpu|database|local|all}"
                exit 1
                ;;
        esac
    done

    action="${action:-all}"

    log "=========================================="
    log "Snowcore Anomaly Detection - Cleanup"
    log "=========================================="
    
    case "$action" in
        streamlit)
            clean_streamlit
            ;;
        search)
            clean_cortex_search
            ;;
        stages)
            clean_stages
            ;;
        notebooks)
            clean_notebooks
            ;;
        external)
            clean_external_access
            ;;
        gpu)
            clean_gpu_compute_pool
            ;;
        database)
            confirm
            clean_database
            ;;
        local)
            clean_local
            ;;
        all)
            confirm
            clean_streamlit
            clean_cortex_search
            clean_notebooks
            clean_external_access
            clean_gpu_compute_pool
            clean_stages
            clean_database
            clean_local
            ;;
    esac
    
    log "=========================================="
    log "Cleanup complete!"
    log "=========================================="
}

main "$@"
