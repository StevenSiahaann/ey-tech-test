"""
Semantic SQL Generation Node for Conversational BI Agent.
Combines LLM-driven generation (grounded in Semantic Views, Dynamic Few-Shot Retrieval,
Structured QueryPlan, and AST Self-Correction Feedback) with a complete deterministic
Semantic Plan-to-SQL Compiler fallback.
"""

from pathlib import Path
from typing import Dict, Any, List
from backend.app.agent.state import AgentState, QueryPlan
from backend.app.core.llm_factory import get_llm, get_langfuse_callback
from backend.app.semantic.schema_registry import get_schema_prompt_text
from backend.app.stores.vector_client import retrieve_few_shots

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sql_gen_prompt.md"
_CACHED_SYSTEM_HEADER: str = ""


def _get_system_prompt_header() -> str:
    """Loads the base system prompt header from `prompts/sql_gen_prompt.md`."""
    global _CACHED_SYSTEM_HEADER
    if not _CACHED_SYSTEM_HEADER:
        try:
            _CACHED_SYSTEM_HEADER = _PROMPT_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            _CACHED_SYSTEM_HEADER = (
                "Anda adalah Senior Database Architect PostgreSQL untuk Enterprise Conversational BI.\n"
                "Tugas Anda adalah menghasilkan HANYA kode query SQL SELECT PostgreSQL tunggal yang akurat, aman, dan berkinerja tinggi."
            )
    return _CACHED_SYSTEM_HEADER


def _format_filter_clause(f) -> str:
    """Formats a single FilterItem (`=`, `!=`, `IN`, `NOT IN`) into a valid SQL predicate."""
    op = str(f.operator).upper().strip()
    if op == "IN" and isinstance(f.value, list):
        vals = ", ".join(f"'{v}'" for v in f.value)
        return f"{f.field} IN ({vals})"
    if op == "NOT IN" and isinstance(f.value, list):
        vals = ", ".join(f"'{v}'" for v in f.value)
        return f"{f.field} NOT IN ({vals})"
    if op in ("!=", "NOT_EQUALS", "NEQ"):
        return f"{f.field} != '{f.value}'"
    return f"{f.field} = '{f.value}'"


def compile_sql_from_plan(plan: QueryPlan) -> str:
    """
    Deterministic Semantic Plan-to-SQL Compiler.
    Translates any structured QueryPlan (metrics, dimensions, multi-value filters,
    time windows, sorting, limits) directly into valid PostgreSQL over Semantic Views.
    """
    if not plan:
        return "SELECT SUM(revenue) AS total_revenue FROM v_order_lines;"

    # Build WHERE clauses
    where_parts: List[str] = []
    if plan.start_date and plan.end_date and plan.intent != "exploratory":
        where_parts.append(f"order_date >= '{plan.start_date}' AND order_date <= '{plan.end_date}'")

    for f in plan.filters:
        where_parts.append(_format_filter_clause(f))

    where_str = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    # 1. Anomaly Detection
    if plan.intent == "anomaly":
        anom_where = ["is_anomaly_drop_over_30pct = TRUE"]
        if plan.start_date and plan.end_date:
            anom_where.append(f"order_date >= '{plan.start_date}' AND order_date <= '{plan.end_date}'")
        return (
            "SELECT order_date, daily_revenue, avg_revenue_prev_7d, pct_change_vs_7d_avg "
            f"FROM v_daily_revenue WHERE {' AND '.join(anom_where)} ORDER BY order_date DESC;"
        )

    # 2. Tiering (NTILE)
    if plan.intent == "tiering":
        return (
            "WITH product_rev AS ("
            f"SELECT product_id, product_name, SUM(revenue) AS total_revenue FROM v_order_lines{where_str} "
            "GROUP BY product_id, product_name"
            "), tiered AS ("
            "SELECT product_id, product_name, total_revenue, NTILE(3) OVER (ORDER BY total_revenue ASC) AS bucket FROM product_rev"
            ") "
            "SELECT CASE bucket WHEN 1 THEN 'Low Tier' WHEN 2 THEN 'Medium Tier' ELSE 'High Tier' END AS revenue_tier, "
            "COUNT(*) AS total_products, ROUND(MIN(total_revenue)::numeric, 2) AS min_revenue, "
            "ROUND(MAX(total_revenue)::numeric, 2) AS max_revenue, ROUND(AVG(total_revenue)::numeric, 2) AS avg_revenue "
            "FROM tiered GROUP BY bucket ORDER BY bucket ASC;"
        )

    # 3. Exploratory / Distinct Entity Listing
    if plan.intent == "exploratory":
        dims = list(plan.dimensions) if plan.dimensions else ["product_name"]
        first_dim = dims[0]
        exp_filters = [_format_filter_clause(f) for f in plan.filters]
        exp_where = f" WHERE {' AND '.join(exp_filters)}" if exp_filters else ""

        if dims == ["product_category"] and "product_count" in plan.metrics:
            return (
                f"SELECT product_category, COUNT(DISTINCT product_id) AS total_products "
                f"FROM v_order_lines{exp_where} GROUP BY product_category ORDER BY total_products DESC;"
            )

        cols_str = ", ".join(dims)
        limit_str = f" LIMIT {plan.limit}" if plan.limit else " LIMIT 100"
        return f"SELECT DISTINCT {cols_str} FROM v_order_lines{exp_where} ORDER BY {first_dim} ASC{limit_str};"

    # 4. Cancel Rate (Order-level view `v_orders`)
    if "cancel_rate" in plan.metrics:
        dims = [d for d in plan.dimensions if d in ("channel", "store_region", "store_city", "store_name", "customer_segment")]
        dim_select = f"{', '.join(dims)}, " if dims else ""
        group_by = f" GROUP BY {', '.join(dims)}" if dims else ""
        order_by = " ORDER BY cancel_rate_pct DESC" if dims else ""
        limit_str = f" LIMIT {plan.limit}" if plan.limit else ""
        return (
            f"SELECT {dim_select}"
            "ROUND((COUNT(CASE WHEN status = 'Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2) AS cancel_rate_pct, "
            "COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) AS cancelled_orders, "
            f"COUNT(*) AS total_orders FROM v_orders{where_str}{group_by}{order_by}{limit_str};"
        )

    # 5. Distinct Entity Count Metrics
    count_map = {
        "product_count": ("product_id", "total_products"),
        "store_count": ("store_id", "total_stores"),
        "category_count": ("product_category", "total_categories"),
        "channel_count": ("channel", "total_channels"),
        "order_count": ("order_id", "total_orders"),
    }
    for m_key, (col_id, alias) in count_map.items():
        if m_key in plan.metrics:
            view_name = "v_orders" if m_key == "order_count" else "v_order_lines"
            dims = [d for d in plan.dimensions if d != col_id]
            dim_select = f"{', '.join(dims)}, " if dims else ""
            group_by = f" GROUP BY {', '.join(dims)}" if dims else ""
            order_by = f" ORDER BY {alias} DESC" if dims else ""
            return f"SELECT {dim_select}COUNT(DISTINCT {col_id}) AS {alias} FROM {view_name}{where_str}{group_by}{order_by};"

    # 6. Standard Financial Metric Queries, Rankings, Breakdowns, Comparisons
    metric_exprs: List[str] = []
    if "gmv" in plan.metrics:
        metric_exprs.append("SUM(gmv) AS total_gmv")
    if "revenue" in plan.metrics:
        metric_exprs.append("SUM(revenue) AS total_revenue")
    if "margin" in plan.metrics:
        metric_exprs.append("SUM(margin) AS total_margin")
        # For margin rankings, include total_revenue as secondary context column
        if "revenue" not in plan.metrics and plan.intent in ("ranking", "breakdown"):
            metric_exprs.append("SUM(revenue) AS total_revenue")
    if "cogs" in plan.metrics:
        metric_exprs.append("SUM(cogs) AS total_cogs")

    if not metric_exprs:
        metric_exprs.append("SUM(revenue) AS total_revenue")

    dims = list(plan.dimensions)
    dim_select = f"{', '.join(dims)}, " if dims else ""
    group_str = f" GROUP BY {', '.join(dims)}" if dims else ""

    # Determine ORDER BY
    sort_col = plan.sort_by or ("total_margin" if "margin" in plan.metrics and "revenue" not in plan.metrics else ("total_gmv" if "gmv" in plan.metrics and "revenue" not in plan.metrics else "total_revenue"))
    sort_dir = plan.sort_direction or "DESC"

    order_str = ""
    if len(dims) > 0 or plan.intent in ("ranking", "comparison", "breakdown") or plan.limit:
        order_str = f" ORDER BY {sort_col} {sort_dir}"

    limit_str = f" LIMIT {plan.limit}" if plan.limit else ""

    return f"SELECT {dim_select}{', '.join(metric_exprs)} FROM v_order_lines{where_str}{group_str}{order_str}{limit_str};"


def generate_sql(state: AgentState) -> Dict[str, Any]:
    """
    AI-First Semantic SQL Generator with Deterministic Plan-to-SQL Fallback.
    """
    plan: QueryPlan = state.get("plan")
    user_message = state.get("user_message", "")
    session_id = state.get("session_id", "default")

    # 1. Retrieve schema and dynamic in-context few-shot examples (using Commander's standalone_query when available)
    schema_info = get_schema_prompt_text()
    retrieval_query = (plan.standalone_query if plan and plan.standalone_query else user_message)
    few_shots = state.get("few_shots") or retrieve_few_shots(retrieval_query, top_k=3)

    fs_items = []
    for fs in few_shots:
        fs_items.append(f"Q: {fs['question']}\nSQL: {fs['sql']}")
    few_shot_text = "\n\n".join(fs_items) if fs_items else "No examples available."

    # 2. Extract conversation history & previous result context for multi-turn reasoning
    history = state.get("history") or []
    prev_digest = state.get("prev_result_digest") or {}
    history_text = ""
    if history:
        history_lines = []
        for h in history[-6:]:
            role = "User" if h.get("role") == "user" else "Assistant"
            content = h.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            history_lines.append(f"{role}: {content}")
        last_turn = prev_digest.get("last_verified_turn") or {}
        if last_turn.get("sql"):
            history_lines.append(f"SQL Putaran Sebelumnya: {last_turn['sql']}")
        if prev_digest.get("last_rows_sample"):
            history_lines.append(f"Sampel Hasil Putaran Sebelumnya: {prev_digest['last_rows_sample']}")
        history_text = "Riwayat Percakapan & Konteks Data Sebelumnya:\n" + "\n".join(history_lines) + "\n\n"

    # 3. Format self-correction reflection if retrying after AST/syntax or execution error
    err_feedback = ""
    if state.get("sql_errors"):
        err_feedback = (
            f"\n[PERBAIKAN SELF-CORRECTION]\n"
            f"Query SQL sebelumnya gagal dengan error: {', '.join(state['sql_errors'])}\n"
            f"Query bermasalah: {state.get('raw_sql', '')}\n"
            f"Perbaiki sintaks dan nama kolom agar sesuai dengan skema allowlist PostgreSQL.\n\n"
        )

    # 4. Deterministic Time Window constraint & Active Business Filters
    time_window_instruction = ""
    if plan and plan.start_date and plan.end_date:
        time_window_instruction = (
            f"Wajib gunakan filter periode waktu: order_date >= '{plan.start_date}' AND order_date <= '{plan.end_date}' "
            f"(Label: {plan.time_window_label}).\n"
        )
    else:
        time_window_instruction = (
            "Jangan gunakan filter tanggal (order_date) karena pertanyaan menanyakan data katalog/keseluruhan (All-Time).\n"
        )

    filter_instruction = ""
    if plan and plan.filters:
        f_clauses = [_format_filter_clause(f) for f in plan.filters]
        if f_clauses:
            filter_instruction = f"Wajib gunakan filter bisnis aktif berikut: {' AND '.join(f_clauses)}.\n"

    plan_summary = ""
    if plan:
        dims_hint = ", ".join(plan.dimensions) if plan.dimensions else "Agregat tunggal (tanpa GROUP BY)"
        special_pattern = ""
        if plan.intent == "exploratory" and plan.dimensions == ["product_category"] and "product_count" in plan.metrics:
            special_pattern = (
                "- Pola SQL Target: SELECT product_category, COUNT(DISTINCT product_id) AS total_products "
                "FROM v_order_lines GROUP BY product_category ORDER BY total_products DESC;\n"
            )
        plan_summary = (
            f"Panduan Commander & Rencana Semantik (QueryPlan):\n"
            f"- Sub-Agent Spesialis: {plan.specialist_agent}\n"
            f"- Pertanyaan Kontekstual (Standalone Query): {plan.standalone_query or user_message}\n"
            f"- Intent: {plan.intent}\n"
            f"- Metrik: {', '.join(plan.metrics)}\n"
            f"- Dimensi GROUP BY: {dims_hint}\n"
            f"- Urutan: {plan.sort_by or 'default'} {plan.sort_direction}\n"
            f"- Limit: {plan.limit if plan.limit else 'Tanpa limit khusus'}\n"
            f"{special_pattern}\n"
        )

    # 5. Build prompt
    system_header = _get_system_prompt_header()
    prompt = f"""{system_header}

{schema_info}

## Contoh Pola Query Emas (Few-Shot):
{few_shot_text}

{history_text}{plan_summary}{err_feedback}## Panduan Teknis Kritis:
1. HANYA gunakan perintah SELECT atau CTE (WITH ... SELECT). Dilarang modifikasi data (DDL/DML).
2. Gunakan Semantic View yang tepat:
   - `v_daily_revenue`: WAJIB digunakan jika intent='anomaly' atau pertanyaan menanyakan anomali penurunan revenue >30% (`WHERE is_anomaly_drop_over_30pct = TRUE`).
   - `v_orders`: untuk jumlah pesanan dan cancel rate (`ROUND((COUNT(CASE WHEN status='Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2) AS cancel_rate_pct`).
   - `v_order_lines`: untuk GMV, revenue, cogs, margin, produk, kategori, channel, toko, kota, region, segmen pelanggan.
3. {time_window_instruction}{filter_instruction}4. Gunakan alias metrik standar (wajib persis):
   - `SUM(gmv) AS total_gmv`
   - `SUM(revenue) AS total_revenue`
   - `SUM(margin) AS total_margin`
   - `SUM(cogs) AS total_cogs`
   - `COUNT(DISTINCT product_category) AS total_categories`
   - `COUNT(DISTINCT product_id) AS total_products`
   - `COUNT(DISTINCT store_id) AS total_stores`
   - `COUNT(DISTINCT channel) AS total_channels`
5. Setiap query yang menggunakan GROUP BY pada dimensi entitas WAJIB menyertakan klausa ORDER BY pada metrik utama (DESC untuk tertinggi/umum, ASC untuk terendah) agar baris pertama selalu merupakan peringkat #1 yang valid.
6. Perhatikan Riwayat Percakapan & QueryPlan: jika pengguna bertanya singkat seperti "apa aja?", "ada apa aja?", atau "kategori produknya?", pastikan subjek entitas melanjutkan topik putaran sebelumnya sesuai Dimensi GROUP BY pada QueryPlan.
7. Hasilkan HANYA kode SQL murni tanpa blok markdown ```sql dan tanpa penjelasan tambahan.

Pertanyaan Asli Pengguna: {user_message}
Pertanyaan Kontekstual (Resolved): {plan.standalone_query if plan and plan.standalone_query else user_message}
SQL:"""

    try:
        lf_cb = get_langfuse_callback(session_id=session_id)
        callbacks = [lf_cb] if lf_cb else None
        llm = get_llm(
            temperature=0.0,
            callbacks=callbacks,
            provider_override=state.get("llm_provider"),
            model_override=state.get("model_name")
        )

        res = llm.invoke(prompt)
        content = res.content
        if isinstance(content, list):
            content = content[0].get("text", "") if isinstance(content[0], dict) else getattr(content[0], "text", str(content[0]))

        raw_sql = str(content).replace("```sql", "").replace("```", "").strip()
        if ";" in raw_sql:
            raw_sql = raw_sql.split(";")[0] + ";"
        elif not raw_sql.endswith(";"):
            raw_sql += ";"

        # Post-LLM Semantic Alignment Guardrail:
        # 1. Ensure planned dimensions are not dropped by the LLM (e.g. during short follow-ups like 'apa aja?')
        # 2. Ensure multi-row GROUP BY queries always include ORDER BY
        sql_lower = raw_sql.lower()
        if plan:
            if plan.dimensions and not any(d.lower() in sql_lower for d in plan.dimensions):
                raw_sql = compile_sql_from_plan(plan)
            elif "group by" in sql_lower and "order by" not in sql_lower:
                raw_sql = compile_sql_from_plan(plan)

        return {"raw_sql": raw_sql, "current_step": "Semantic SQL Generated via LLM"}
    except Exception:
        # Compile SQL deterministically from the structured QueryPlan
        compiled_sql = compile_sql_from_plan(plan)
        return {"raw_sql": compiled_sql, "current_step": "Semantic SQL Compiled from Structured QueryPlan"}
