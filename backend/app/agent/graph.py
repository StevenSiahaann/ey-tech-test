"""
LangGraph Conversational BI Workflow Builder.
Orchestrates Input Guard, Context Loading, Planning, Few-shot Retrieval,
SQL Generation, AST Validation with Self-Correction Retry Loop, Execution,
Grounded Synthesis, and Session State Persistence.
"""

import logging
import re
import time
import uuid
from typing import Dict, Any, Generator, Optional, Literal
from langgraph.graph import StateGraph, END

from backend.app.agent.state import AgentState, AgentResponse, ClarificationPayload
from backend.app.core.logger import get_logger, set_log_context, log_step_event
from backend.app.safety.input_guard import check_input_safety

logger = get_logger("agent.graph")
from backend.app.stores.redis_session import session_store
from backend.app.agent.nodes.planner import plan_query
from backend.app.stores.vector_client import retrieve_few_shots
from backend.app.agent.nodes.generator import generate_sql
from backend.app.agent.nodes.validator import validate_sql_node
from backend.app.agent.nodes.executor import execute_sql_node
from backend.app.agent.nodes.synthesizer import synthesize_response, synthesize_discussion_response


def _extract_views_from_sql(sql: str) -> str:
    """Extracts semantic view names actually used in the generated SQL."""
    if not sql:
        return "none"
    views = []
    for v in ("v_daily_revenue", "v_orders", "v_order_lines"):
        if re.search(rf"\b{v}\b", sql, re.IGNORECASE):
            views.append(v)
    return ", ".join(views) if views else "custom_subquery"


def _retrieve_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node for hybrid semantic few-shot retrieval using Commander's standalone query."""
    plan_obj = state.get("plan")
    search_query = (
        plan_obj.standalone_query
        if (plan_obj and plan_obj.standalone_query)
        else state.get("user_message", "")
    )
    few_shots = retrieve_few_shots(search_query, top_k=3)
    return {
        "few_shots": few_shots,
        "current_step": f"Retrieved {len(few_shots)} relevant few-shot SQL templates for '{search_query[:60]}'"
    }


def _route_after_plan(state: AgentState) -> Literal["retrieve", "discuss", "end_early"]:
    plan_obj = state.get("plan")
    if not plan_obj or plan_obj.intent == "out_of_scope" or plan_obj.needs_clarification:
        return "end_early"
    if plan_obj.intent == "discussion":
        return "discuss"
    return "retrieve"


def _route_after_validate(state: AgentState) -> Literal["execute", "retry_generate", "synthesize"]:
    if state.get("validated_sql"):
        return "execute"
    if state.get("retry_count", 0) < 2:
        return "retry_generate"
    return "synthesize"


def _route_after_execute(state: AgentState) -> Literal["synthesize", "retry_generate"]:
    q_res = state.get("query_result") or {}
    if q_res.get("success", False):
        return "synthesize"
    if state.get("retry_count", 0) < 2:
        return "retry_generate"
    return "synthesize"


def build_agent_graph():
    """
    Compiles the formal LangGraph StateGraph for the Conversational BI Agent.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", plan_query)
    workflow.add_node("retrieve", _retrieve_node)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("synthesize", synthesize_response)
    workflow.add_node("discuss", synthesize_discussion_response)

    workflow.set_entry_point("plan")

    workflow.add_conditional_edges(
        "plan",
        _route_after_plan,
        {
            "retrieve": "retrieve",
            "discuss": "discuss",
            "end_early": END,
        },
    )
    workflow.add_edge("discuss", END)
    workflow.add_edge("retrieve", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    workflow.add_conditional_edges(
        "validate_sql",
        _route_after_validate,
        {
            "execute": "execute_sql",
            "retry_generate": "generate_sql",
            "synthesize": "synthesize",
        },
    )
    workflow.add_conditional_edges(
        "execute_sql",
        _route_after_execute,
        {
            "synthesize": "synthesize",
            "retry_generate": "generate_sql",
        },
    )
    workflow.add_edge("synthesize", END)

    return workflow.compile()


# Singleton compiled LangGraph instance
COMPILED_AGENT_GRAPH = build_agent_graph()


def process_conversational_turn(
    session_id: str,
    user_message: str,
    llm_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
) -> AgentResponse:
    """
    Synchronous processing of a complete conversation turn.
    """
    for event in stream_conversational_turn(
        session_id,
        user_message,
        llm_provider=llm_provider,
        model_name=model_name,
        language=language,
    ):
        if event.get("type") in ("answer", "refusal", "error"):
            return event.get("payload")

    is_en = language == "en"
    return AgentResponse(
        type="error",
        language="en" if is_en else "id",
        summary="Unable to process request." if is_en else "Tidak dapat memproses permintaan.",
        insights=["Conversation flow terminated unexpectedly." if is_en else "Alur percakapan terhenti tanpa hasil final."],
        assumptions=[],
    )


def stream_conversational_turn(
    session_id: str,
    user_message: str,
    llm_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator yielding real-time step progression events for SSE streaming,
    orchestrating the agent nodes with honest runtime telemetry and self-correction retries.
    """
    from backend.app.core.llm_factory import get_langfuse_client

    lf_client = get_langfuse_client()
    lf_trace = None
    if lf_client:
        try:
            lf_trace = lf_client.trace(
                name=f"Chat: {user_message[:50]}",
                session_id=session_id,
                input={"user_message": user_message, "language": language},
            )
        except Exception:
            pass

    steps_log = []
    t_start = time.time()
    turn_req_id = uuid.uuid4().hex[:8]
    set_log_context(session_id=session_id, request_id=turn_req_id, step_name="turn_start")
    logger.info(
        f"Starting conversational turn | lang={language or 'auto'} | provider={llm_provider or 'default'} | "
        f"model={model_name or 'default'} | msg='{user_message[:100]}'"
    )

    def make_step(node: str, title: str, description: str, detail: str = ""):
        elapsed = round((time.time() - t_start) * 1000, 1)
        s = {
            "node": node,
            "title": title,
            "description": description,
            "detail": detail,
            "elapsed_ms": elapsed,
        }
        steps_log.append(s)
        lvl = logging.WARNING if ("DIBLOKIR" in detail or "INVALID" in detail or "GAGAL" in detail) else logging.INFO
        log_step_event(node=node, title=title, detail=detail, elapsed_ms=elapsed, level=lvl)
        if lf_trace:
            try:
                span = lf_trace.span(
                    name=title,
                    input={"description": description, "detail": detail},
                )
                span.end()
            except Exception:
                pass
        return {"type": "step", **s}

    # Step 1: Input Guardrail Check
    guard_res = check_input_safety(user_message, language=language)
    if not guard_res.is_safe:
        is_en_guard = (language or "").lower() == "en"
        yield make_step(
            "guard_input",
            "Input Guardrails",
            "Memeriksa keamanan dan validitas pertanyaan",
            f"DIBLOKIR ({guard_res.violation_type}): {guard_res.refusal_reason}",
        )
        refusal_resp = AgentResponse(
            type="refusal",
            language="en" if is_en_guard else "id",
            summary=guard_res.refusal_reason or "Permintaan tidak dapat diproses.",
            insights=(
                [
                    "This system enforces multi-layered security guardrails (Read-Only role, credential isolation, and AST validation).",
                    guard_res.suggested_alternative
                    or "Please select one of the verified business analytics queries below:",
                ]
                if is_en_guard
                else [
                    "Sistem menerapkan pengamanan berlapis (mode Read-Only, isolasi kredensial, serta validasi AST SQL).",
                    guard_res.suggested_alternative
                    or "Silakan pilih salah satu analisis data bisnis yang tersedia di bawah ini:",
                ]
            ),
            assumptions=[
                "Security Guardrail Enforced: Blocked unauthorized credential, DDL/DML, or prompt-override request."
                if is_en_guard
                else "Pengamanan Berlapis Aktif: Menolak akses kredensial internal, modifikasi data (DDL/DML), atau injeksi instruksi."
            ],
            clarification=ClarificationPayload(
                question=(
                    "Explore safe, verified business analytics queries instead:"
                    if is_en_guard
                    else "Jalankan salah satu analisis data bisnis resmi berikut:"
                ),
                options=(
                    [
                        {"label": "MTD GMV for Java Region", "value": "MTD GMV for Java region?"},
                        {"label": "Top 5 Products by Revenue Last Month", "value": "Top 5 products by revenue last month?"},
                        {"label": "Cancel Rate This Month", "value": "Cancel rate this month?"},
                    ]
                    if is_en_guard
                    else [
                        {"label": "GMV MTD untuk Region Jawa", "value": "GMV MTD untuk region Jawa?"},
                        {"label": "Top 5 Produk Revenue Tertinggi Bulan Lalu", "value": "Top 5 produk berdasarkan revenue bulan lalu?"},
                        {"label": "Cancel Rate Bulan Ini", "value": "Cancel rate bulan ini?"},
                    ]
                ),
            ),
            trace={"steps": steps_log, "total_duration_ms": round((time.time() - t_start) * 1000, 1)},
        )
        if lf_trace and lf_client:
            try:
                lf_trace.update(output={"refusal": refusal_resp.summary}, level="WARNING")
                lf_client.flush()
            except Exception:
                pass
        yield {"type": "refusal", "payload": refusal_resp}
        return

    yield make_step(
        "guard_input",
        "Input Guardrails",
        "Memeriksa keamanan dan validitas pertanyaan",
        "LOLOS: Bebas dari pola SQL injection, prompt override, dan instruksi DDL/DML",
    )

    # Step 2: Load Context from Session Store
    session_data = session_store.get_session(session_id)
    prev_plan = session_data.get("prev_plan")
    prev_digest = session_data.get("prev_result_digest", {})
    history = list(session_data.get("history", []))
    ctx_detail = f"{len(history) // 2} putaran percakapan sebelumnya"
    if prev_digest.get("top_city"):
        ctx_detail += f" | Entitas tersimpan: top_city={prev_digest['top_city']}"
    yield make_step(
        "load_context",
        "Context & Session Memory",
        "Memuat riwayat dan konteks percakapan sebelumnya",
        ctx_detail,
    )

    state: AgentState = {
        "session_id": session_id,
        "user_message": user_message,
        "language": language or "",
        "prev_plan": prev_plan,
        "prev_result_digest": prev_digest,
        "history": history,
        "retry_count": 0,
        "llm_provider": llm_provider,
        "model_name": model_name,
    }

    # Step 3: Commander Routing, Contextual Query Rewriting & Semantic Planning
    plan_out = plan_query(state)
    state.update(plan_out)
    plan_obj = state.get("plan")
    resolved_lang = state.get("language") or "id"
    is_en = resolved_lang == "en"

    if plan_obj:
        metrics_str = ", ".join(plan_obj.metrics) if plan_obj.metrics else "revenue"
        dims_str = ", ".join(plan_obj.dimensions) if plan_obj.dimensions else "none (aggregate)"
        filters_str = (
            ", ".join(f"{f.field} {f.operator} {f.value}" for f in plan_obj.filters)
            if plan_obj.filters
            else "none"
        )
        followup_str = (
            f" | Follow-up ({', '.join(plan_obj.inherited_fields)})"
            if plan_obj.is_follow_up
            else ""
        )
        win_range = (
            f"({plan_obj.start_date}..{plan_obj.end_date})"
            if (plan_obj.start_date and plan_obj.end_date)
            else "(All-Time)"
        )
        rewritten_str = (
            f" | Rewritten: '{plan_obj.standalone_query}'"
            if (plan_obj.standalone_query and plan_obj.standalone_query != user_message)
            else ""
        )
        intent_desc = (
            f"Specialist: {plan_obj.specialist_agent} | Intent: {plan_obj.intent} | "
            f"Metrics: [{metrics_str}] | GroupBy: [{dims_str}] | "
            f"Filters: [{filters_str}] | Window: {plan_obj.time_window_label} "
            f"{win_range}{followup_str}{rewritten_str}"
        )
    else:
        intent_desc = "Query Plan tersusun"

    yield make_step(
        "plan",
        "Commander & Semantic Planner",
        "Melakukan contextual query rewriting, menentukan sub-agent spesialis, metrik, dimensi, dan periode waktu",
        intent_desc,
    )

    # Handle Out-of-Scope Queries
    if plan_obj and plan_obj.intent == "out_of_scope":
        refusal_resp = AgentResponse(
            type="refusal",
            language=resolved_lang,
            summary=(
                "Sorry, your question is outside the scope of retail business and transaction analytics. "
                "As a Conversational BI assistant, I can only analyze sales performance, revenue, products, and store branches."
                if is_en
                else "Maaf, pertanyaan Anda berada di luar cakupan analitik bisnis dan transaksi ritel. "
                "Sebagai asisten Conversational BI, saya hanya dapat mengakses data terkait performa penjualan, revenue, produk, dan toko cabang."
            ),
            insights=(
                [
                    "This system connects directly to the PostgreSQL analytical transaction database (not a general web search engine).",
                    "Information about public figures, politics, general news, weather, or trivia is not stored in the database.",
                    "Please select one of the business analytics queries below:",
                ]
                if is_en
                else [
                    "Sistem ini terhubung langsung dengan basis data analitik transaksi PostgreSQL (bukan mesin pencari web umum).",
                    "Data mengenai figur publik, politik, berita, cuaca, atau pengetahuan umum tidak tersedia dalam database.",
                    "Silakan ajukan pertanyaan seputar analitik penjualan ritel melalui tombol rekomendasi di bawah ini:",
                ]
            ),
            assumptions=["Domain Scope Guardrail: Enforcing enterprise retail analytics boundary."],
            clarification=ClarificationPayload(
                question=(
                    "Recommended business analytics queries you can run:"
                    if is_en
                    else "Rekomendasi analisis data bisnis yang dapat Anda jalankan:"
                ),
                options=[
                    {"label": "Top 5 Produk Revenue Tertinggi Bulan Lalu", "value": "Top 5 produk berdasarkan revenue bulan lalu"},
                    {"label": "GMV MTD Region Jawa", "value": "GMV MTD untuk region Jawa"},
                    {"label": "Cancel Rate Bulan Ini", "value": "Cancel rate bulan ini?"},
                    {"label": "Perbandingan POS vs E-Commerce", "value": "Revenue POS vs E-commerce minggu ini?"},
                ],
            ),
            trace={"steps": steps_log, "total_duration_ms": round((time.time() - t_start) * 1000, 1)},
        )
        if lf_trace and lf_client:
            try:
                lf_trace.update(output={"refusal": refusal_resp.summary}, level="DEFAULT")
                lf_client.flush()
            except Exception:
                pass
        yield {"type": "refusal", "payload": refusal_resp}
        return

    # Handle Ambiguous Queries Needing Clarification
    if plan_obj and plan_obj.needs_clarification:
        clarification_resp = AgentResponse(
            type="clarification",
            language=resolved_lang,
            summary=plan_obj.clarification_question
            or (
                "Your question requires metric or dimension clarification."
                if is_en
                else "Pertanyaan Anda memerlukan klarifikasi parameter analitik."
            ),
            insights=(
                [
                    "The query contains ambiguous business terms that require specific metric selection.",
                    "Click one of the options below to execute the exact analysis:",
                ]
                if is_en
                else [
                    "Pertanyaan mengandung parameter analitis yang membutuhkan spesifikasi metrik.",
                    "Silakan klik salah satu opsi di bawah ini untuk langsung menjalankan analisis yang tepat:",
                ]
            ),
            assumptions=[
                "No unilateral assumptions made on ambiguous KPIs to preserve data integrity."
                if is_en
                else "Sistem tidak melakukan asumsi sepihak demi menjamin integritas data analitik."
            ],
            clarification=ClarificationPayload(
                question=plan_obj.clarification_question
                or (
                    "Select the analytical parameter to run:"
                    if is_en
                    else "Pilih parameter analisis yang ingin dijalankan:"
                ),
                options=plan_obj.clarification_options,
            ),
            trace={"steps": steps_log, "total_duration_ms": round((time.time() - t_start) * 1000, 1)},
        )
        if lf_trace and lf_client:
            try:
                lf_trace.update(output={"clarification": clarification_resp.summary}, level="DEFAULT")
                lf_client.flush()
            except Exception:
                pass
        yield {"type": "answer", "payload": clarification_resp}
        return

    # Handle Conversational Discussion & Advisory Mode (ConversationalAdvisorSpecialist)
    if plan_obj and plan_obj.intent == "discussion":
        disc_out = synthesize_discussion_response(state)
        state.update(disc_out)
        disc_resp: AgentResponse = state["final_response"]
        yield make_step(
            "advisor_discussion",
            "ConversationalAdvisorSpecialist: Analytical Discussion & Advisory",
            "Menyusun penjelasan konseptual, interpretasi metrik, dan rekomendasi strategis berbasis konteks sesi",
            f"Grounded in session context ({len(prev_digest.get('last_rows_sample') or [])} prior rows) | Bahasa: {disc_resp.language.upper()}",
        )
        disc_resp.trace["steps"] = steps_log
        disc_resp.trace["total_duration_ms"] = round((time.time() - t_start) * 1000, 1)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": disc_resp.summary})
        save_data = {
            "prev_plan": prev_plan if prev_plan else plan_obj.model_dump(),
            "prev_result_digest": prev_digest,
            "history": history[-10:],
        }
        session_store.save_session(session_id, save_data)

        if lf_trace and lf_client:
            try:
                lf_trace.update(output={"discussion": disc_resp.summary}, level="DEFAULT")
                lf_client.flush()
            except Exception:
                pass
        yield {"type": "answer", "payload": disc_resp}
        return

    # Step 4: Hybrid Semantic Few-Shot Retrieval
    ret_out = _retrieve_node(state)
    state.update(ret_out)
    few_shots = state.get("few_shots", [])
    if few_shots:
        top_ex = few_shots[0]
        sim_score = top_ex.get("similarity_score", 0.0)
        ret_detail = (
            f"Top-{len(few_shots)} pola diambil | Match teratas: '{top_ex.get('question', '')}' "
            f"(cosine score: {sim_score})"
        )
    else:
        ret_detail = "Tidak ada contoh few-shot yang relevan"
    yield make_step(
        "retrieve_examples",
        "Semantic Few-Shot Retrieval",
        "Mengambil contoh pasangan NL-to-SQL terverifikasi (Vector DB / Hybrid Retrieval)",
        ret_detail,
    )

    # Step 5, 6, 7: SQL Generation -> AST Validation -> DB Execution (with Self-Correction Retry Loop)
    max_retries = 2
    specialist_name = plan_obj.specialist_agent if plan_obj else "AnalyticalSQLSpecialist"
    while True:
        attempt = state.get("retry_count", 0) + 1
        gen_out = generate_sql(state)
        state.update(gen_out)
        raw_sql = state.get("raw_sql") or ""
        used_views = _extract_views_from_sql(raw_sql)
        sql_preview = " ".join(raw_sql.split())[:110]
        yield make_step(
            "generate_sql" if attempt == 1 else f"retry_sql_{attempt - 1}",
            f"{specialist_name}: SQL Compilation" if attempt == 1 else f"{specialist_name}: Self-Correction Retry #{attempt - 1}",
            f"Sub-agent {specialist_name} menyusun query PostgreSQL di atas Semantic Views"
            if attempt == 1
            else "Memperbaiki query SQL berdasarkan umpan balik error AST/Database",
            f"View: {used_views} | SQL: {sql_preview}...",
        )

        # AST Validation
        val_out = validate_sql_node(state)
        state.update(val_out)
        validated_sql = state.get("validated_sql")
        val_errors = state.get("sql_errors") or []

        if validated_sql:
            yield make_step(
                "validate_sql",
                "AST & Security Validation",
                "Memverifikasi keamanan SQL (SELECT-only, tabel & kolom allowlist, outer LIMIT)",
                f"VALID (sqlglot AST): View [{used_views}] & kolom terverifikasi pada allowlist",
            )
        else:
            err_joined = "; ".join(val_errors)
            yield make_step(
                "validate_sql",
                "AST & Security Validation",
                "Memverifikasi keamanan SQL (SELECT-only, tabel & kolom allowlist, outer LIMIT)",
                f"INVALID: {err_joined}",
            )
            if state.get("retry_count", 0) <= max_retries:
                continue
            else:
                break

        # Database Execution
        exec_out = execute_sql_node(state)
        state.update(exec_out)
        q_res = state.get("query_result") or {}
        exec_ok = q_res.get("success", False)
        exec_ms = q_res.get("execution_time_ms", 0)
        row_count = q_res.get("row_count", 0)

        if exec_ok:
            yield make_step(
                "execute_query",
                "Relational Database Execution",
                "Mengeksekusi query read-only pada database analitik",
                f"SUKSES: Dieksekusi dalam {exec_ms}ms ({row_count} baris data dikembalikan)",
            )
            break
        else:
            db_err = q_res.get("error_message") or "Unknown DB error"
            yield make_step(
                "execute_query",
                "Relational Database Execution",
                "Mengeksekusi query read-only pada database analitik",
                f"GAGAL ({exec_ms}ms): {db_err}",
            )
            if state.get("retry_count", 0) <= max_retries:
                continue
            else:
                break

    # Step 8: Grounded Synthesis
    synth_out = synthesize_response(state)
    state.update(synth_out)
    final_resp: AgentResponse = state["final_response"]
    chart_type = final_resp.chart.type if final_resp.chart else "none"
    yield make_step(
        "synthesize",
        "Insight Synthesis & Grounding",
        "Menyusun ringkasan eksekutif, kartu KPI, insight berbasis data, dan asumsi",
        f"Grounded: {len(final_resp.kpis)} KPI card | Chart: {chart_type} | Bahasa: {final_resp.language.upper()}",
    )

    # Attach thinking steps and total duration to final trace
    final_resp.trace["steps"] = steps_log
    final_resp.trace["total_duration_ms"] = round((time.time() - t_start) * 1000, 1)

    # Step 9: Save Context & Result Digest to Session Store
    new_digest = dict(prev_digest)
    rows = (state.get("query_result") or {}).get("rows", [])
    if rows and "store_city" in rows[0]:
        new_digest["top_city"] = rows[0]["store_city"]
    elif rows and "city" in rows[0]:
        new_digest["top_city"] = rows[0]["city"]

    # Extract entity values from current result rows for rich anaphoric follow-ups (e.g., "ini produknya di kategori apa?")
    if rows:
        entity_values: Dict[str, Any] = {}
        for entity_key in ("product_name", "store_name", "store_city", "product_category", "channel", "customer_segment"):
            if entity_key in rows[0]:
                vals = []
                for r in rows[:10]:
                    v = r.get(entity_key)
                    if v and v not in vals:
                        vals.append(v)
                if vals:
                    entity_values[entity_key] = vals
        new_digest["entity_values"] = entity_values
        new_digest["last_rows_sample"] = rows[:5]

    # Store last verified SQL for feedback-driven Vector DB learning
    if state.get("validated_sql") and (state.get("query_result") or {}).get("success"):
        new_digest["last_verified_turn"] = {
            "question": user_message,
            "sql": state.get("validated_sql"),
            "intent": plan_obj.intent if plan_obj else "metric_query",
        }

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": final_resp.summary})

    save_data = {
        "prev_plan": plan_obj.model_dump() if plan_obj else None,
        "prev_result_digest": new_digest,
        "history": history[-10:],
    }
    session_store.save_session(session_id, save_data)
    set_log_context(step_name="persist_session")
    logger.info(
        f"Completed conversational turn in {round((time.time() - t_start) * 1000, 1)}ms | "
        f"specialist={plan_obj.specialist_agent if plan_obj else 'unknown'} | "
        f"rows={len(rows)} | kpis={len(final_resp.kpis)}"
    )

    # Langfuse Trace Final Update
    if lf_trace and lf_client:
        try:
            lf_trace.update(
                output={
                    "summary": final_resp.summary,
                    "sql": final_resp.sql,
                    "kpis": [k.model_dump() for k in final_resp.kpis],
                    "row_count": len(rows),
                    "total_duration_ms": round((time.time() - t_start) * 1000, 1),
                }
            )
            is_valid_sql = bool(state.get("validated_sql"))
            is_exec_ok = bool((state.get("query_result") or {}).get("success", False))
            exec_ms = (state.get("query_result") or {}).get("execution_time_ms", 0)

            lf_client.score(
                trace_id=lf_trace.id,
                name="guardrail_safety",
                value=1.0,
                comment="Input passed regex & AST safety inspection",
            )
            lf_client.score(
                trace_id=lf_trace.id,
                name="sql_validity",
                value=1.0 if is_valid_sql else 0.0,
                comment="sqlglot AST validation passed (read-only allowlist)",
            )
            lf_client.score(
                trace_id=lf_trace.id,
                name="execution_success",
                value=1.0 if is_exec_ok else 0.0,
                comment=f"Database query executed ({exec_ms}ms, {len(rows)} rows)",
            )
            lf_client.flush()
        except Exception:
            pass

    yield {"type": "answer", "payload": final_resp}
