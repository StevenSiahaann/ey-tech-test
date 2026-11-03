"""
Database Query Executor for Conversational BI Agent.
Connects strictly via Read-Only role on PostgreSQL with ThreadedConnectionPool and timeout guardrails.
Transparently falls back to local embedded DuckDB if PostgreSQL is offline (zero-dependency local/cloud mode).
"""

import time
import os
import threading
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.core.logger import get_logger

logger = get_logger("stores.pg_executor")

_duckdb_con = None
_duckdb_lock = threading.Lock()
_pg_pool = None
_pg_pool_lock = threading.Lock()
_pg_offline_until: float = 0.0
_PG_RETRY_COOLDOWN_SECONDS: float = 30.0


def _get_duckdb_connection():
    global _duckdb_con
    if _duckdb_con is not None:
        return _duckdb_con
    with _duckdb_lock:
        if _duckdb_con is not None:
            return _duckdb_con
        try:
            import duckdb
            db_path = settings.DUCKDB_PATH
            if not os.path.exists(db_path):
                init_con = duckdb.connect(db_path)
                schema_file = "db/01_schema.sql"
                seed_file = "db/seed/seed_data.sql"
                views_file = "db/02_views.sql"
                if os.path.exists(schema_file) and os.path.exists(seed_file):
                    with open(schema_file) as f:
                        init_con.execute(f.read().replace("NUMERIC(14, 2)", "DOUBLE").replace("ON DELETE CASCADE", ""))
                    with open(seed_file) as f:
                        init_con.execute(f.read())
                    if os.path.exists(views_file):
                        with open(views_file) as vf:
                            init_con.execute(vf.read().replace("::numeric", "::DOUBLE"))
                init_con.close()

            # Connect strictly with read_only=True for concurrent access
            con = duckdb.connect(db_path, read_only=True)
            _duckdb_con = con
            return _duckdb_con
        except Exception:
            return None


def _get_pg_pool(dsn: str):
    """Lazily initializes ThreadedConnectionPool with thread safety."""
    global _pg_pool
    if _pg_pool is not None and not _pg_pool.closed:
        return _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None and not _pg_pool.closed:
            return _pg_pool
        from psycopg2.pool import ThreadedConnectionPool
        _pg_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn,
            connect_timeout=2
        )
        return _pg_pool


class QueryExecutionResult:
    def __init__(self, success: bool, columns: List[Dict[str, str]], rows: List[Dict[str, Any]], 
                 row_count: int, execution_time_ms: float, error_message: Optional[str] = None,
                 engine: str = "duckdb"):
        self.success = success
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
        self.error_message = error_message
        self.engine = engine

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "engine": self.engine,
        }


def execute_readonly_sql(sql: str, timeout_ms: Optional[int] = None) -> QueryExecutionResult:
    """
    Executes a sanitized SELECT SQL query.
    Tries PostgreSQL connection pool first; if offline, transparently falls back to local DuckDB
    with a cooldown timer so transient PostgreSQL outages self-heal automatically.
    """
    global _pg_offline_until, _pg_pool
    t_start = time.time()
    t_limit = int(timeout_ms or settings.SQL_TIMEOUT_MS)
    dsn = settings.DATABASE_URL_RO

    # 1. Attempt PostgreSQL execution via ThreadedConnectionPool (with automatic recovery after cooldown)
    is_localhost_dsn = "localhost" in dsn or "127.0.0.1" in dsn
    if not (is_localhost_dsn and time.time() < _pg_offline_until):
        pool = None
        conn = None
        try:
            from psycopg2.extras import RealDictCursor
            pool = _get_pg_pool(dsn)
            conn = pool.getconn()
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET statement_timeout = {t_limit};")
                cur.execute(sql)
                
                records = cur.fetchall()
                col_names = [desc[0] for desc in cur.description] if cur.description else []
                columns = [{"name": c, "type": "text"} for c in col_names]
                rows = [dict(r) for r in records]
                
                for row in rows:
                    for k, v in row.items():
                        if hasattr(v, "isoformat"):
                            row[k] = v.isoformat()
                        elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
                            row[k] = float(v)

                dur_ms = round((time.time() - t_start) * 1000, 2)
                _pg_offline_until = 0.0
                logger.info(f"[PostgreSQL Pool] Executed read-only SQL in {dur_ms}ms | rows={len(rows)}")
                return QueryExecutionResult(
                    success=True,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=dur_ms,
                    engine="postgresql",
                )
        except Exception as pg_err:
            if is_localhost_dsn:
                _pg_offline_until = time.time() + _PG_RETRY_COOLDOWN_SECONDS
            logger.debug(f"PostgreSQL connection unavailable ({pg_err}); falling back to embedded DuckDB engine.")
            if pool is not None and conn is not None:
                try:
                    pool.putconn(conn, close=True)
                    conn = None
                except Exception:
                    pass
        finally:
            if conn is not None and pool is not None:
                try:
                    pool.putconn(conn)
                except Exception:
                    pass

    # 2. Local Embedded DuckDB Fallback
    try:
        duck_con = _get_duckdb_connection()
        if duck_con:
            # Clean postgres-specific casts if any
            clean_sql = sql.replace("::numeric", "::DOUBLE")
            cur = duck_con.cursor()
            try:
                res = cur.execute(clean_sql)
                col_names = [desc[0] for desc in res.description] if res.description else []
                records = res.fetchall()
            finally:
                cur.close()
            
            columns = [{"name": c, "type": "text"} for c in col_names]
            rows = []
            for r in records:
                row_dict = {}
                for idx, col in enumerate(col_names):
                    val = r[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__") and not isinstance(val, (int, float, bool)):
                        val = float(val)
                    row_dict[col] = val
                rows.append(row_dict)

            dur_ms = round((time.time() - t_start) * 1000, 2)
            logger.info(f"[DuckDB Engine] Executed read-only SQL in {dur_ms}ms | rows={len(rows)}")
            return QueryExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=dur_ms
            )
    except Exception as e:
        dur_ms = round((time.time() - t_start) * 1000, 2)
        logger.error(f"SQL execution failed after {dur_ms}ms: {e}")
        return QueryExecutionResult(
            success=False,
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=dur_ms,
            error_message=str(e)
        )

    dur_ms = round((time.time() - t_start) * 1000, 2)
    return QueryExecutionResult(
        success=False,
        columns=[],
        rows=[],
        row_count=0,
        execution_time_ms=dur_ms,
        error_message="Database offline and local engine unavailable."
    )
