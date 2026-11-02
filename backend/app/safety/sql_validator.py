"""
SQL Security Validator and Guardrails Module.
Enforces:
1. Strict SELECT-only operations (no DDL, DML, TCL, COPY, CALL, etc.)
2. Exactly one statement (no semicolon chaining or multi-statement injection)
3. Schema, Table/View, and Column allowlist validation via sqlglot AST
4. Prohibition of destructive or dangerous PostgreSQL system functions (pg_sleep, pg_read_file, dblink, etc.)
5. Mandatory outer-query LIMIT cap (maximum 1000 rows)
"""

import re
from typing import List, Set, Optional
from backend.app.semantic.schema_registry import get_allowed_tables, get_allowed_columns_for_table
from backend.app.core.logger import get_logger, log_security_event

logger = get_logger("safety.sql_validator")

DISALLOWED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
    "GRANT", "REVOKE", "COPY", "CALL", "EXECUTE", "VACUUM", "REINDEX",
    "LOCK", "EXPLAIN", "ANALYZE"
}

DANGEROUS_FUNCTIONS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_write_file", "pg_ls_dir",
    "pg_stat_file", "dblink", "dblink_exec", "lo_export", "lo_import", "lo_get",
    "lo_put", "lo_from_bytea", "set_config", "current_setting",
    "pg_terminate_backend", "pg_cancel_backend", "query_to_xml", "inet_server_addr",
    "inet_server_port", "version"
}

ALLOWED_ANONYMOUS_FUNCTIONS = {
    "ntile", "date_trunc", "date_part", "to_char", "round", "coalesce", "nullif",
    "abs", "cast", "lower", "upper", "trim", "substring", "stddev",
    "percentile_cont", "percentile_disc", "lag", "lead", "rank", "dense_rank",
    "row_number", "extract", "greatest", "least"
}

FORBIDDEN_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


def escape_sql_literal(value: object) -> str:
    """Safely escapes single quotes in SQL string literals to prevent injection or broken syntax."""
    return str(value).replace("'", "''")


class ValidationResult:
    def __init__(self, is_valid: bool, sanitized_sql: str = "", errors: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.sanitized_sql = sanitized_sql
        self.errors = errors or []
        if not is_valid and self.errors:
            log_security_event(
                event_type="SQL_AST_VALIDATION_REJECTED",
                status="BLOCKED",
                detail=f"Errors={self.errors} | SQL='{sanitized_sql[:120]}'",
            )
        elif is_valid:
            logger.info(f"SQL AST validated & sanitized: '{' '.join(sanitized_sql.split())[:120]}'")

    def __repr__(self):
        return f"<ValidationResult valid={self.is_valid} errors={self.errors}>"


def validate_and_sanitize_sql(raw_sql: str, max_limit: int = 1000) -> ValidationResult:
    """
    Validates generated SQL for security, schema compliance, and injects outer LIMIT.
    Returns ValidationResult with sanitized_sql if valid, or errors list if invalid.
    """
    # 1. Clean query string
    sql = raw_sql.strip()
    if sql.startswith("```"):
        lines = sql.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    if sql.endswith(";"):
        sql = sql[:-1].strip()

    if not sql:
        return ValidationResult(is_valid=False, errors=["Query SQL kosong."])

    # 2. Check for multiple statements (semicolon chaining outside string literals)
    parts = re.split(r";(?=(?:[^']*'[^']*')*[^']*$)", sql)
    if len(parts) > 1:
        return ValidationResult(is_valid=False, errors=["Multi-statement tidak diizinkan (dilarang menggunakan titik koma ganda)."])

    # 3. Check AST using sqlglot
    try:
        import sqlglot
        from sqlglot import exp

        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception as e:
            return ValidationResult(is_valid=False, errors=[f"Sintaks SQL tidak valid: {str(e)}"])

        # Root expression must be Select or Union
        if not isinstance(parsed, (exp.Select, exp.Union)):
            return ValidationResult(is_valid=False, errors=[f"Hanya query SELECT yang diizinkan. Tipe perintah terdeteksi: {parsed.key.upper()}"])

        allowed_tables = get_allowed_tables()
        cte_names = {cte.alias_or_name.lower() for cte in parsed.find_all(exp.CTE)}
        referenced_base_tables: Set[str] = set()

        for node in parsed.walk():
            if isinstance(node, exp.Into):
                return ValidationResult(is_valid=False, errors=["SELECT INTO tidak diizinkan."])

            if isinstance(node, exp.Anonymous):
                fn_name = node.name.lower()
                if fn_name in DANGEROUS_FUNCTIONS:
                    return ValidationResult(is_valid=False, errors=[f"Fungsi berbahaya '{fn_name}' diblokir."])
                if fn_name not in ALLOWED_ANONYMOUS_FUNCTIONS:
                    return ValidationResult(is_valid=False, errors=[f"Fungsi tidak dikenal atau tidak diizinkan: '{fn_name}'."])
            elif isinstance(node, exp.Func):
                fn_name = (node.sql_name() or "").lower()
                if fn_name in DANGEROUS_FUNCTIONS:
                    return ValidationResult(is_valid=False, errors=[f"Fungsi berbahaya '{fn_name}' diblokir."])

            if isinstance(node, exp.Table):
                table_name = node.name.lower()
                db_schema = node.db.lower() if node.db else ""

                if db_schema in FORBIDDEN_SCHEMAS:
                    return ValidationResult(is_valid=False, errors=[f"Akses ke skema sistem '{db_schema}' diblokir."])

                if table_name not in allowed_tables and table_name not in cte_names:
                    return ValidationResult(is_valid=False, errors=[f"Tabel atau view '{table_name}' tidak ada dalam skema database yang diizinkan."])

                if table_name in allowed_tables:
                    referenced_base_tables.add(table_name)

        # Validate column names against allowed base tables/views AND CTE aliases (closes CTE column bypass)
        if referenced_base_tables:
            allowed_cols: Set[str] = set()
            for t_name in referenced_base_tables:
                allowed_cols.update(get_allowed_columns_for_table(t_name))
            # Also allow SELECT aliases defined in the query or inside CTE projections
            select_aliases = {alias.alias.lower() for alias in parsed.find_all(exp.Alias) if alias.alias}
            for col_node in parsed.find_all(exp.Column):
                c_name = col_node.name.lower()
                if c_name and c_name != "*" and c_name not in allowed_cols and c_name not in select_aliases:
                    return ValidationResult(
                        is_valid=False,
                        errors=[f"Kolom '{c_name}' tidak ditemukan pada tabel/view {', '.join(sorted(referenced_base_tables))}."]
                    )

        # 4. Enforce or Cap LIMIT on the outermost query AST
        outer_limit_node = parsed.args.get("limit")
        if outer_limit_node is not None and isinstance(outer_limit_node, exp.Limit):
            try:
                existing_limit = int(outer_limit_node.expression.name)
                if existing_limit > max_limit:
                    sql = re.sub(r'\bLIMIT\s+\d+\s*$', f"LIMIT {max_limit}", sql, flags=re.IGNORECASE)
            except Exception:
                pass
        else:
            sql = f"{sql} LIMIT {max_limit}"

        return ValidationResult(is_valid=True, sanitized_sql=sql)

    except ImportError:
        # Fallback lexical check if sqlglot is unavailable
        sql_upper = sql.upper()
        first_token = re.split(r'\s+', sql_upper)[0]
        if first_token not in ("SELECT", "WITH"):
            return ValidationResult(is_valid=False, errors=[f"Hanya perintah SELECT atau WITH yang diizinkan (ditemukan: {first_token})."])

        for kw in DISALLOWED_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', sql_upper):
                return ValidationResult(is_valid=False, errors=[f"Kata kunci berbahaya '{kw}' tidak diizinkan."])

        for fn in DANGEROUS_FUNCTIONS:
            if re.search(r'\b' + fn + r'\b', sql.lower()):
                return ValidationResult(is_valid=False, errors=[f"Fungsi sistem '{fn}' diblokir."])

        limit_match = re.search(r'\bLIMIT\s+(\d+)\s*$', sql, re.IGNORECASE)
        if limit_match:
            if int(limit_match.group(1)) > max_limit:
                sql = re.sub(r'\bLIMIT\s+\d+\s*$', f"LIMIT {max_limit}", sql, flags=re.IGNORECASE)
        else:
            sql = f"{sql} LIMIT {max_limit}"

        return ValidationResult(is_valid=True, sanitized_sql=sql)
