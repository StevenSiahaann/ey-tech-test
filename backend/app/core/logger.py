"""
Enterprise Structured Logging & Dual Log Rotation Module.
Provides:
1. Context-aware structured logging across all FastAPI routes and LangGraph agent steps
   (propagating `session_id`, `request_id`, and `step` via Python `contextvars`).
2. Size-based log rotation (`RotatingFileHandler`) for `logs/agent_app.log`
   (default: 10 MB max size per file, 5 backup archives).
3. Time-based daily log rotation (`TimedRotatingFileHandler`) for `logs/security_audit.log`
   (default: rotates at midnight, retains 30 days of security & SQL audit trails).
4. Resilient directory initialization with automatic `/tmp/logs` fallback for read-only
   container filesystems.
"""

import logging
import os
import sys
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any

from backend.app.core.config import settings

# Context variables for automatic correlation across async/sync execution frames
_ctx_session_id: ContextVar[str] = ContextVar("session_id", default="-")
_ctx_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_ctx_step_name: ContextVar[str] = ContextVar("step_name", default="system")

_LOGGING_INITIALIZED = False
_ACTIVE_LOG_DIR: str = "logs"


class StructuredContextFilter(logging.Filter):
    """Injects correlation context (`session_id`, `request_id`, `step_name`) into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "session_id") or record.session_id == "-":
            record.session_id = _ctx_session_id.get()
        if not hasattr(record, "request_id") or record.request_id == "-":
            record.request_id = _ctx_request_id.get()
        if not hasattr(record, "step_name") or record.step_name == "system":
            record.step_name = _ctx_step_name.get()
        return True


def _resolve_writable_log_dir() -> Path:
    """Ensures a writable log directory exists, falling back to `/tmp/logs` if needed."""
    global _ACTIVE_LOG_DIR
    preferred = Path(settings.LOG_DIR)
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        test_file = preferred / ".write_probe"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        _ACTIVE_LOG_DIR = str(preferred.resolve())
        return preferred
    except Exception:
        fallback = Path("/tmp/ey_bi_logs")
        fallback.mkdir(parents=True, exist_ok=True)
        _ACTIVE_LOG_DIR = str(fallback.resolve())
        return fallback


def setup_logging() -> None:
    """
    Initializes root application logger and dedicated security audit logger
    with size-based (`RotatingFileHandler`) and time-based (`TimedRotatingFileHandler`) rotation.
    Idempotent: safe to call multiple times.
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    log_dir = _resolve_writable_log_dir()
    log_level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-7s | %(name)-24s | "
        "sess=%(session_id)s | req=%(request_id)s | step=%(step_name)-18s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    ctx_filter = StructuredContextFilter()

    # 1. Configure Application Namespace Logger ("ey_bi")
    app_logger = logging.getLogger("ey_bi")
    app_logger.setLevel(log_level)
    app_logger.propagate = False
    app_logger.handlers.clear()

    # Handler A: Console StreamHandler (Container stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ctx_filter)
    app_logger.addHandler(console_handler)

    # Handler B: Size-Rotated Application Log (`agent_app.log`, 10 MB x 5 backups)
    app_log_file = log_dir / "agent_app.log"
    rotating_file_handler = RotatingFileHandler(
        filename=str(app_log_file),
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    rotating_file_handler.setLevel(log_level)
    rotating_file_handler.setFormatter(formatter)
    rotating_file_handler.addFilter(ctx_filter)
    app_logger.addHandler(rotating_file_handler)

    # 2. Configure Security & Guardrail Audit Logger ("ey_bi.audit")
    audit_logger = logging.getLogger("ey_bi.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    audit_logger.handlers.clear()

    audit_log_file = log_dir / "security_audit.log"
    timed_audit_handler = TimedRotatingFileHandler(
        filename=str(audit_log_file),
        when="midnight",
        interval=1,
        backupCount=settings.LOG_AUDIT_RETENTION_DAYS,
        encoding="utf-8",
        utc=False,
    )
    timed_audit_handler.suffix = "%Y-%m-%d"
    timed_audit_handler.setLevel(logging.INFO)
    timed_audit_handler.setFormatter(formatter)
    timed_audit_handler.addFilter(ctx_filter)
    audit_logger.addHandler(timed_audit_handler)
    # Mirror security events to console as well
    audit_logger.addHandler(console_handler)

    _LOGGING_INITIALIZED = True


def set_log_context(
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    step_name: Optional[str] = None,
) -> None:
    """Binds correlation identifiers to the current execution context."""
    if session_id is not None:
        _ctx_session_id.set(session_id)
    if request_id is not None:
        _ctx_request_id.set(request_id)
    if step_name is not None:
        _ctx_step_name.set(step_name)


def clear_log_context() -> None:
    """Resets correlation context variables to default values."""
    _ctx_session_id.set("-")
    _ctx_request_id.set("-")
    _ctx_step_name.set("system")


def get_logger(component: str = "agent") -> logging.Logger:
    """Returns a child logger under the `ey_bi` hierarchy with rotation configured."""
    setup_logging()
    clean_name = component.replace("backend.app.", "").replace("ey_bi.", "")
    return logging.getLogger(f"ey_bi.{clean_name}")


def get_audit_logger() -> logging.Logger:
    """Returns the dedicated daily-rotated security audit logger (`ey_bi.audit`)."""
    setup_logging()
    return logging.getLogger("ey_bi.audit")


def log_step_event(
    node: str,
    title: str,
    detail: str,
    elapsed_ms: float,
    level: int = logging.INFO,
) -> None:
    """Logs a standardized LangGraph pipeline step progression event."""
    set_log_context(step_name=node)
    logger = get_logger(f"step.{node}")
    compact_detail = " ".join((detail or "").split())
    logger.log(level, f"[{title}] ({elapsed_ms:.1f}ms) {compact_detail}")


def log_security_event(
    event_type: str,
    status: str,
    detail: str,
    level: int = logging.WARNING,
) -> None:
    """Records a guardrail or SQL AST security event to both app and audit logs."""
    audit = get_audit_logger()
    app_log = get_logger("safety")
    clean_detail = " ".join((detail or "").split())
    msg = f"SECURITY_EVENT={event_type} | STATUS={status} | {clean_detail}"
    audit.log(level, msg)
    app_log.log(level, msg)


def get_log_rotation_status() -> Dict[str, Any]:
    """Returns diagnostic metadata about active log files and rotation policies."""
    setup_logging()
    app_log_path = os.path.join(_ACTIVE_LOG_DIR, "agent_app.log")
    audit_log_path = os.path.join(_ACTIVE_LOG_DIR, "security_audit.log")
    return {
        "log_dir": _ACTIVE_LOG_DIR,
        "app_log": {
            "path": app_log_path,
            "exists": os.path.exists(app_log_path),
            "policy": "RotatingFileHandler (size-based)",
            "max_bytes": settings.LOG_MAX_BYTES,
            "backup_count": settings.LOG_BACKUP_COUNT,
        },
        "security_audit_log": {
            "path": audit_log_path,
            "exists": os.path.exists(audit_log_path),
            "policy": "TimedRotatingFileHandler (daily midnight)",
            "retention_days": settings.LOG_AUDIT_RETENTION_DAYS,
        },
    }

