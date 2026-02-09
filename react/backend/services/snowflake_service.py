import os
import json
import requests
import snowflake.connector
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

AGENT_DATABASE = "SNOWCORE_PDM"
AGENT_SCHEMA = "PDM"
AGENT_NAME = "RELIABILITY_COPILOT"


class SnowflakeService:
    def __init__(self):
        self.connection_name = os.getenv("SNOWFLAKE_CONNECTION_NAME", "demo")
        self.database = os.getenv("SNOWFLAKE_DATABASE", "SNOWCORE_PDM")
        self.schema = os.getenv("SNOWFLAKE_SCHEMA", "PDM")
        self._connection: Optional[snowflake.connector.SnowflakeConnection] = None

    def _get_connection(self) -> snowflake.connector.SnowflakeConnection:
        if self._connection is None or self._connection.is_closed():
            logger.info(f"Connecting to Snowflake with connection: {self.connection_name}")
            self._connection = snowflake.connector.connect(
                connection_name=self.connection_name,
                database=self.database,
                schema=self.schema,
            )
        return self._connection

    def close(self):
        if self._connection and not self._connection.is_closed():
            self._connection.close()
            self._connection = None
            logger.info("Snowflake connection closed")

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {timeout}")

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_api_token(self) -> str:
        """Get a session token for REST API authentication."""
        conn = self._get_connection()
        token_data = conn._rest._token_request("ISSUE")
        return token_data["data"]["sessionToken"]

    def get_account_url(self) -> str:
        """Get the Snowflake account URL for REST API calls."""
        conn = self._get_connection()
        host = conn.host
        if "_" in host:
            host = host.replace("_", "-")
        return f"https://{host}"

    def call_cortex_agent(self, user_message: str) -> Dict[str, Any]:
        """Call the Cortex Agent REST API and return parsed response."""
        token = self.get_api_token()
        account_url = self.get_account_url()

        api_endpoint = f"{account_url}/api/v2/databases/{AGENT_DATABASE}/schemas/{AGENT_SCHEMA}/agents/{AGENT_NAME}:run"

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_message}]
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f'Snowflake Token="{token}"',
        }

        logger.info(f"Calling Cortex Agent: {AGENT_NAME}")

        response = requests.post(
            api_endpoint,
            json=payload,
            headers=headers,
            stream=True,
            timeout=60
        )

        if response.status_code != 200:
            logger.error(f"Agent API error {response.status_code}: {response.text}")
            raise Exception(f"Agent API error {response.status_code}: {response.text}")

        text_parts = []
        tool_calls = []
        sources = []
        current_event_type = None

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("event:"):
                current_event_type = line[6:].strip()
                continue
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str and data_str != "[DONE]":
                    try:
                        data = json.loads(data_str)
                        if current_event_type == "error":
                            error_msg = data.get("message", "Unknown error from Cortex Agent")
                            logger.error(f"Agent error: {error_msg}")
                            return {
                                "response": f"The Cortex Agent encountered an error: {error_msg}",
                                "tool_calls": [],
                                "sources": []
                            }
                        if isinstance(data, dict):
                            if current_event_type == "response.text.delta":
                                text_parts.append(data.get("text", ""))
                            elif current_event_type == "response.tool_use":
                                tool_name = data.get("name", "unknown")
                                tool_calls.append({
                                    "name": tool_name,
                                    "type": "cortex_analyst" if "analyst" in tool_name.lower() else "cortex_search",
                                    "status": "complete"
                                })
                            elif current_event_type == "response.tool_result":
                                content = data.get("content", [])
                                for item in content:
                                    if isinstance(item, dict) and item.get("json", {}).get("searchResults"):
                                        for result in item["json"].get("searchResults", []):
                                            sources.append({
                                                "title": result.get("title", "Document"),
                                                "snippet": result.get("text", "")[:200] if result.get("text") else None
                                            })
                    except json.JSONDecodeError:
                        continue

        logger.info(f"Agent response text parts: {len(text_parts)}")
        return {
            "response": "".join(text_parts),
            "tool_calls": tool_calls,
            "sources": sources
        }


_service: Optional[SnowflakeService] = None


def get_snowflake_service() -> SnowflakeService:
    global _service
    if _service is None:
        _service = SnowflakeService()
    return _service


def close_snowflake_service():
    global _service
    if _service:
        _service.close()
        _service = None
