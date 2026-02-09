-- Cortex Agent for Reliability Copilot
-- Creates an AI agent with Cortex Search and Cortex Analyst tools

USE DATABASE SNOWCORE_PDM;
USE SCHEMA PDM;

CREATE OR REPLACE AGENT RELIABILITY_COPILOT
  COMMENT = 'Reliability engineering copilot for anomaly diagnosis and root cause analysis'
  PROFILE = '{"display_name": "Reliability Copilot"}'
  FROM SPECIFICATION $$
  {
    "models": {
      "orchestration": "claude-4-sonnet"
    },
    "instructions": {
      "orchestration": "Use knowledge_search for maintenance history, manuals, and work orders. Use data_analyst for metrics, trends, and structured data queries about assets, anomalies, and financial impact.",
      "response": "Always cite your sources with document names or table references. For anomalies, check if similar incidents occurred before. Highlight the humidity-scrap correlation when relevant: high humidity (>65%) in Layup Room causes 3x higher scrap rates 6 hours later during autoclave cure."
    },
    "tools": [
      {
        "tool_spec": {
          "type": "cortex_search",
          "name": "knowledge_search",
          "description": "Search maintenance manuals, CMMS logs, work orders, and historical incident documentation"
        }
      },
      {
        "tool_spec": {
          "type": "cortex_analyst_text_to_sql",
          "name": "data_analyst",
          "description": "Query structured data about asset health, anomaly events, maintenance metrics, scrap rates, and financial impact"
        }
      }
    ],
    "tool_resources": {
      "knowledge_search": {
        "search_service": "SNOWCORE_PDM.PDM.KNOWLEDGE_BASE_SEARCH",
        "max_results": 5,
        "columns": ["DOC_TYPE", "TITLE", "CONTENT", "SOURCE_FILE", "ASSET_MODEL"]
      },
      "data_analyst": {
        "semantic_view": "SNOWCORE_PDM.PDM.SNOWCORE_PDM_SEMANTIC_VIEW",
        "execution_environment": {
          "type": "warehouse",
          "warehouse": "COMPUTE_WH"
        }
      }
    }
  }
  $$;

GRANT USAGE ON AGENT RELIABILITY_COPILOT TO ROLE PUBLIC;
