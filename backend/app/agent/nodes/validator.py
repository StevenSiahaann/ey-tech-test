"""
SQL Validation Node.
Enforces guardrails, validates AST against schema allowlist, and injects LIMIT.
"""

from typing import Dict, Any
from backend.app.agent.state import AgentState
from backend.app.safety.sql_validator import validate_and_sanitize_sql


def validate_sql_node(state: AgentState) -> Dict[str, Any]:
    raw_sql = state.get("raw_sql", "")
    retries = state.get("retry_count", 0)

    val_res = validate_and_sanitize_sql(raw_sql)

    if val_res.is_valid:
        return {
            "validated_sql": val_res.sanitized_sql,
            "sql_errors": [],
            "current_step": "SQL Validated (Safety & Schema Approved)"
        }
    else:
        return {
            "validated_sql": None,
            "sql_errors": val_res.errors,
            "retry_count": retries + 1,
            "current_step": f"SQL Validation Failed: {', '.join(val_res.errors)}"
        }
