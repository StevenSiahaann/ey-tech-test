"""
Intent Understanding, Semantic Planning, and Context Management Node.
Translates user queries (ID & EN) into a complete, structured QueryPlan:
- Resolves temporal windows with explicit/implicit tracking (prevents time leakage).
- Handles Indonesian morphology (-nya suffixes) and compound nouns ('kategori produk' vs 'produk').
- Extracts all requested metrics, dimensions, multi-value filters, sort order, and limits.
- Performs rich anaphoric follow-up resolution using previous turn entities and plans.
- Serves as Domain Scope & Ambiguity Gatekeeper.
"""

import re
from typing import Dict, Any, Optional, List
from backend.app.agent.state import AgentState, QueryPlan, FilterItem
from backend.app.semantic.time_resolver import resolve_time_window, get_as_of_date
from backend.app.semantic.dimension_catalog import extract_dimension_filters
from backend.app.stores.pg_executor import execute_readonly_sql


def _detect_language(text: str, explicit_lang: Optional[str] = None) -> str:
    if explicit_lang in ("id", "en"):
        return explicit_lang
    t = text.lower()
    en_markers = ["what", "which", "highest", "lowest", "last month", "this month", "this week", "by revenue", "for java", "how many"]
    id_markers = ["untuk", "bulan", "minggu", "tertinggi", "terendah", "berdasarkan", "berapa", "di jawa", "paling", "apa", "ini"]
    en_score = sum(1 for m in en_markers if m in t)
    id_score = sum(1 for m in id_markers if m in t)
    return "en" if en_score > id_score else "id"


def _extract_metrics(msg_lower: str) -> List[str]:
    """Deterministically extracts all requested canonical metrics from the user message."""
    metrics: List[str] = []

    if re.search(r'\b(?:cancel\s+rate|cancellation\s+rate|tingkat\s+pembatalan|rasio\s+pembatalan|rasio\s+cancel)\b', msg_lower):
        metrics.append("cancel_rate")

    if re.search(r'\b(?:gmv|gross\s+merchandise\s+value|nilai\s+transaksi\s+kotor|total\s+transaksi\s+kotor)\b', msg_lower):
        metrics.append("gmv")

    if re.search(r'\b(?:revenue|net\s+revenue|pendapatan|omset|omzet|penjualan)(?:nya)?\b', msg_lower):
        metrics.append("revenue")

    if re.search(r'\b(?:margin|gross\s+margin|laba|profit|keuntungan)(?:nya)?\b', msg_lower):
        metrics.append("margin")

    if re.search(r'\b(?:cogs|hpp|harga\s+pokok|biaya\s+modal|cost\s+of\s+goods)(?:nya)?\b', msg_lower):
        metrics.append("cogs")

    if re.search(r'\b(?:jumlah\s+order|total\s+order|banyaknya\s+pesanan|jumlah\s+pesanan|order\s+count|total\s+orders|berapa\s+order|berapa\s+pesanan)\b', msg_lower):
        metrics.append("order_count")

    # Check category_count BEFORE product_count so "berapa kategori produk" matches category_count, NOT product_count
    if re.search(r'\b(?:jumlah\s+kategori|berapa\s+banyak\s+kategori|berapa\s+kategori|total\s+kategori|category\s+count|how\s+many\s+(?:product\s+)?categories)\b', msg_lower):
        metrics.append("category_count")
    elif re.search(r'\b(?:jumlah\s+produk|berapa\s+banyak\s+produk|berapa\s+produk|total\s+produk|banyak\s+produk|product\s+count|how\s+many\s+products)\b', msg_lower):
        metrics.append("product_count")

    if re.search(r'\b(?:jumlah\s+store|jumlah\s+toko|berapa\s+banyak\s+toko|berapa\s+toko|berapa\s+store|total\s+store|store\s+count|how\s+many\s+stores)\b', msg_lower):
        metrics.append("store_count")

    if re.search(r'\b(?:jumlah\s+channel|berapa\s+channel|total\s+channel|channel\s+count|how\s+many\s+channels)\b', msg_lower):
        metrics.append("channel_count")

    return metrics


def _resolve_top_city_dynamically(filters: List[FilterItem], start_date: str, end_date: str) -> Optional[str]:
    """Queries the database to find the actual #1 city for the active context when digest is missing."""
    where_clauses = []
    if start_date and end_date:
        where_clauses.append(f"order_date >= '{start_date}' AND order_date <= '{end_date}'")
    for f in filters:
        if f.field != "store_city":
            if f.operator == "=":
                where_clauses.append(f"{f.field} = '{f.value}'")
            elif f.operator == "IN" and isinstance(f.value, list):
                vals = ", ".join(f"'{v}'" for v in f.value)
                where_clauses.append(f"{f.field} IN ({vals})")
    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"SELECT store_city, SUM(revenue) AS total_revenue FROM v_order_lines{where_sql} GROUP BY store_city ORDER BY total_revenue DESC LIMIT 1;"
    res = execute_readonly_sql(sql)
    if res.success and res.rows:
        return res.rows[0].get("store_city")
    return None


def _is_anaphoric_or_followup_query(msg_lower: str) -> bool:
    """
    Detects whether the user message references entities, metrics, or results
    from the immediately preceding turn (Indonesian & English deictic/anaphoric markers).
    """
    # Explicit deictic pronouns / references to prior turn
    if re.search(
        r'\b(?:ini|itu|tadi|tersebut|barusan|di\s+atas|yang\s+tadi|yang\s+itu|yang\s+ini|'
        r'produknya|tokonya|kategorinya|kotanya|channelnya|segmennya|datanya|hasilnya|'
        r'these|those|that|above|previous|its|their)\b',
        msg_lower
    ):
        return True

    # Conversational continuation starters
    if re.search(
        r'^(?:kalau|kalo|bagaimana\s+dengan|gimana\s+kalau|gimana\s+dengan|untuk\s+yang|'
        r'lalu|terus|kemudian|dan\s+kalau|coba\s+lihat|what\s+about|how\s+about|and\s+for|now\s+show)\b',
        msg_lower
    ):
        return True

    return False


def plan_query(state: AgentState) -> Dict[str, Any]:
    """
    Semantic & Context-Aware Query Planner.
    1. Normalizes temporal window into concrete date boundaries (with `is_explicit` flag).
    2. Extracts multi-value dimension filters from the live database catalog.
    3. Extracts metrics, dimensions, intent, sort order, and limits.
    4. Safely chains multi-turn context (including entity values from previous rows) on follow-ups.
    """
    msg = state.get("user_message", "").strip()
    msg_lower = msg.lower()
    prev_plan_dict = state.get("prev_plan")
    prev_digest = state.get("prev_result_digest") or {}
    lang = _detect_language(msg, state.get("language"))

    # 1. Resolve Time Window (MTD, YTD, Q1 2025, Bulan Lalu, Minggu Ini, etc.)
    tw = resolve_time_window(msg, base_date=get_as_of_date())

    plan = QueryPlan(
        start_date=tw.start_date.isoformat(),
        end_date=tw.end_date.isoformat(),
        time_window_label=tw.label
    )

    # 2. Dynamic Semantic Entity Linking (Supports single '=' and multi-value 'IN')
    plan.filters.extend(extract_dimension_filters(msg))

    # 3. Extract Metrics & Base Intent
    extracted_metrics = _detect_metrics_and_intent(msg_lower, plan, is_explicit_time=tw.is_explicit)

    # 4. Check for Genuine Conversational Context Chaining (Follow-Up)
    is_breakdown_followup = bool(re.search(
        r'\b(?:breakdown|rincian|per\s+kota|per\s+city|by\s+city|berdasarkan\s+kota|per\s+kategori|per\s+category|per\s+channel|per\s+region)\b',
        msg_lower
    )) and len(msg_lower.split()) <= 7

    is_top_store_followup = (
        any(k in msg_lower for k in ["top 3 store", "top store", "store tertinggi", "toko tertinggi", "3 store teratas"])
        and any(k in msg_lower for k in ["city tertinggi", "kota tertinggi", "top city", "kota tersebut", "kota itu"])
    )

    is_show_all_followup = (
        msg_lower in {
            "sebutkan semuanya", "semuanya", "tampilkan semua", "tampilkan seluruhnya",
            "semua", "seluruhnya", "ada apa lagi", "sisanya", "daftar lengkap", "semua produk",
            "lengkapnya", "lengkapnya apa", "apa saja lengkapnya", "show all", "list all"
        }
    )

    is_anaphoric_followup = _is_anaphoric_or_followup_query(msg_lower)

    # Attribute inquiry about previous turn's entities (e.g. "ini produknya di kategori apa?", "toko tadi di kota mana?")
    is_entity_attribute_followup = bool(
        prev_plan_dict
        and is_anaphoric_followup
        and re.search(
            r'\b(?:kategori\s+apa|di\s+kategori|masuk\s+kategori|what\s+category|which\s+category|'
            r'kota\s+mana|di\s+kota\s+apa|which\s+city|region\s+mana|di\s+region\s+apa|which\s+region|'
            r'channel\s+apa|segmen\s+apa)\b',
            msg_lower
        )
    )

    is_genuine_followup = (
        is_breakdown_followup
        or is_top_store_followup
        or is_show_all_followup
        or is_entity_attribute_followup
        or is_anaphoric_followup
    )

    if prev_plan_dict and is_genuine_followup:
        prev_plan = QueryPlan(**prev_plan_dict) if isinstance(prev_plan_dict, dict) else prev_plan_dict
        plan.is_follow_up = True

        # Merge previous filters that were not overridden by current turn
        current_fields = {f.field for f in plan.filters}
        for pf in prev_plan.filters:
            if pf.field not in current_fields:
                plan.filters.append(pf)
        if prev_plan.filters:
            plan.inherited_fields.append("filters")

        # Inherit metrics if the follow-up did not specify new metrics
        if not extracted_metrics and prev_plan.metrics:
            plan.metrics = list(prev_plan.metrics)
            plan.inherited_fields.append("metrics")

        # Inherit time window ONLY if the user did NOT explicitly specify a time window in this turn
        if not tw.is_explicit and prev_plan.start_date and prev_plan.end_date:
            plan.start_date = prev_plan.start_date
            plan.end_date = prev_plan.end_date
            plan.time_window_label = prev_plan.time_window_label
            plan.inherited_fields.append("time_window")

        # CASE A: Entity Attribute Follow-up (e.g. "ini produknya di kategori apa?" after "Top 5 produk bulan lalu?")
        if is_entity_attribute_followup:
            plan.intent = "breakdown"
            prev_entities = prev_digest.get("entity_values") or {}
            # If previous turn returned specific products, filter directly to those products!
            if prev_entities.get("product_name") and "product_name" not in current_fields:
                prod_list = prev_entities["product_name"]
                plan.filters.append(
                    FilterItem(
                        field="product_name",
                        operator="IN" if len(prod_list) > 1 else "=",
                        value=prod_list if len(prod_list) > 1 else prod_list[0],
                    )
                )
                plan.inherited_fields.append("product_name_entities")
            elif prev_entities.get("store_name") and "store_name" not in current_fields:
                store_list = prev_entities["store_name"]
                plan.filters.append(
                    FilterItem(
                        field="store_name",
                        operator="IN" if len(store_list) > 1 else "=",
                        value=store_list if len(store_list) > 1 else store_list[0],
                    )
                )
                plan.inherited_fields.append("store_name_entities")

            # Ensure requested attribute dimension + parent entity dimension are in SELECT / GROUP BY
            if "kategori" in msg_lower or "category" in msg_lower:
                if "product_name" in prev_plan.dimensions or prev_entities.get("product_name"):
                    plan.dimensions = ["product_name", "product_category"]
                else:
                    plan.dimensions = ["product_category"]
            elif "kota" in msg_lower or "city" in msg_lower:
                if "store_name" in prev_plan.dimensions or prev_entities.get("store_name"):
                    plan.dimensions = ["store_name", "store_city"]
                else:
                    plan.dimensions = ["store_city"]
            elif "region" in msg_lower or "wilayah" in msg_lower:
                plan.dimensions = ["store_name", "store_region"] if "store_name" in prev_plan.dimensions else ["store_region"]
            elif "channel" in msg_lower:
                plan.dimensions = ["channel"]

            if not plan.metrics:
                plan.metrics = prev_plan.metrics or ["revenue"]
            plan.sort_by = prev_plan.sort_by or "total_revenue"
            plan.sort_direction = prev_plan.sort_direction or "DESC"
            return {"plan": plan, "language": lang, "current_step": f"Planned (Follow-up Entity Attribute: {', '.join(plan.dimensions)})"}

        # CASE B: Breakdown Follow-up ("Breakdown per city")
        if is_breakdown_followup:
            plan.intent = "breakdown"
            if "kategori" in msg_lower or "category" in msg_lower:
                plan.dimensions = ["product_category"]
            elif "channel" in msg_lower:
                plan.dimensions = ["channel"]
            elif "region" in msg_lower or "wilayah" in msg_lower:
                plan.dimensions = ["store_region"]
            else:
                plan.dimensions = ["store_city"]
            if not plan.metrics:
                plan.metrics = ["revenue", "margin"]
            plan.sort_by = "total_revenue"
            plan.sort_direction = "DESC"
            return {"plan": plan, "language": lang, "current_step": f"Planned (Follow-up: Breakdown per {plan.dimensions[0]})"}

        # CASE C: Top Store in Top City Follow-up ("Top 3 store dari city tertinggi")
        if is_top_store_followup:
            plan.intent = "ranking"
            plan.dimensions = ["store_id", "store_name", "store_city"]
            if not plan.metrics:
                plan.metrics = ["revenue"]
            plan.sort_by = "total_revenue"
            plan.sort_direction = "DESC"
            m_top = re.search(r'\btop\s+(\d+)\b', msg_lower)
            plan.limit = int(m_top.group(1)) if m_top else 3

            top_city = prev_digest.get("top_city") or _resolve_top_city_dynamically(
                plan.filters, plan.start_date, plan.end_date
            )
            if top_city:
                plan.filters = [f for f in plan.filters if f.field != "store_city"]
                plan.filters.append(FilterItem(field="store_city", operator="=", value=top_city))
            return {"plan": plan, "language": lang, "current_step": f"Planned (Follow-up: Top {plan.limit} store in {top_city or 'top city'})"}

        # CASE D: Show All Follow-up ("Tampilkan semua")
        if is_show_all_followup:
            plan.intent = prev_plan.intent if prev_plan.intent != "clarification_reply" else "exploratory"
            plan.dimensions = list(prev_plan.dimensions)
            plan.limit = None
            return {"plan": plan, "language": lang, "current_step": "Planned (Follow-up: Show All Items)"}

        # CASE E: General Anaphoric Follow-up (e.g., "kalau di Sumatera?", "bagaimana dengan bulan ini?")
        if not plan.dimensions and prev_plan.dimensions:
            plan.dimensions = [d for d in prev_plan.dimensions if d not in current_fields]
            for cf in current_fields:
                if cf not in plan.dimensions:
                    plan.dimensions.append(cf)
            plan.inherited_fields.append("dimensions")
        if plan.intent == "metric_query" and prev_plan.intent in ("ranking", "breakdown", "comparison"):
            plan.intent = prev_plan.intent
            plan.limit = prev_plan.limit

    # 5. Out-of-Scope Domain Guardrail
    OUT_OF_SCOPE_TERMS = [
        "presiden", "menteri", "pemilu", "partai", "dpr", "gubernur", "walikota", "bupati", "raja",
        "ibukota", "ibu kota", "cuaca", "ramalan", "resep", "masak", "lagu", "musik",
        "film", "aktor", "artis", "sepak bola", "pemain", "olahraga", "zodiak", "horoskop",
        "siapa penemu", "siapa pencipta", "cerpen", "pantun", "puisi", "coding", "bikin script",
        "president", "minister", "weather", "recipe", "movie", "song", "football", "who is the",
        "joke", "lelucon", "tebak-tebakan"
    ]
    has_business_intent = bool(extracted_metrics) or bool(plan.filters) or any(k in msg_lower for k in [
        "gmv", "revenue", "margin", "cogs", "penjualan", "sales", "order", "pesanan", "cancel",
        "batal", "produk", "product", "toko", "store", "cabang", "kota", "city", "region",
        "wilayah", "pelanggan", "customer", "channel", "segmen", "segment", "brand", "merk",
        "terlaris", "tertinggi", "terendah", "sepi", "lambat", "ranking", "top", "tier",
        "anomali", "anomaly", "drop", "turun", "kategori", "category", "unit", "qty", "harga"
    ])

    if any(term in msg_lower for term in OUT_OF_SCOPE_TERMS) and not has_business_intent:
        plan.intent = "out_of_scope"
        return {"plan": plan, "language": lang, "current_step": "Out of Scope (Domain Scope Guardrail)"}

    # 6. Ambiguity Gatekeeper: Proactive Clarification Loop
    words = msg_lower.split()
    is_pure_greeting = (
        len(words) <= 3 and any(w in ["halo", "hi", "hey", "pagi", "siang", "sore", "malam", "assalamualaikum", "menu", "bantu", "help", "hello"] for w in words)
    )
    is_vague_request = (
        msg_lower in ["analisis dong", "tolong analisis", "rekomendasi analisis", "apa yang bisa kamu lakukan", "mau tanya data", "cek data", "cek", "analisis", "analyze", "help me analyze"]
    )

    if is_pure_greeting or is_vague_request:
        plan.needs_clarification = True
        plan.intent = "clarification_reply"

        if lang == "en":
            plan.clarification_question = "Which business analytics query would you like to run?"
            plan.clarification_options = [
                {"label": "MTD GMV for Java Region", "value": "MTD GMV for Java region?"},
                {"label": "Top 5 Products by Revenue Last Month", "value": "Top 5 products by revenue last month?"},
                {"label": "MTD Revenue & Margin for FMCG in Java", "value": "MTD Revenue and margin for FMCG in Java?"}
            ]
        else:
            plan.clarification_question = "Silakan pilih salah satu parameter analisis bisnis berikut untuk dijalankan:"
            plan.clarification_options = [
                {"label": "GMV MTD Region Jawa", "value": "GMV MTD untuk region Jawa?"},
                {"label": "Top 5 Produk Berdasarkan Revenue Bulan Lalu", "value": "Top 5 produk berdasarkan revenue bulan lalu?"},
                {"label": "Revenue & Margin FMCG Jawa", "value": "Revenue dan margin MTD untuk FMCG di Jawa?"}
            ]
        return {"plan": plan, "language": lang, "current_step": "Needs Clarification (Proactive Disambiguation)"}

    return {"plan": plan, "language": lang, "current_step": f"Planned (Intent: {plan.intent}, Window: {plan.time_window_label})"}


def _detect_metrics_and_intent(msg_lower: str, plan: QueryPlan, is_explicit_time: bool = False) -> List[str]:
    """
    Populates `plan.metrics`, `plan.intent`, `plan.dimensions`, `plan.limit`,
    `plan.sort_by`, and `plan.sort_direction` deterministically from the user query.
    Returns the raw extracted metrics list before default fallback.
    """
    extracted_metrics = _extract_metrics(msg_lower)
    plan.metrics = list(extracted_metrics)

    # 1. Anomaly Detection Intent
    if re.search(r'\b(?:anomali|anomaly|drop\s*>\s*30%|turun\s*>\s*30%|7-day\s+average)\b', msg_lower):
        plan.intent = "anomaly"
        plan.metrics = ["revenue"]
        plan.dimensions = ["order_date"]
        plan.sort_by = "order_date"
        plan.sort_direction = "DESC"
        return extracted_metrics

    # 2. Tiering Intent
    if re.search(r'\b(?:tier|tiering|kuantil|ntile)\b', msg_lower):
        plan.intent = "tiering"
        if not plan.metrics:
            plan.metrics = ["revenue"]
        plan.dimensions = ["revenue_tier"]
        return extracted_metrics

    # 3. Exploratory / Distinct Listing Intent (when no financial/count metrics are requested)
    if not extracted_metrics and re.search(
        r'\b(?:apa\s+saja|apa\s+aja|sebutkan|daftar|list\s+of|what\s+are\s+the|kategori\s+apa|di\s+kategori\s+apa)\b',
        msg_lower
    ):
        plan.intent = "exploratory"
        if "kategori" in msg_lower or "category" in msg_lower:
            plan.dimensions = ["product_category"]
        elif "store" in msg_lower or "toko" in msg_lower or "cabang" in msg_lower:
            plan.dimensions = ["store_name"]
        elif "channel" in msg_lower or "kanal" in msg_lower:
            plan.dimensions = ["channel"]
        elif "segmen" in msg_lower or "segment" in msg_lower:
            plan.dimensions = ["customer_segment"]
        elif "kota" in msg_lower or "city" in msg_lower:
            plan.dimensions = ["store_city"]
        elif "region" in msg_lower or "wilayah" in msg_lower:
            plan.dimensions = ["store_region"]
        else:
            plan.dimensions = ["product_name"]
        return extracted_metrics

    # 4. Master Catalog Count Queries ("ada berapa kategori produk?", "ada berapa toko?")
    # When counting distinct catalog entities without an explicit time filter, do not restrict to MTD
    is_catalog_count = any(m in plan.metrics for m in ("category_count", "product_count", "store_count", "channel_count"))
    if is_catalog_count and not is_explicit_time:
        plan.start_date = None
        plan.end_date = None
        plan.time_window_label = "Seluruh Data (All-Time)"

    # Default metric to revenue when not explicitly stated
    if not plan.metrics:
        plan.metrics = ["revenue"]

    # 5. Detect Sort Direction (ASC for slow-moving / lowest, DESC for top / highest)
    is_ascending = bool(re.search(
        r'\b(?:paling\s+sepi|paling\s+lambat|terendah|terkecil|paling\s+sedikit|slow\s+moving|slow-moving|lowest|worst|bottom)\b',
        msg_lower
    ))
    plan.sort_direction = "ASC" if is_ascending else "DESC"

    # 6. Detect Dimensions from Question Subject & Active Filters
    # Note: Check compound "kategori produk" / "product category" BEFORE standalone "produk" / "product"
    in_filter_fields = {f.field for f in plan.filters if f.operator == "IN"}
    mentions_category_phrase = bool(re.search(r'\b(?:kategori\s+produk|product\s+categor(?:y|ies)|per\s+kategori|per\s+category|by\s+category|kategori\s+mana|kategori\s+apa|which\s+category)\b', msg_lower))

    if is_catalog_count:
        # For count queries ("ada berapa kategori produk?"), only group by a secondary dimension if explicitly requested ("per region", "per kota")
        if re.search(r'\b(?:per\s+kota|per\s+city|by\s+city)\b', msg_lower):
            plan.dimensions = ["store_city"]
        elif re.search(r'\b(?:per\s+region|per\s+wilayah|by\s+region)\b', msg_lower):
            plan.dimensions = ["store_region"]
        elif re.search(r'\b(?:per\s+kategori|per\s+category|by\s+category)\b', msg_lower) and "category_count" not in plan.metrics:
            plan.dimensions = ["product_category"]
        else:
            plan.dimensions = []
    elif mentions_category_phrase and not re.search(r'\b(?:top\s+\d+\s+produk|produk\s+terlaris|produk\s+tertinggi)\b', msg_lower):
        plan.dimensions = ["product_category"]
    elif re.search(r'\b(?:produk|product|products|sku|item|barang)(?:nya)?\b', msg_lower) and "product_count" not in plan.metrics:
        plan.dimensions = ["product_id", "product_name", "product_category"]
    elif re.search(r'\b(?:store|stores|toko|cabang|gerai)(?:nya)?\b', msg_lower) and "store_count" not in plan.metrics:
        plan.dimensions = ["store_id", "store_name", "store_city"]
    elif re.search(r'\b(?:channel|channels|kanal|saluran)(?:nya)?\b', msg_lower) or "channel" in in_filter_fields:
        if "channel_count" not in plan.metrics:
            plan.dimensions = ["channel"]
    elif re.search(r'\b(?:segment|segments|segmen)(?:nya)?\b', msg_lower) or "customer_segment" in in_filter_fields:
        plan.dimensions = ["customer_segment"]
    elif re.search(r'\b(?:per\s+kota|per\s+city|by\s+city|kota\s+mana|which\s+city|antar\s+kota)\b', msg_lower) or "store_city" in in_filter_fields:
        plan.dimensions = ["store_city"]
    elif re.search(r'\b(?:per\s+region|per\s+wilayah|by\s+region|wilayah\s+mana|which\s+region)\b', msg_lower) or "store_region" in in_filter_fields:
        plan.dimensions = ["store_region"]
    elif "product_category" in in_filter_fields:
        plan.dimensions = ["product_category"]
    elif "cancel_rate" not in plan.metrics and not any(m.endswith("_count") for m in plan.metrics):
        # Include filtered dimensions in SELECT / GROUP BY for clear contextual reporting
        for f in plan.filters:
            if f.field not in plan.dimensions:
                plan.dimensions.append(f.field)

    # 7. Detect Comparison vs Ranking vs Breakdown vs Metric Query
    has_comparison_marker = bool(re.search(r'\b(?:vs\.?|versus|bandingkan|perbandingan|dibanding|compare|compared\s+to)\b', msg_lower)) or bool(in_filter_fields)
    top_n_match = re.search(r'\b(?:top|bottom|teratas|tertinggi|terbesar|terlaris|terendah)\s+(\d+)\b|\b(\d+)\s+(?:produk|product|products|store|stores|toko|channel|kota|city|segmen|segment)?\s*(?:teratas|tertinggi|terbesar|terlaris|terendah|paling\s+sepi)\b', msg_lower)
    has_superlative = bool(re.search(
        r'\b(?:tertinggi|terbesar|terlaris|teratas|paling\s+tinggi|paling\s+besar|paling\s+laku|highest|top|best|most|terendah|paling\s+sepi|paling\s+lambat|lowest|slowest|worst)\b',
        msg_lower
    ))
    has_breakdown_marker = bool(re.search(
        r'\b(?:breakdown|rincian|per\s+kota|per\s+city|per\s+region|per\s+channel|per\s+kategori|per\s+category|per\s+segmen|by\s+city|by\s+region|by\s+channel|by\s+category|by\s+segment)\b',
        msg_lower
    ))

    if has_comparison_marker:
        plan.intent = "comparison"
    elif top_n_match:
        plan.intent = "ranking"
        n_str = top_n_match.group(1) or top_n_match.group(2)
        plan.limit = int(n_str)
    elif has_superlative:
        plan.intent = "ranking"
        plan.limit = 5 if is_ascending and "daftar" in msg_lower else 1
    elif has_breakdown_marker:
        plan.intent = "breakdown"
    else:
        plan.intent = "metric_query"

    # Determine primary sort column
    if "margin" in plan.metrics and "revenue" not in plan.metrics:
        plan.sort_by = "total_margin"
    elif "gmv" in plan.metrics and "revenue" not in plan.metrics:
        plan.sort_by = "total_gmv"
    elif "cancel_rate" in plan.metrics:
        plan.sort_by = "cancel_rate_pct"
    else:
        plan.sort_by = "total_revenue"

    return extracted_metrics
