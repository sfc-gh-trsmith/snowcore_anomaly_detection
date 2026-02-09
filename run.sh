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

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error_exit() { echo -e "${RED}[ERROR] $1${NC}" >&2; exit 1; }
warn() { echo -e "${YELLOW}[WARNING] $1${NC}"; }

snow_sql() { snow sql -c "$CONNECTION" "$@"; }

cmd_main() {
    log "=== Snowcore Reliability Dashboard ==="
    log "App: SNOWCORE_PDM.PDM.RELIABILITY_DASHBOARD"
    log "Open Snowsight to view the app"
}

cmd_status() {
    log "=== Resource Status ==="
    
    log "Database:"
    snow_sql -q "SHOW DATABASES LIKE 'SNOWCORE_PDM'" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
    
    log "Streamlit App:"
    snow_sql -q "SHOW STREAMLITS LIKE 'RELIABILITY_DASHBOARD' IN SNOWCORE_PDM.PDM" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Not found"
    
    log "Cortex Search:"
    snow_sql -q "SHOW CORTEX SEARCH SERVICES IN SNOWCORE_PDM.PDM" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Not found"
    
    log "Notebooks:"
    snow_sql -q "SHOW NOTEBOOKS IN SNOWCORE_PDM.PDM" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Not found"
    
    log "GNN Propagation Scores:"
    snow_sql -q "SELECT COUNT(*) AS ROW_COUNT FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Table not found"
    
    log "Model Diagnostics:"
    snow_sql -q "SELECT COUNT(*) AS ROW_COUNT FROM SNOWCORE_PDM.PDM.MODEL_DIAGNOSTICS" --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Table not found"
}

cmd_streamlit() {
    log "=== Streamlit App URL ==="
    echo "https://app.snowflake.com/<account>/#/streamlit-apps/SNOWCORE_PDM.PDM.RELIABILITY_DASHBOARD"
    log "Replace <account> with your Snowflake account identifier"
}

cmd_test() {
    log "=== Running Tests ==="
    
    log "Testing DDL..."
    snow_sql -q "SELECT 1 FROM SNOWCORE_PDM.DATA_MART.FINANCIAL_SUMMARY LIMIT 1" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "FINANCIAL_SUMMARY not accessible"
    
    log "Testing Cortex Search..."
    snow_sql -q "SHOW CORTEX SEARCH SERVICES IN SNOWCORE_PDM.PDM" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Cortex Search not found"
    
    log "Testing humidity-scrap correlation..."
    snow_sql -q "SELECT * FROM SNOWCORE_PDM.DATA_MART.V_HUMIDITY_SCRAP_CORRELATION LIMIT 1" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Correlation view not found"
    
    log "Testing asset graph..."
    snow_sql -q "SELECT COUNT(*) FROM SNOWCORE_PDM.CONFIG.ASSET_GRAPH" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Asset graph not found"
    
    log "Testing GNN propagation scores..."
    snow_sql -q "SELECT COUNT(*) FROM SNOWCORE_PDM.PDM.GNN_PROPAGATION_SCORES" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "GNN scores not found"
    
    log "Testing model diagnostics..."
    snow_sql -q "SELECT COUNT(*) FROM SNOWCORE_PDM.PDM.MODEL_DIAGNOSTICS" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Model diagnostics not found"
    
    log "Testing maintenance decisions..."
    snow_sql -q "SELECT ASSET_ID, RECOMMENDATION, NET_BENEFIT FROM SNOWCORE_PDM.PDM.MAINTENANCE_DECISIONS_LIVE ORDER BY NET_BENEFIT DESC LIMIT 5" \
        --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE" || warn "Maintenance decisions not found"
    
    log "=== All Tests Complete ==="
}

cmd_demo() {
    log "=== Injecting Demo Anomaly ==="
    
    snow_sql -q "
    INSERT INTO SNOWCORE_PDM.PDM.ANOMALY_EVENTS (ASSET_ID, TIMESTAMP, ANOMALY_TYPE, ANOMALY_SCORE, SEVERITY, ROOT_CAUSE)
    VALUES ('AUTOCLAVE_01', CURRENT_TIMESTAMP(), 'VACUUM_LEAK', 0.87, 'HIGH', 'Vacuum seal degradation detected');
    " --warehouse "$SNOWFLAKE_WAREHOUSE" --role "$SNOWFLAKE_ROLE"
    
    log "Demo anomaly event created"
    log "Open Streamlit app to see the Investigation Deck"
}

main() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c)
                CONNECTION="$2"
                shift 2
                ;;
            main|test|demo|status|streamlit)
                break
                ;;
            *)
                echo "Usage: $0 [-c CONNECTION] {main|test|demo|status|streamlit}"
                exit 1
                ;;
        esac
    done

    case "${1:-main}" in
        main) cmd_main ;;
        test) cmd_test ;;
        demo) cmd_demo ;;
        status) cmd_status ;;
        streamlit) cmd_streamlit ;;
        *)
            echo "Usage: $0 [-c CONNECTION] {main|test|demo|status|streamlit}"
            exit 1
            ;;
    esac
}

main "$@"
