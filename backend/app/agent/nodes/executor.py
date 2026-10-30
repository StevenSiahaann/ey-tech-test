"""
Query Execution Node.
Executes validated SQL via read-only PostgreSQL / DuckDB connection with statement timeout.
"""

from typing import Dict, Any
from backend.app.agent.state import AgentState
from backend.app.stores.pg_executor import execute_readonly_sql


def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    sql = state.get("validated_sql")
    retries = state.get("retry_count", 0)
    if not sql:
        return {
            "query_result": None,
            "current_step": "Execution Skipped (No Validated SQL)"
        }

    res = execute_readonly_sql(sql)

    if res.success:
        return {
            "query_result": res.to_dict(),
            "sql_errors": [],
            "current_step": f"Executed Successfully ({res.row_count} rows, {res.execution_time_ms}ms)"
        }
    else:
        return {
            "query_result": res.to_dict(),
            "sql_errors": [f"Database Execution Error: {res.error_message or 'Unknown execution error'}"],
            "retry_count": retries + 1,
            "current_step": f"Execution Error: {res.error_message}"
        }
