"""
FastAPI REST and SSE Routes for Conversational BI Agent.
"""

import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.agent.graph import stream_conversational_turn, process_conversational_turn
from backend.app.agent.state import AgentResponse
from backend.app.core.logger import get_logger, get_log_rotation_status
from backend.app.stores.redis_session import session_store
from backend.app.semantic.schema_registry import ALLOWED_SCHEMAS

logger = get_logger("api.routes")
router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = True
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    language: Optional[str] = None


class FeedbackRequest(BaseModel):
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    score: int # 1 for thumbs up, -1 for thumbs down
    comment: Optional[str] = None


class TestConnectionRequest(BaseModel):
    provider: Optional[str] = "gemini"
    model: Optional[str] = None


@router.get("/models")
def get_models_endpoint():
    """
    Returns available LLM providers (Gemini & Azure OpenAI) and their configuration status.
    """
    from backend.app.core.llm_factory import get_available_models
    return get_available_models()


@router.post("/models/test-connection")
def test_model_connection(req: TestConnectionRequest):
    """
    Tests connectivity and latency to the specified LLM Provider & Model.
    """
    import time
    from backend.app.core.llm_factory import get_llm

    start_time = time.time()
    prov = (req.provider or "gemini").lower().strip()
    target_model = req.model

    try:
        llm = get_llm(provider_override=prov, model_override=target_model)
        probe_res = llm.invoke("Hi")
        latency_ms = round((time.time() - start_time) * 1000, 1)
        return {
            "status": "connected",
            "provider": prov,
            "model": target_model or "default",
            "latency_ms": latency_ms,
            "message": f"Koneksi berhasil! Model merespons dalam {latency_ms}ms."
        }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 1)
        err_msg = str(e)
        if "API_KEY" in err_msg.upper() or "AUTHENTICATION" in err_msg.upper() or "403" in err_msg or "FORBIDDEN" in err_msg.upper():
            user_friendly = "Autentikasi gagal. Kredensial API Key belum valid atau dibatasi kebijakan jaringan/sandbox."
        elif "NOT_FOUND" in err_msg.upper() or "404" in err_msg:
            user_friendly = f"Model '{target_model}' tidak ditemukan pada provider {prov}."
        elif "ENDPOINT" in err_msg.upper() or "CONNECTION" in err_msg.upper():
            user_friendly = f"Gagal menghubungi endpoint provider {prov}. Periksa konfigurasi endpoint."
        else:
            user_friendly = f"Error koneksi ({prov}): {err_msg[:120]}"

        return {
            "status": "error",
            "provider": prov,
            "model": target_model or "default",
            "latency_ms": latency_ms,
            "message": user_friendly,
            "raw_error": err_msg[:200]
        }


@router.post("/chat")
def chat_endpoint(req: ChatRequest):
    """
    Main Chat Endpoint. Returns SSE stream of real-time agent progression
    or standard JSON response.
    """
    if not req.stream:
        resp = process_conversational_turn(
            req.session_id, 
            req.message,
            llm_provider=req.llm_provider,
            model_name=req.model_name,
            language=req.language
        )
        return resp.model_dump()

    def event_generator():
        try:
            for event in stream_conversational_turn(
                req.session_id, 
                req.message,
                llm_provider=req.llm_provider,
                model_name=req.model_name,
                language=req.language
            ):
                ev_type = event.get("type")
                if ev_type == "step":
                    yield f"event: step\ndata: {json.dumps(event)}\n\n"
                elif ev_type in ("answer", "refusal", "error"):
                    payload = event.get("payload")
                    dumped = payload.model_dump() if hasattr(payload, "model_dump") else payload
                    yield f"event: {ev_type}\ndata: {json.dumps(dumped)}\n\n"
        except Exception as e:
            err_payload = {
                "type": "error",
                "language": req.language or "id",
                "summary": f"Terjadi kesalahan pemrosesan: {str(e)[:120]}",
                "insights": ["Permintaan tidak dapat diselesaikan karena kendala internal.", "Silakan muat ulang atau coba pertanyaan lain."],
                "assumptions": []
            }
            yield f"event: error\ndata: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/examples")
def get_examples():
    """Returns the 10 Technical Test benchmark questions for quick UI testing."""
    return [
        {"id": 1, "text": "GMV MTD untuk region Jawa?", "tag": "GMV & MTD"},
        {"id": 2, "text": "Revenue dan margin MTD untuk FMCG di Jawa?", "tag": "Revenue & Margin"},
        {"id": 3, "text": "Top 5 produk berdasarkan revenue bulan lalu?", "tag": "Ranking & Prior Month"},
        {"id": 4, "text": "Channel dengan revenue tertinggi di Q1 2025?", "tag": "Quarterly Analysis"},
        {"id": 5, "text": "Cancel rate bulan ini?", "tag": "Operational Metric"},
        {"id": 6, "text": "Segment customer dengan margin tertinggi YTD?", "tag": "Customer Segments"},
        {"id": 7, "text": "Revenue POS vs E-commerce minggu ini?", "tag": "Channel Comparison"},
        {"id": 8, "text": "Store di Jakarta dengan revenue tertinggi bulan ini?", "tag": "Store Performance"},
        {"id": 9, "text": "Revenue FMCG MTD di Jawa? -> Breakdown per city. -> Top 3 store dari city tertinggi.", "tag": "Follow-up Context"},
        {"id": 10, "text": "Revenue anomaly: drop >30% vs 7-day average", "tag": "Anomaly Detection"}
    ]


@router.get("/schema")
def get_schema_dictionary():
    """Returns the analytical schema definitions."""
    return ALLOWED_SCHEMAS


@router.get("/sessions/{session_id}")
def get_session_info(session_id: str):
    """Retrieves session state details."""
    data = session_store.get_session(session_id)
    return {"session_id": session_id, "state": data}


@router.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    """Clears conversation session history."""
    session_store.clear_session(session_id)
    return {"status": "success", "message": f"Session {session_id} has been reset."}


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """Submits user feedback for Langfuse observability and promotes verified SQL to Vector Store."""
    promoted = False
    if req.score > 0 and req.session_id:
        from backend.app.stores.vector_client import add_verified_example
        sess = session_store.get_session(req.session_id)
        last_turn = (sess.get("prev_result_digest") or {}).get("last_verified_turn")
        if last_turn and last_turn.get("question") and last_turn.get("sql"):
            promoted = add_verified_example(
                question=last_turn["question"],
                sql=last_turn["sql"],
                intent=last_turn.get("intent", "metric_query")
            )
    if req.trace_id:
        try:
            from backend.app.core.llm_factory import get_langfuse_client
            lf = get_langfuse_client()
            if lf:
                lf.score(
                    trace_id=req.trace_id,
                    name="user_feedback",
                    value=float(req.score),
                    comment=req.comment or ("Positive user feedback" if req.score > 0 else "Negative user feedback"),
                )
                lf.flush()
        except Exception:
            pass
    return {"status": "recorded", "score": req.score, "promoted_to_vector_store": promoted}


@router.get("/health")
def healthcheck():
    """Service health status including log rotation diagnostics."""
    return {
        "status": "healthy",
        "service": "Conversational BI Agent",
        "semantic_layer": "active",
        "guardrails": "enforced",
        "logging": get_log_rotation_status(),
    }
