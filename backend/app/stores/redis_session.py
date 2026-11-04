"""
Session State Manager using Redis with In-Memory Fallback.
Stores conversation state, previous query plans, and result digests.
Uses only standard Redis commands (GET, SETEX, DEL) for full compatibility with Azure Cache for Redis.
"""

import json
import time
from typing import Dict, Any, Optional
from backend.app.core.config import settings

_in_memory_store: Dict[str, Dict[str, Any]] = {}


def _get_redis_client():
    if not settings.REDIS_URL or settings.REDIS_URL.lower() in ("none", "not-configured", ""):
        return None
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Test ping with short timeout
        client.ping()
        return client
    except Exception:
        return None


class SessionStore:
    def __init__(self):
        self._redis = _get_redis_client()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieves session state data by session_id."""
        if self._redis:
            try:
                data = self._redis.get(f"session:{session_id}")
                return json.loads(data) if data else {}
            except Exception:
                pass
        
        # Fallback in-memory
        item = _in_memory_store.get(session_id)
        if item:
            if time.time() < item.get("_expires_at", 0):
                return item.get("data", {})
            else:
                del _in_memory_store[session_id]
        return {}

    def save_session(self, session_id: str, state_data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        """Saves session state with expiry TTL."""
        ttl = ttl_seconds or settings.SESSION_TTL_SECONDS
        if self._redis:
            try:
                self._redis.setex(
                    f"session:{session_id}",
                    ttl,
                    json.dumps(state_data)
                )
                return
            except Exception:
                pass

        # Fallback in-memory
        _in_memory_store[session_id] = {
            "data": state_data,
            "_expires_at": time.time() + ttl
        }

    def clear_session(self, session_id: str) -> None:
        """Deletes session state."""
        if self._redis:
            try:
                self._redis.delete(f"session:{session_id}")
            except Exception:
                pass
        _in_memory_store.pop(session_id, None)


session_store = SessionStore()
