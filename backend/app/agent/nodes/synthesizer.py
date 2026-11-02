"""
Data-Grounded Response Synthesis Node for Conversational BI Agent.
Strictly computes all KPIs, analytical insights, and prescriptive recommendations
from actual query results and structured QueryPlan metadata (Zero Hallucination).
Supports bilingual output ('id' and 'en').
"""

from typing import Dict, Any, List, Optional
from backend.app.agent.state import (
    AgentState,
    AgentResponse,
    KPICard,
    TableData,
    ChartConfig,
    QueryPlan,
    ClarificationPayload,
)


def format_idr(value: float, lang: str = "id") -> str:
    """Formats a numeric amount into IDR currency string (bilingual ID/EN)."""
    if abs(value) >= 1_000_000_000:
        unit = "Billion" if lang == "en" else "Miliar"
        prefix = "IDR" if lang == "en" else "Rp"
        return f"{prefix} {value / 1_000_000_000:.2f} {unit}"
    elif abs(value) >= 1_000_000:
        unit = "Million" if lang == "en" else "Juta"
        prefix = "IDR" if lang == "en" else "Rp"
        return f"{prefix} {value / 1_000_000:.2f} {unit}"
    else:
        prefix = "IDR" if lang == "en" else "Rp"
        formatted = f"{value:,.0f}" if lang == "en" else f"{value:,.0f}".replace(",", ".")
        return f"{prefix} {formatted}"


def _describe_active_filters(plan: QueryPlan, lang: str = "id") -> str:
    """Builds a human-readable description of active dimension filters (including negation) from QueryPlan."""
    if not plan or not plan.filters:
        return ""
    parts = []
    neg_prefix = "Excluding " if lang == "en" else "Selain "
    for f in plan.filters:
        op = str(f.operator).upper().strip()
        if op == "NOT IN" and isinstance(f.value, list):
            parts.append(f"{neg_prefix}{', '.join(str(v) for v in f.value)}")
        elif op in ("!=", "NOT_EQUALS", "NEQ"):
            parts.append(f"{neg_prefix}{f.value}")
        elif isinstance(f.value, list):
            parts.append(" vs ".join(str(v) for v in f.value))
        else:
            parts.append(str(f.value))
    return ", ".join(parts)


def _resolve_entity_meta(columns: List[Dict[str, str]], rows: List[Dict[str, Any]], lang: str = "id") -> tuple[str, str]:
    """
    Determines the primary entity column name and its human-readable label (ID/EN)
    from the result set columns.
    """
    col_names = [c["name"] for c in columns]
    entity_map_id = [
        ("product_name", "Produk"),
        ("store_name", "Toko / Cabang"),
        ("channel", "Channel Penjualan"),
        ("customer_segment", "Segmen Pelanggan"),
        ("store_city", "Kota"),
        ("store_region", "Region"),
        ("product_category", "Kategori Produk"),
    ]
    entity_map_en = [
        ("product_name", "Product"),
        ("store_name", "Store"),
        ("channel", "Sales Channel"),
        ("customer_segment", "Customer Segment"),
        ("store_city", "City"),
        ("store_region", "Region"),
        ("product_category", "Product Category"),
    ]
    mapping = entity_map_en if lang == "en" else entity_map_id
    for col_key, label in mapping:
        if col_key in col_names:
            return col_key, label
    first_col = col_names[0] if col_names else "entity"
    return first_col, first_col.replace("_", " ").title()


def synthesize_response(state: AgentState) -> Dict[str, Any]:
    plan: QueryPlan = state.get("plan") or QueryPlan()
    q_res = state.get("query_result")
    sql = state.get("validated_sql") or state.get("raw_sql")
    lang = state.get("language") if state.get("language") in ("id", "en") else "id"
    is_en = lang == "en"

    # Base Assumptions (100% grounded in resolved time window and metric definitions)
    if plan.start_date and plan.end_date:
        time_assumption = (
            f"Time window evaluated: {plan.time_window_label} ({plan.start_date} to {plan.end_date}) in Asia/Jakarta timezone"
            if is_en else
            f"Periode waktu dievaluasi untuk: {plan.time_window_label} ({plan.start_date} s.d. {plan.end_date}) zona waktu Asia/Jakarta"
        )
    else:
        time_assumption = (
            "Time window evaluated: All-Time (entire dataset without date filter) in Asia/Jakarta timezone"
            if is_en else
            "Periode waktu dievaluasi untuk: Seluruh Data (tanpa filter tanggal) zona waktu Asia/Jakarta"
        )
    assumptions: List[str] = [time_assumption]
    if "gmv" in plan.metrics:
        assumptions.append(
            "GMV is calculated as Σ(qty × unit_price − discount) across all order statuses"
            if is_en else
            "GMV dihitung sebagai Σ(qty × unit_price − discount) untuk seluruh status pesanan sesuai spesifikasi"
        )
    if any(m in plan.metrics for m in ("revenue", "margin", "cogs")):
        assumptions.append(
            "Net Revenue & Gross Margin strictly include orders with status = 'Completed'"
            if is_en else
            "Revenue & Margin hanya memperhitungkan transaksi berstatus 'Completed'"
        )
    if plan.is_follow_up and plan.inherited_fields:
        filter_desc = _describe_active_filters(plan, lang)
        if filter_desc:
            assumptions.append(
                f"Inherited active conversation context filters: {filter_desc}"
                if is_en else
                f"Melanjutkan filter konteks percakapan aktif: {filter_desc}"
            )

    # Handle Execution Error
    if not q_res or not q_res.get("success"):
        err = (q_res.get("error_message") if q_res else None) or (
            "An error occurred while executing the query." if is_en else "Terjadi kesalahan saat memproses data."
        )
        resp = AgentResponse(
            type="error",
            language=lang,
            summary=(f"Failed to execute analysis: {err}" if is_en else f"Gagal mengeksekusi analisis: {err}"),
            insights=(
                ["Database query could not be completed.", "Please verify query parameters or try again."]
                if is_en else
                ["Query database tidak berhasil diselesaikan.", "Silakan periksa parameter pertanyaan atau coba kembali."]
            ),
            sql=sql,
            assumptions=assumptions
        )
        return {"final_response": resp, "current_step": "Synthesized Error Response"}

    rows: List[Dict[str, Any]] = q_res.get("rows", [])
    columns: List[Dict[str, str]] = q_res.get("columns", [])
    col_names = [c["name"] for c in columns]

    kpis: List[KPICard] = []
    insights: List[str] = []
    recommendations: List[str] = []
    chart_config = ChartConfig(type="none")

    # Handle Empty Result Set Gracefully
    if not rows:
        filter_str = _describe_active_filters(plan, lang)
        ctx_note = f" ({filter_str})" if filter_str else ""
        summary = (
            f"No transaction records found for period {plan.time_window_label}{ctx_note}."
            if is_en else
            f"Tidak ditemukan data transaksi untuk periode {plan.time_window_label}{ctx_note}."
        )
        insights.append(
            f"Query executed successfully against the database and returned 0 matching rows for {plan.start_date} to {plan.end_date}."
            if is_en else
            f"Query berhasil dieksekusi namun menghasilkan 0 baris data pada rentang {plan.start_date} s.d. {plan.end_date}."
        )
        resp = AgentResponse(
            type="answer",
            language=lang,
            summary=summary,
            kpis=[KPICard(label="Matching Rows" if is_en else "Baris Ditemukan", value=0, format="number")],
            table=TableData(columns=columns, rows=[], truncated=False),
            chart=chart_config,
            insights=insights,
            recommendations=[],
            sql=sql,
            assumptions=assumptions,
            trace={"plan": plan.model_dump(), "row_count": 0}
        )
        return {"final_response": resp, "current_step": "Synthesized Empty Result Response"}

    # -------------------------------------------------------------------------
    # CASE 0: Exploratory / Distinct Entity Listing
    # -------------------------------------------------------------------------
    has_metric_cols = any(
        c in col_names
        for c in ("total_revenue", "total_gmv", "total_margin", "total_cogs", "revenue", "gmv", "margin",
                  "total_products", "total_stores", "total_categories", "total_channels", "cancel_rate_pct", "daily_revenue")
    )
    is_count_metric = any(m in plan.metrics for m in ("product_count", "store_count", "category_count", "channel_count"))

    if (plan.intent == "exploratory" or (columns and not has_metric_cols)) and not is_count_metric:
        first_col = col_names[0]
        val_list = [str(r[first_col]) for r in rows if r.get(first_col) is not None]
        _, dim_label = _resolve_entity_meta(columns, rows, lang)

        summary = (
            f"Found {len(val_list)} distinct {dim_label.lower()} entries: {', '.join(val_list[:10])}."
            if is_en else
            f"Ditemukan {len(val_list)} {dim_label.lower()} unik: {', '.join(val_list[:10])}."
        )
        kpis.append(KPICard(label=f"Total {dim_label}", value=len(val_list), format="number"))
        insights.append(
            f"Database records {len(val_list)} unique values for {dim_label.lower()}."
            if is_en else
            f"Tercatat {len(val_list)} entitas {dim_label.lower()} unik di dalam database."
        )
        assumptions.append(
            "Retrieved via SELECT DISTINCT from the semantic layer."
            if is_en else
            "Data diambil dari daftar nilai unik (SELECT DISTINCT) pada semantic layer."
        )

    # -------------------------------------------------------------------------
    # CASE 1: Anomaly Detection (`v_daily_revenue`)
    # -------------------------------------------------------------------------
    elif plan.intent == "anomaly" or "pct_change_vs_7d_avg" in col_names:
        count_anomalies = len(rows)
        latest = rows[0]
        steepest = min(rows, key=lambda r: float(r.get("pct_change_vs_7d_avg", 0)))
        latest_drop = abs(float(latest.get("pct_change_vs_7d_avg", 0)))
        steepest_drop = abs(float(steepest.get("pct_change_vs_7d_avg", 0)))
        latest_rev = float(latest.get("daily_revenue", 0))
        latest_avg = float(latest.get("avg_revenue_prev_7d", 0))

        summary = (
            f"Detected {count_anomalies} anomaly dates where daily revenue dropped >30% vs the preceding 7-day rolling average ({plan.time_window_label})."
            if is_en else
            f"Ditemukan {count_anomalies} tanggal kejadian anomali penurunan revenue >30% dibandingkan rata-rata bergulir 7 hari sebelumnya ({plan.time_window_label})."
        )
        kpis.append(KPICard(
            label="Anomaly Events" if is_en else "Total Kejadian Anomali",
            value=count_anomalies,
            format="number",
            subtitle="Drop >30% vs 7d avg" if is_en else "Penurunan >30% vs rata-rata 7 hari"
        ))
        kpis.append(KPICard(
            label="Latest Anomaly" if is_en else "Anomali Terbaru",
            value=str(latest.get("order_date")),
            format="text",
            subtitle=f"-{latest_drop:.2f}% ({format_idr(latest_rev, lang)})"
        ))
        kpis.append(KPICard(
            label="Steepest Drop" if is_en else "Penurunan Terdalam",
            value=str(steepest.get("order_date")),
            format="text",
            subtitle=f"-{steepest_drop:.2f}% ({format_idr(float(steepest.get('daily_revenue', 0)), lang)})"
        ))

        insights.append(
            f"Most recent anomaly occurred on {latest.get('order_date')}: daily revenue fell to {format_idr(latest_rev, lang)} (-{latest_drop:.2f}% vs 7-day average of {format_idr(latest_avg, lang)})."
            if is_en else
            f"Anomali terbaru terjadi pada {latest.get('order_date')}: revenue harian turun ke {format_idr(latest_rev, lang)} (-{latest_drop:.2f}% dibanding rata-rata 7 hari sebelumnya sebesar {format_idr(latest_avg, lang)})."
        )
        insights.append(
            f"Steepest contraction occurred on {steepest.get('order_date')} with a {steepest_drop:.2f}% drop (daily revenue {format_idr(float(steepest.get('daily_revenue', 0)), lang)} vs 7-day average {format_idr(float(steepest.get('avg_revenue_prev_7d', 0)), lang)})."
            if is_en else
            f"Penurunan paling tajam tercatat pada {steepest.get('order_date')} sebesar -{steepest_drop:.2f}% (revenue harian {format_idr(float(steepest.get('daily_revenue', 0)), lang)} vs rata-rata 7 hari {format_idr(float(steepest.get('avg_revenue_prev_7d', 0)), lang)})."
        )

        recommendations.append(
            f"Root-Cause Audit: Cross-check order volume, cancellation spikes, and channel availability specifically on {steepest.get('order_date')} and {latest.get('order_date')}."
            if is_en else
            f"Audit Akar Masalah: Periksa volume pesanan, rasio pembatalan, dan performa per channel secara spesifik pada tanggal {steepest.get('order_date')} dan {latest.get('order_date')}."
        )
        recommendations.append(
            "Automated Early Warning: Configure real-time alerting when intraday revenue trails the 7-day rolling baseline by >20%."
            if is_en else
            "Peringatan Dini Otomatis: Terapkan notifikasi otomatis apabila revenue harian berjalan turun >20% dari rata-rata 7 hari sebelumnya."
        )

        chart_config = ChartConfig(
            type="line",
            x_axis="order_date",
            y_axes=["daily_revenue", "avg_revenue_prev_7d"],
            title="Daily Revenue vs 7-Day Rolling Average" if is_en else "Tren Revenue Harian vs Rata-rata 7 Hari"
        )
        assumptions.append(
            "Computed deterministically from view `v_daily_revenue` where daily_revenue < 0.70 × avg_revenue_prev_7d"
            if is_en else
            "Anomali dihitung secara deterministik dari view `v_daily_revenue` (daily_revenue < 70% rata-rata 7 hari kalender sebelumnya)"
        )

    # -------------------------------------------------------------------------
    # CASE 2: Cancel Rate (`v_orders`)
    # -------------------------------------------------------------------------
    elif "cancel_rate" in plan.metrics or "cancel_rate_pct" in col_names:
        row0 = rows[0]
        rate = float(row0.get("cancel_rate_pct", 0.0))
        cancelled = int(row0.get("cancelled_orders", 0))
        total = int(row0.get("total_orders", 0))
        completed_est = total - cancelled
        filter_desc = _describe_active_filters(plan, lang)
        scope_str = f" ({filter_desc})" if filter_desc else ""

        summary = (
            f"Order cancellation rate for {plan.time_window_label}{scope_str} is {rate:.2f}% ({cancelled:,} cancelled out of {total:,} total orders)."
            if is_en else
            f"Cancel rate untuk periode {plan.time_window_label}{scope_str} adalah sebesar {rate:.2f}% ({cancelled:,} dibatalkan dari {total:,} total pesanan)."
        )
        kpis.append(KPICard(
            label="Cancel Rate",
            value=rate,
            format="percentage",
            subtitle=f"{plan.time_window_label}{scope_str}"
        ))
        kpis.append(KPICard(
            label="Cancelled Orders" if is_en else "Pesanan Dibatalkan",
            value=cancelled,
            format="number"
        ))
        kpis.append(KPICard(
            label="Total Orders" if is_en else "Total Pesanan",
            value=total,
            format="number"
        ))

        insights.append(
            f"Out of {total:,} orders placed during {plan.time_window_label}, {cancelled:,} orders were cancelled and {completed_est:,} orders proceeded."
            if is_en else
            f"Dari total {total:,} pesanan pada periode {plan.time_window_label}, sebanyak {cancelled:,} pesanan berstatus Cancelled dan {completed_est:,} pesanan lainnya diproses."
        )
        # Data-grounded threshold check (no blind "<10% normal" claim!)
        if rate < 10.0:
            insights.append(
                f"At {rate:.2f}%, the cancellation rate remains below the 10.0% retail risk threshold."
                if is_en else
                f"Pada angka {rate:.2f}%, tingkat pembatalan berada di bawah batas toleransi risiko operasional ritel (10,0%)."
            )
            recommendations.append(
                "Channel Breakdown: Run a follow-up breakdown of cancel rate by channel or payment method to isolate minor friction points."
                if is_en else
                "Analisis Per Kanal: Lakukan rincian (breakdown) cancel rate per channel atau metode pembayaran untuk memetakan sumber pembatalan."
            )
        else:
            excess = rate - 10.0
            insights.append(
                f"At {rate:.2f}%, the cancellation rate exceeds the 10.0% tolerance benchmark by +{excess:.2f} percentage points."
                if is_en else
                f"Pada angka {rate:.2f}%, tingkat pembatalan melampaui ambang batas normal ritel (10,0%) sebesar +{excess:.2f} poin persentase."
            )
            recommendations.append(
                "Payment & Stock Sync Audit: Investigate payment gateway timeouts and inventory sync delays causing high order cancellations."
                if is_en else
                "Audit Pembayaran & Stok: Evaluasi segera waktu tunggu gateway pembayaran dan akurasi stok untuk menekan tingkat pembatalan."
            )

        assumptions.append(
            "Cancel rate = COUNT(status='Cancelled') / COUNT(total orders) × 100 from `v_orders`"
            if is_en else
            "Cancel rate dihitung dari COUNT(status='Cancelled') / COUNT(total pesanan) × 100 pada view `v_orders`"
        )

    # -------------------------------------------------------------------------
    # CASE 3: Distinct Entity Count Queries
    # -------------------------------------------------------------------------
    elif is_count_metric or any(c.startswith(("total_categor", "total_product", "total_store", "total_channel", "total_kategor", "jumlah_")) for c in col_names):
        count_col = next(
            (c for c in ("total_products", "total_stores", "total_categories", "total_channels", "total_orders") if c in col_names),
            col_names[-1]
        )
        raw_clean = count_col.lower()
        if "categor" in raw_clean or "kategor" in raw_clean or "category_count" in plan.metrics:
            label_clean = "Product Categories" if is_en else "Kategori Produk"
            unit_name = "product categories" if is_en else "kategori produk"
        elif "product" in raw_clean or "produk" in raw_clean or "product_count" in plan.metrics:
            label_clean = "Products" if is_en else "Produk"
            unit_name = "products" if is_en else "produk"
        elif "store" in raw_clean or "toko" in raw_clean or "store_count" in plan.metrics:
            label_clean = "Stores" if is_en else "Toko / Cabang"
            unit_name = "stores" if is_en else "toko cabang"
        elif "channel" in raw_clean or "kanal" in raw_clean or "channel_count" in plan.metrics:
            label_clean = "Sales Channels" if is_en else "Channel Penjualan"
            unit_name = "sales channels" if is_en else "channel penjualan"
        elif "order" in raw_clean or "pesanan" in raw_clean or "order_count" in plan.metrics:
            label_clean = "Orders" if is_en else "Pesanan"
            unit_name = "orders" if is_en else "pesanan"
        else:
            label_clean = count_col.replace("total_", "").replace("jumlah_", "").replace("_", " ").title()
            unit_name = label_clean.lower()

        if len(rows) == 1 and len(col_names) == 1:
            val = int(rows[0].get(count_col, 0))
            summary = (
                f"There are {val:,} distinct {unit_name} recorded ({plan.time_window_label})."
                if is_en else
                f"Tercatat sebanyak {val:,} {unit_name} unik ({plan.time_window_label})."
            )
            kpis.append(KPICard(label=f"Total {label_clean}", value=val, format="number", subtitle=plan.time_window_label))
            insights.append(summary)
        elif col_names[0] == "product_category" and count_col == "total_products":
            dim_col = "product_category"
            num_cats = len(rows)
            total_prods = sum(int(r.get(count_col, 0)) for r in rows)
            cat_names = [str(r.get(dim_col)) for r in rows]
            cat_breakdown_str = ", ".join(
                f"{r.get(dim_col)} ({int(r.get(count_col, 0))} {'products' if is_en else 'produk'})"
                for r in rows
            )
            top_r = rows[0]
            top_cnt = int(top_r.get(count_col, 0))
            top_pct = (top_cnt / total_prods * 100.0) if total_prods > 0 else 0.0

            summary = (
                f"There are {num_cats} product categories encompassing {total_prods} total products: {cat_breakdown_str}."
                if is_en else
                f"Terdapat {num_cats} kategori produk yang mencakup total {total_prods} produk: {cat_breakdown_str}."
            )
            kpis.append(KPICard(
                label="Total Product Categories" if is_en else "Total Kategori Produk",
                value=num_cats,
                format="number",
                subtitle=", ".join(cat_names)
            ))
            kpis.append(KPICard(
                label="Total Products (SKUs)" if is_en else "Total Produk (SKU)",
                value=total_prods,
                format="number",
                subtitle=f"Across {num_cats} categories" if is_en else f"Tersebar di {num_cats} kategori"
            ))
            kpis.append(KPICard(
                label="Largest Category" if is_en else "Kategori Terbanyak",
                value=f"{top_r.get(dim_col)} ({top_cnt})",
                format="text",
                subtitle=f"{top_pct:.1f}% of products" if is_en else f"{top_pct:.1f}% dari total produk"
            ))
            insights.append(summary)
            insights.append(
                f"Note: {num_cats} is the number of distinct product categories ({', '.join(cat_names)}), while {total_prods} is the total number of individual products across those {num_cats} categories."
                if is_en else
                f"Penjelasan: {num_cats} adalah jumlah kategori produk ({', '.join(cat_names)}), sedangkan {total_prods} adalah total keseluruhan item produk yang tersebar di ke-{num_cats} kategori tersebut."
            )
            if len(rows) > 1:
                chart_config = ChartConfig(
                    type="bar",
                    x_axis=dim_col,
                    y_axes=[count_col],
                    title="Products per Product Category" if is_en else "Jumlah Produk per Kategori Produk"
                )
        else:
            dim_col = col_names[0]
            dim_clean = dim_col.replace("_", " ").title()
            top_r = rows[0]
            summary = (
                f"Breakdown of {unit_name} by {dim_clean.lower()} across {len(rows)} groups (top: {top_r.get(dim_col)} with {int(top_r.get(count_col, 0)):,})."
                if is_en else
                f"Rincian jumlah {unit_name} berdasarkan {dim_clean.lower()} mencakup {len(rows)} kelompok (terbanyak: {top_r.get(dim_col)} sebanyak {int(top_r.get(count_col, 0)):,})."
            )
            for r in rows[:3]:
                kpis.append(KPICard(label=str(r.get(dim_col)), value=int(r.get(count_col, 0)), format="number"))
            insights.append(summary)
            if len(rows) > 1:
                chart_config = ChartConfig(type="bar", x_axis=dim_col, y_axes=[count_col], title=f"{label_clean} per {dim_clean}")

    # -------------------------------------------------------------------------
    # CASE 4: Tiering Analysis (Low / Medium / High Tier)
    # -------------------------------------------------------------------------
    elif plan.intent == "tiering" or "revenue_tier" in col_names:
        summary = (
            f"Product revenue distribution across {len(rows)} quantiles (NTILE-3) for {plan.time_window_label}."
            if is_en else
            f"Distribusi revenue produk terbagi menjadi {len(rows)} kelompok kuantil (Low, Medium, High Tier) untuk periode {plan.time_window_label}."
        )
        for r in rows:
            tier_name = str(r.get("revenue_tier", "Tier"))
            min_v = float(r.get("min_revenue", 0))
            max_v = float(r.get("max_revenue", 0))
            cnt = int(r.get("total_products", 0))
            kpis.append(KPICard(
                label=f"{tier_name} ({cnt})",
                value=f"{format_idr(min_v, lang)} - {format_idr(max_v, lang)}",
                format="text",
                subtitle=f"Avg: {format_idr(float(r.get('avg_revenue', 0)), lang)}"
            ))
            insights.append(
                f"{tier_name}: {cnt} products ranging from {format_idr(min_v, lang)} to {format_idr(max_v, lang)} (average {format_idr(float(r.get('avg_revenue', 0)), lang)})."
                if is_en else
                f"{tier_name}: mencakup {cnt} produk dengan rentang {format_idr(min_v, lang)} s.d. {format_idr(max_v, lang)} (rata-rata {format_idr(float(r.get('avg_revenue', 0)), lang)})."
            )
        chart_config = ChartConfig(type="bar", x_axis="revenue_tier", y_axes=["avg_revenue"], title="Average Revenue by Tier" if is_en else "Rata-rata Revenue per Tier")

    # -------------------------------------------------------------------------
    # CASE 5: Single-Row Metric Aggregation (e.g. GMV MTD Jawa, Revenue & Margin FMCG Jawa)
    # -------------------------------------------------------------------------
    elif len(rows) == 1 and plan.intent == "metric_query":
        r0 = rows[0]
        filter_desc = _describe_active_filters(plan, lang)
        scope_label = f" ({filter_desc})" if filter_desc else ""

        has_gmv = "total_gmv" in col_names or "gmv" in col_names
        has_rev = "total_revenue" in col_names or "revenue" in col_names
        has_margin = "total_margin" in col_names or "margin" in col_names
        has_cogs = "total_cogs" in col_names or "cogs" in col_names

        gmv_val = float(r0.get("total_gmv") or r0.get("gmv") or 0.0)
        rev_val = float(r0.get("total_revenue") or r0.get("revenue") or 0.0)
        margin_val = float(r0.get("total_margin") or r0.get("margin") or 0.0)
        cogs_val = float(r0.get("total_cogs") or r0.get("cogs") or 0.0)

        if has_rev and has_margin:
            margin_pct = (margin_val / rev_val * 100.0) if rev_val > 0 else 0.0
            summary = (
                f"For {plan.time_window_label}{scope_label}, Net Revenue reached {format_idr(rev_val, lang)} with Gross Margin of {format_idr(margin_val, lang)} ({margin_pct:.1f}% margin ratio)."
                if is_en else
                f"Pada periode {plan.time_window_label}{scope_label}, capaian Net Revenue adalah {format_idr(rev_val, lang)} dengan Gross Margin sebesar {format_idr(margin_val, lang)} (rasio margin {margin_pct:.1f}%)."
            )
            kpis.append(KPICard(label=f"Net Revenue{scope_label}", value=rev_val, format="currency_idr", subtitle=plan.time_window_label))
            kpis.append(KPICard(label=f"Gross Margin{scope_label}", value=margin_val, format="currency_idr", subtitle=f"Margin Ratio: {margin_pct:.1f}%"))
            insights.append(
                f"Completed transactions generated {format_idr(rev_val, lang)} in Net Revenue and {format_idr(margin_val, lang)} in Gross Margin ({margin_pct:.1f}%)."
                if is_en else
                f"Transaksi berstatus selesai (Completed) membukukan Net Revenue sebesar {format_idr(rev_val, lang)} dan Gross Margin {format_idr(margin_val, lang)} ({margin_pct:.1f}%)."
            )
            insights.append(
                f"Implied cost of goods sold (COGS) is {format_idr(rev_val - margin_val, lang)} ({100.0 - margin_pct:.1f}% of revenue)."
                if is_en else
                f" Struktur beban pokok penjualan (COGS) berada pada {format_idr(rev_val - margin_val, lang)} ({100.0 - margin_pct:.1f}% terhadap revenue)."
            )
            recommendations.append(
                f"City & Store Drill-Down: Break down {filter_desc or 'this segment'} by city (`Breakdown per city`) to identify the highest-margin branches."
                if is_en else
                f"Drill-Down Wilayah: Lakukan rincian per kota (`Breakdown per city`) untuk memetakan cabang dengan kontribusi margin tertinggi."
            )
        elif has_gmv and not has_rev:
            summary = (
                f"Total GMV for {plan.time_window_label}{scope_label} reached {format_idr(gmv_val, lang)}."
                if is_en else
                f"Total GMV pada periode {plan.time_window_label}{scope_label} mencapai {format_idr(gmv_val, lang)}."
            )
            kpis.append(KPICard(label=f"Total GMV{scope_label}", value=gmv_val, format="currency_idr", subtitle=plan.time_window_label))
            insights.append(
                f"Gross Merchandise Value (GMV) recorded for {plan.time_window_label}{scope_label} is {format_idr(gmv_val, lang)} ({gmv_val:,.0f} IDR)."
                if is_en else
                f"Nilai transaksi kotor (GMV) yang tercatat untuk periode {plan.time_window_label}{scope_label} adalah sebesar {format_idr(gmv_val, lang)} (Rp {gmv_val:,.0f}).".replace(",", ".")
            )
            insights.append(
                "GMV aggregates gross transaction value (qty × unit_price − discount) across all order statuses."
                if is_en else
                "Perhitungan GMV mencakup seluruh nilai transaksi kotor (qty × unit_price − discount) pada rentang tanggal yang dipilih."
            )
            recommendations.append(
                "Net Conversion Check: Compare GMV against Completed Net Revenue and Cancel Rate to measure net realization efficiency."
                if is_en else
                "Evaluasi Realisasi Bersih: Bandingkan GMV terhadap Net Revenue (Completed) dan Cancel Rate untuk mengukur efisiensi konversi pesanan."
            )
        elif has_margin and not has_rev:
            summary = (
                f"Total Gross Margin for {plan.time_window_label}{scope_label} is {format_idr(margin_val, lang)}."
                if is_en else
                f"Total Gross Margin untuk periode {plan.time_window_label}{scope_label} adalah {format_idr(margin_val, lang)}."
            )
            kpis.append(KPICard(label=f"Gross Margin{scope_label}", value=margin_val, format="currency_idr", subtitle=plan.time_window_label))
            insights.append(summary)
        else:
            primary_val = rev_val if has_rev else (cogs_val if has_cogs else gmv_val)
            primary_lbl = "Net Revenue" if has_rev else ("Total COGS" if has_cogs else "Total")
            summary = (
                f"{primary_lbl} for {plan.time_window_label}{scope_label} reached {format_idr(primary_val, lang)}."
                if is_en else
                f"Total {primary_lbl} untuk periode {plan.time_window_label}{scope_label} mencapai {format_idr(primary_val, lang)}."
            )
            kpis.append(KPICard(label=f"{primary_lbl}{scope_label}", value=primary_val, format="currency_idr", subtitle=plan.time_window_label))
            insights.append(summary)

        chart_config = ChartConfig(type="none")

    # -------------------------------------------------------------------------
    # CASE 6: Multi-Entity Comparison, Ranking, or Breakdown
    # -------------------------------------------------------------------------
    else:
        entity_col, entity_label = _resolve_entity_meta(columns, rows, lang)
        metric_col = next(
            (c for c in ("total_margin", "total_revenue", "total_gmv", "total_cogs") if c in col_names and (plan.sort_by == c or c in col_names)),
            col_names[-1]
        )
        # Prefer plan.sort_by if present in columns
        if plan.sort_by and plan.sort_by in col_names:
            metric_col = plan.sort_by

        # Defensive sort: ensure rows are strictly ordered by metric_col according to plan.sort_direction
        if len(rows) > 1 and metric_col in col_names:
            try:
                is_desc = (plan.sort_direction or "DESC").upper() != "ASC"
                rows = sorted(rows, key=lambda r: float(r.get(metric_col) or 0.0), reverse=is_desc)
            except (ValueError, TypeError):
                pass

        metric_label = metric_col.replace("total_", "").upper() if metric_col in ("total_gmv", "total_cogs") else metric_col.replace("total_", "").title()
        total_sum = sum(float(r.get(metric_col) or 0.0) for r in rows)

        top_row = rows[0]
        top_name = str(top_row.get(entity_col, "N/A"))
        top_val = float(top_row.get(metric_col) or 0.0)
        top_share = (top_val / total_sum * 100.0) if total_sum > 0 else 0.0
        filter_desc = _describe_active_filters(plan, lang)
        scope_str = f" ({filter_desc})" if filter_desc else ""

        if plan.intent == "comparison" and len(rows) >= 2:
            r1, r2 = rows[0], rows[1]
            n1, n2 = str(r1.get(entity_col)), str(r2.get(entity_col))
            v1, v2 = float(r1.get(metric_col) or 0.0), float(r2.get(metric_col) or 0.0)
            diff = abs(v1 - v2)
            pct_lead = (diff / v2 * 100.0) if v2 > 0 else 0.0
            share1 = (v1 / total_sum * 100.0) if total_sum > 0 else 0.0
            share2 = (v2 / total_sum * 100.0) if total_sum > 0 else 0.0

            summary = (
                f"{entity_label} comparison ({plan.time_window_label}): {n1} ({format_idr(v1, lang)}) vs {n2} ({format_idr(v2, lang)})."
                if is_en else
                f"Perbandingan {entity_label} ({plan.time_window_label}): {n1} ({format_idr(v1, lang)}) vs {n2} ({format_idr(v2, lang)})."
            )
            for r in rows[:4]:
                r_name = str(r.get(entity_col))
                r_val = float(r.get(metric_col) or 0.0)
                r_sh = (r_val / total_sum * 100.0) if total_sum > 0 else 0.0
                kpis.append(KPICard(label=f"{metric_label} {r_name}", value=r_val, format="currency_idr", subtitle=f"{r_sh:.1f}% share"))

            insights.append(
                f"{n1} leads {n2} by {format_idr(diff, lang)} (+{pct_lead:.1f}%), accounting for {share1:.1f}% vs {share2:.1f}% of the combined {format_idr(total_sum, lang)}."
                if is_en else
                f"{n1} mengungguli {n2} dengan selisih {format_idr(diff, lang)} (+{pct_lead:.1f}%), menyumbang porsi {share1:.1f}% berbanding {share2:.1f}% dari total gabungan {format_idr(total_sum, lang)}."
            )
            insights.append(
                f"Evaluated strictly over {plan.time_window_label} ({plan.start_date} to {plan.end_date})."
                if is_en else
                f"Perbandingan dihitung secara aktual pada rentang {plan.time_window_label} ({plan.start_date} s.d. {plan.end_date})."
            )
            recommendations.append(
                f"Channel & Area Optimization: Focus high-margin campaigns on {n1} while evaluating conversion bottlenecks on {n2}."
                if is_en else
                f"Optimalisasi Kanal & Wilayah: Pertahankan performa di {n1} dan evaluasi potensi peningkatan konversi pada {n2}."
            )

        elif plan.sort_direction == "ASC":
            summary = (
                f"Lowest-performing {entity_label.lower()} for {plan.time_window_label}{scope_str} is '{top_name}' with {metric_label} of {format_idr(top_val, lang)}."
                if is_en else
                f"{entity_label} dengan capaian {metric_label.lower()} terendah pada periode {plan.time_window_label}{scope_str} adalah '{top_name}' sebesar {format_idr(top_val, lang)}."
            )
            kpis.append(KPICard(
                label=f"Lowest {entity_label}" if is_en else f"{entity_label} Terendah",
                value=top_name,
                format="text",
                subtitle=format_idr(top_val, lang)
            ))
            insights.append(
                f"'{top_name}' recorded the lowest {metric_label.lower()} ({format_idr(top_val, lang)}) during {plan.time_window_label}."
                if is_en else
                f"'{top_name}' mencatatkan akumulasi {metric_label.lower()} paling rendah ({format_idr(top_val, lang)}) sepanjang periode {plan.time_window_label}."
            )
            recommendations.append(
                f"Inventory & Bundling Review: Evaluate promotional bundling or SKU rationalization for slow-moving {entity_label.lower()} '{top_name}'."
                if is_en else
                f"Evaluasi Bundling & Stok: Tinjau strategi bundling promosi atau penyesuaian kuota stok untuk '{top_name}'."
            )

        elif "product_name_entities" in plan.inherited_fields and "product_category" in col_names:
            cats = []
            pairs = []
            for r in rows:
                pname = str(r.get("product_name", ""))
                pcat = str(r.get("product_category", ""))
                if pcat and pcat not in cats:
                    cats.append(pcat)
                if pname and pcat:
                    pairs.append(f"{pname} ({pcat})")
            cats_str = ", ".join(cats)
            summary = (
                f"The {len(rows)} products from {plan.time_window_label} belong to {len(cats)} categories ({cats_str}): {'; '.join(pairs[:5])}."
                if is_en else
                f"Ke-{len(rows)} produk dari periode {plan.time_window_label} terbagi ke dalam {len(cats)} kategori ({cats_str}): {'; '.join(pairs[:5])}."
            )
            kpis.append(KPICard(
                label="Categories Covered" if is_en else "Kategori Produk",
                value=cats_str,
                format="text",
                subtitle=f"{len(cats)} kategori ({len(rows)} produk)"
            ))
            kpis.append(KPICard(
                label=f"#1 {entity_label}",
                value=top_name,
                format="text",
                subtitle=f"{top_row.get('product_category', '')} • {format_idr(top_val, lang)}"
            ))
            for r in rows[:5]:
                insights.append(
                    f"'{r.get('product_name')}' belongs to category '{r.get('product_category')}' with {metric_label} of {format_idr(float(r.get(metric_col) or 0), lang)}."
                    if is_en else
                    f"Produk '{r.get('product_name')}' berada di kategori '{r.get('product_category')}' dengan {metric_label} {format_idr(float(r.get(metric_col) or 0), lang)}."
                )
            recommendations.append(
                f"Category Strategy: Prioritize category-level merchandising across {cats_str} where your top-performing SKUs are concentrated."
                if is_en else
                f"Strategi Kategori: Fokuskan alokasi kampanye dan ketersediaan stok pada kategori {cats_str} yang mendominasi daftar produk teratas."
            )

        else:
            # Top-N Ranking or Multi-row Breakdown
            if len(rows) == 1:
                summary = (
                    f"Top {entity_label.lower()} for {plan.time_window_label}{scope_str} is '{top_name}' with {metric_label} of {format_idr(top_val, lang)}."
                    if is_en else
                    f"{entity_label} tertinggi pada periode {plan.time_window_label}{scope_str} adalah '{top_name}' dengan {metric_label} sebesar {format_idr(top_val, lang)}."
                )
            else:
                summary = (
                    f"'{top_name}' ranks #1 across {len(rows)} {entity_label.lower()}s for {plan.time_window_label}{scope_str} with {format_idr(top_val, lang)} ({top_share:.1f}% of total {format_idr(total_sum, lang)})."
                    if is_en else
                    f"'{top_name}' menempati peringkat #1 dari {len(rows)} {entity_label.lower()} pada periode {plan.time_window_label}{scope_str} dengan {metric_label} {format_idr(top_val, lang)} ({top_share:.1f}% dari total {format_idr(total_sum, lang)})."
                )

            kpis.append(KPICard(
                label=f"#1 {entity_label}",
                value=top_name,
                format="text",
                subtitle=f"{format_idr(top_val, lang)} ({top_share:.1f}%)" if len(rows) > 1 else format_idr(top_val, lang)
            ))
            if len(rows) > 1:
                kpis.append(KPICard(
                    label=f"Total {metric_label} ({len(rows)} {entity_label})",
                    value=total_sum,
                    format="currency_idr",
                    subtitle=plan.time_window_label
                ))

            # Secondary metric check (e.g., when both revenue and margin are returned)
            if "total_margin" in col_names and "total_revenue" in col_names:
                rev0 = float(top_row.get("total_revenue") or 0.0)
                mar0 = float(top_row.get("total_margin") or 0.0)
                mpct0 = (mar0 / rev0 * 100.0) if rev0 > 0 else 0.0
                insights.append(
                    f"Leader '{top_name}' generated {format_idr(rev0, lang)} in Revenue and {format_idr(mar0, lang)} in Margin ({mpct0:.1f}% margin efficiency)."
                    if is_en else
                    f"Peringkat pertama '{top_name}' menghasilkan Revenue {format_idr(rev0, lang)} dan Margin {format_idr(mar0, lang)} (efisiensi margin {mpct0:.1f}%)."
                )
            else:
                insights.append(
                    f"'{top_name}' contributed {format_idr(top_val, lang)} ({top_share:.1f}% of the group total) in {plan.time_window_label}."
                    if is_en else
                    f"'{top_name}' memberikan kontribusi sebesar {format_idr(top_val, lang)} ({top_share:.1f}% dari total kelompok) pada periode {plan.time_window_label}."
                )

            if len(rows) >= 2:
                second_row = rows[1]
                second_name = str(second_row.get(entity_col, "N/A"))
                second_val = float(second_row.get(metric_col) or 0.0)
                gap = top_val - second_val
                insights.append(
                    f"Ranked #2 is '{second_name}' with {format_idr(second_val, lang)} (a gap of {format_idr(gap, lang)} behind '{top_name}')."
                    if is_en else
                    f"Posisi kedua ditempati oleh '{second_name}' sebesar {format_idr(second_val, lang)} (berjarak {format_idr(gap, lang)} dari '{top_name}')."
                )

            recommendations.append(
                f"Stock & Availability Protection: Maintain optimal safety stock and fulfillment priority for '{top_name}' to sustain peak revenue contribution."
                if is_en else
                f"Prioritas Ketersediaan Stok: Jaga ketersediaan stok pengaman (safety stock) dan distribusi pada '{top_name}' untuk mempertahankan kontribusi utama."
            )

        if len(rows) > 1:
            chart_config = ChartConfig(
                type="bar",
                x_axis=entity_col,
                y_axes=[metric_col],
                title=(
                    f"{metric_label} by {entity_label} ({plan.time_window_label})"
                    if is_en else
                    f"Distribusi {metric_label} per {entity_label} ({plan.time_window_label})"
                )
            )

    # Construct Final AgentResponse
    resp = AgentResponse(
        type="answer",
        language=lang,
        summary=summary,
        kpis=kpis,
        table=TableData(columns=columns, rows=rows, truncated=len(rows) > 50),
        chart=chart_config,
        insights=insights[:4],
        recommendations=recommendations[:3],
        sql=sql,
        assumptions=assumptions,
        trace={"plan": plan.model_dump(), "row_count": len(rows)}
    )
    return {"final_response": resp, "current_step": "Synthesized Grounded Final Answer"}


def synthesize_discussion_response(state: AgentState) -> Dict[str, Any]:
    """
    ConversationalAdvisorSpecialist Node:
    Synthesizes an executive, context-grounded analytical discussion, metric definition/formula
    explanation, benchmark evaluation, or strategic recommendation without re-running a redundant
    SQL query. Preserves full awareness of the previous turn's numbers and provides clickable
    follow-up drill-down options.
    """
    import json
    import re
    from backend.app.core.llm_factory import get_llm

    plan: QueryPlan = state.get("plan") or QueryPlan(intent="discussion")
    user_msg = (state.get("user_message") or "").strip()
    msg_lower = user_msg.lower()
    lang = state.get("language") if state.get("language") in ("id", "en") else "id"
    is_en = lang == "en"

    prev_digest = state.get("prev_result_digest") or {}
    last_rows: List[Dict[str, Any]] = prev_digest.get("last_rows_sample") or []
    first_row = last_rows[0] if last_rows else {}

    active_metrics = list(plan.metrics) if plan.metrics else []
    win_label = plan.time_window_label or ("MTD" if is_en else "Bulan Ini (MTD)")
    filter_desc = _describe_active_filters(plan, lang)
    scope_txt = f" ({filter_desc})" if filter_desc else ""

    summary = ""
    insights: List[str] = []
    recommendations: List[str] = []
    follow_up_options: List[Dict[str, str]] = []

    asks_gmv_vs_rev = (
        ("gmv" in msg_lower and "revenue" in msg_lower)
        or bool(re.search(r'\b(?:bedanya|perbedaan|difference\s+between)\b', msg_lower) and ("gmv" in msg_lower or "revenue" in msg_lower or "margin" in msg_lower))
        or any(k in msg_lower for k in ["apa itu gmv", "artinya gmv", "maksudnya gmv", "apa itu margin", "artinya margin", "apa itu revenue", "artinya revenue", "apa itu cogs", "artinya cogs"])
    )

    # CASE 1: Discussion about Cancel Rate (e.g. "ini berarti apa artinya cancel rate?", "7.13% bagus atau jelek?")
    if not asks_gmv_vs_rev and ("cancel_rate" in active_metrics or "cancel" in msg_lower or "batal" in msg_lower):
        cr_val = first_row.get("cancel_rate_pct")
        canc_cnt = first_row.get("cancelled_orders")
        tot_cnt = first_row.get("total_orders")

        if cr_val is not None and canc_cnt is not None and tot_cnt is not None:
            cr_float = float(cr_val)
            canc_int = int(canc_cnt)
            tot_int = int(tot_cnt)
            proceed_int = max(0, tot_int - canc_int)
            proceed_pct = round(100.0 - cr_float, 2)
            status_eval_id = "masih berada di bawah ambang batas risiko ritel (10,0%), sehingga tergolong terkendali" if cr_float < 10.0 else "melampaui ambang batas risiko ritel (10,0%), sehingga memerlukan intervensi operasional segera"
            status_eval_en = "remains below the 10.0% retail risk threshold (operationally healthy)" if cr_float < 10.0 else "exceeds the 10.0% retail risk threshold (requiring immediate operational review)"

            summary = (
                f"A Cancel Rate of {cr_float:.2f}% in {win_label}{scope_txt} means that out of {tot_int:,} total orders placed, "
                f"{canc_int:,} orders were cancelled (status = 'Cancelled'), while the remaining {proceed_int:,} orders ({proceed_pct:.2f}%) proceeded normally."
                if is_en else
                f"Cancel Rate (Tingkat Pembatalan Pesanan) sebesar {cr_float:.2f}% pada periode {win_label}{scope_txt} berarti dari total {tot_int:,} pesanan yang masuk, "
                f"terdapat {canc_int:,} pesanan yang dibatalkan (status = 'Cancelled'), sedangkan {proceed_int:,} pesanan lainnya ({proceed_pct:.2f}%) berhasil diproses."
            )
            insights = (
                [
                    f"Formula & Semantic Definition: Cancel Rate is calculated as COUNT(orders with status = 'Cancelled') / COUNT(all orders) × 100 from `v_orders` ({canc_int:,} / {tot_int:,} = {cr_float:.2f}%).",
                    f"Benchmark Evaluation: At {cr_float:.2f}%, your cancellation rate {status_eval_en}.",
                    f"Financial Impact (GMV vs Net Revenue): The transaction value of the {canc_int:,} cancelled orders is still included in Gross Merchandise Value (GMV), but is strictly excluded from Net Revenue and Gross Margin."
                ]
                if is_en else
                [
                    f"Definisi & Rumus Perhitungan: Cancel Rate dihitung dengan rumus COUNT(pesanan berstatus 'Cancelled') / COUNT(seluruh pesanan) × 100 pada tabel `v_orders` ({canc_int:,} / {tot_int:,} = {cr_float:.2f}%).",
                    f"Evaluasi Kesehatan Operasional: Pada angka {cr_float:.2f}%, tingkat pembatalan Anda {status_eval_id}.",
                    f"Dampak Finansial (GMV vs Net Revenue): Nilai transaksi dari {canc_int:,} pesanan yang batal tersebut masih tercatat di dalam GMV (nilai transaksi kotor), namun otomatis dikeluarkan dari perhitungan Net Revenue dan Gross Margin."
                ]
            )
        else:
            summary = (
                "Cancel Rate measures the percentage of customer orders that are cancelled before completion relative to total orders placed."
                if is_en else
                "Cancel Rate (Tingkat Pembatalan Pesanan) adalah metrik operasional yang mengukur persentase pesanan pelanggan yang berakhir dibatalkan (status = 'Cancelled') dibandingkan dengan total seluruh pesanan yang masuk."
            )
            insights = (
                [
                    "Formula & Data Source: Calculated from `v_orders` as `COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) * 100.0 / COUNT(*)`.",
                    "Retail Benchmark: In omnichannel retail, a Cancel Rate below 10.0% is considered normal/controlled, while >10.0% indicates stock-out or payment gateway friction.",
                    "Accounting Impact: Cancelled orders are included in GMV (Gross Merchandise Value) but excluded from Net Revenue and Gross Margin."
                ]
                if is_en else
                [
                    "Rumus & Sumber Data: Dihitung dari view `v_orders` dengan formula `COUNT(status = 'Cancelled') / COUNT(total pesanan) × 100`.",
                    "Benchmark Industri Ritel: Pada ritel omnichannel, Cancel Rate di bawah 10,0% tergolong terkendali/sehat, sedangkan di atas 10,0% menandakan adanya friksi stok atau kendala pembayaran.",
                    "Dampak Akuntansi: Pesanan berstatus 'Cancelled' tetap dihitung dalam GMV (Gross Merchandise Value), tetapi tidak diakui sebagai Net Revenue maupun Gross Margin."
                ]
            )

        recommendations = (
            [
                "Channel & City Isolation: Break down the Cancel Rate by sales channel (POS, E-commerce, Marketplace, Mobile App, Social Commerce) or by city to pinpoint where cancellations concentrate.",
                "Inventory Sync & Payment SLA Audit: High digital-channel cancellations typically stem from delayed stock synchronization or expired payment windows."
            ]
            if is_en else
            [
                "Isolasi per Channel & Kota: Lakukan breakdown Cancel Rate berdasarkan channel penjualan (POS, E-commerce, Marketplace, Mobile App, Social Commerce) atau per kota untuk menemukan sumber pembatalan tertinggi.",
                "Audit Sinkronisasi Stok & Pembayaran: Pembatalan pesanan pada kanal digital umumnya dipicu oleh selisih stok gudang (stock-out pasca checkout) atau batas waktu pembayaran yang kedaluwarsa."
            ]
        )
        follow_up_options = (
            [
                {"label": "Breakdown Cancel Rate by Channel (This Month)", "value": "Cancel rate by channel this month?"},
                {"label": "Breakdown Cancel Rate by Region (This Month)", "value": "Cancel rate by region this month?"},
                {"label": "Compare GMV vs Net Revenue (This Month)", "value": "Compare GMV and revenue this month?"}
            ]
            if is_en else
            [
                {"label": "Breakdown Cancel Rate per Channel Bulan Ini", "value": "Breakdown cancel rate per channel bulan ini?"},
                {"label": "Breakdown Cancel Rate per Region Bulan Ini", "value": "Breakdown cancel rate per region bulan ini?"},
                {"label": "Bandingkan GMV vs Net Revenue Bulan Ini", "value": "Bandingkan GMV dan revenue bulan ini?"}
            ]
        )

    # CASE 2: Conceptual Comparison (GMV vs Net Revenue vs Gross Margin)
    elif asks_gmv_vs_rev or any(k in msg_lower for k in ["apa itu gmv", "artinya gmv", "maksudnya gmv", "apa itu margin", "artinya margin", "apa itu revenue", "artinya revenue", "apa itu cogs", "artinya cogs"]):
        summary = (
            "In our enterprise retail semantic layer, GMV, Net Revenue, COGS, and Gross Margin represent distinct stages of transaction realization."
            if is_en else
            "Dalam standar akuntansi analitik ritel pada sistem ini, GMV, Net Revenue, COGS, dan Gross Margin merepresentasikan tahapan realisasi nilai transaksi yang berbeda."
        )
        insights = (
            [
                "GMV (Gross Merchandise Value): Calculated as `Σ(qty × unit_price − discount)` across ALL order statuses (`Completed`, `Cancelled`, and `Returned`). It reflects gross demand volume.",
                "Net Revenue (Realized Sales): Uses the same line-item formula `Σ(qty × unit_price − discount)` but STRICTLY filters for `status = 'Completed'`. Cancelled and returned orders are excluded.",
                "COGS & Gross Margin: `COGS = Σ(qty × unit_cost)` and `Gross Margin = Net Revenue − COGS` (strictly for `status = 'Completed'`), measuring true net profitability."
            ]
            if is_en else
            [
                "GMV (Gross Merchandise Value): Dihitung dengan rumus `Σ(qty × unit_price − discount)` mencakup SELURUH status pesanan (`Completed`, `Cancelled`, dan `Returned`). GMV mencerminkan total nilai permintaan kotor.",
                "Net Revenue (Pendapatan Bersih Terealisasi): Menggunakan rumus item yang sama namun HANYA menghitung pesanan berstatus `Completed` (tidak termasuk pesanan batal atau retur).",
                "COGS & Gross Margin: `COGS (HPP) = Σ(qty × unit_cost)` dan `Gross Margin = Net Revenue − COGS` (khusus status `Completed`), yang mengukur tingkat keuntungan bersih riil."
            ]
        )
        recommendations = (
            [
                "Monitor the GMV-to-Revenue Gap: A widening gap between GMV and Net Revenue signals rising cancellations or returns.",
                "Evaluate Categories by Margin %: Pair Net Revenue with Gross Margin % when reviewing product categories (such as FMCG vs Electronics)."
            ]
            if is_en else
            [
                "Pantau Selisih GMV terhadap Net Revenue: Semakin lebar selisih antara GMV dan Net Revenue menandakan tingginya pesanan yang batal (`Cancelled`) atau diretur (`Returned`).",
                "Evaluasi Kategori Berdasarkan Margin %: Gunakan kombinasi Net Revenue dan Gross Margin saat mengevaluasi performa kategori (seperti FMCG vs Electronics)."
            ]
        )
        follow_up_options = (
            [
                {"label": "MTD GMV for Java Region", "value": "MTD GMV for Java region?"},
                {"label": "MTD Revenue & Margin for FMCG in Java", "value": "MTD Revenue and margin for FMCG in Java?"},
                {"label": "Cancel Rate This Month", "value": "Cancel rate this month?"}
            ]
            if is_en else
            [
                {"label": "Cek GMV MTD Region Jawa", "value": "GMV MTD untuk region Jawa?"},
                {"label": "Cek Revenue & Margin FMCG di Jawa (MTD)", "value": "Revenue dan margin MTD untuk FMCG di Jawa?"},
                {"label": "Cek Cancel Rate Bulan Ini", "value": "Cancel rate bulan ini?"}
            ]
        )

    # CASE 3: Contextual Discussion / Strategy / Interpretation of Previous Data Turn
    elif last_rows:
        # Summarize the key figures from `last_rows` and optionally enrich via LLM
        top_keys = list(first_row.keys())
        rev_val = first_row.get("total_revenue")
        gmv_val = first_row.get("total_gmv")
        mar_val = first_row.get("total_margin")
        entity_name = (
            first_row.get("product_name")
            or first_row.get("store_name")
            or first_row.get("store_city")
            or first_row.get("channel")
            or first_row.get("customer_segment")
            or first_row.get("product_category")
            or first_row.get("store_region")
        )

        if entity_name and rev_val is not None:
            total_rev_all = sum(float(r.get("total_revenue") or 0.0) for r in last_rows)
            top_rev = float(rev_val)
            share_pct = (top_rev / total_rev_all * 100.0) if total_rev_all > 0 else 100.0
            summary = (
                f"Based on the previous analysis for {win_label}{scope_txt}, '{entity_name}' leads with {format_idr(top_rev, lang)} "
                f"({share_pct:.1f}% of the {format_idr(total_rev_all, lang)} total across {len(last_rows)} analyzed groups)."
                if is_en else
                f"Berdasarkan hasil analisis periode {win_label}{scope_txt} sebelumnya, '{entity_name}' merupakan kontributor tertinggi dengan nilai {format_idr(top_rev, lang)} "
                f"({share_pct:.1f}% dari total {format_idr(total_rev_all, lang)} pada {len(last_rows)} kelompok yang dianalisis)."
            )
            insights = (
                [
                    f"Primary Driver Concentration: '{entity_name}' accounts for {share_pct:.1f}% of total realized revenue in the selected view, making it the core anchor of performance.",
                    "Revenue Realization Rule: All figures in this breakdown strictly reflect completed transactions (`status = 'Completed'`), ensuring zero inflation from cancelled orders.",
                    f"Portfolio Distribution: Across the {len(last_rows)} rows analyzed, performance can be further segmented by city, channel, or product category to identify growth pockets."
                ]
                if is_en else
                [
                    f"Konsentrasi Kontributor Utama: '{entity_name}' menyumbang {share_pct:.1f}% dari total revenue pada cakupan ini, menjadikannya penopang utama kinerja.",
                    "Validitas Pendapatan Bersih: Seluruh angka pada hasil ini hanya memperhitungkan transaksi yang telah selesai (`status = 'Completed'`), bebas dari distorsi pesanan batal.",
                    f"Distribusi Portofolio: Dari {len(last_rows)} baris hasil analisis, Anda dapat melakukan pembedahan lanjutan per kota, channel, atau kategori produk untuk melihat potensi pertumbuhan."
                ]
            )
        elif gmv_val is not None or rev_val is not None:
            val_num = float(rev_val if rev_val is not None else gmv_val)
            m_lbl = "Net Revenue" if rev_val is not None else "GMV"
            summary = (
                f"The {m_lbl} figure of {format_idr(val_num, lang)} for {win_label}{scope_txt} represents the aggregate transaction value recorded during the evaluated period."
                if is_en else
                f"Angka {m_lbl} sebesar {format_idr(val_num, lang)} pada periode {win_label}{scope_txt} merepresentasikan akumulasi nilai transaksi yang tercatat selama periode tersebut."
            )
            if mar_val is not None and rev_val:
                m_pct = (float(mar_val) / float(rev_val) * 100.0) if float(rev_val) > 0 else 0.0
                insights.append(
                    f"Profitability Ratio: With Gross Margin at {format_idr(float(mar_val), lang)} ({m_pct:.1f}% of Net Revenue), cost of goods sold (COGS) consumed {100.0 - m_pct:.1f}% of revenue."
                    if is_en else
                    f"Rasio Profitabilitas: Dengan Gross Margin sebesar {format_idr(float(mar_val), lang)} ({m_pct:.1f}% dari Net Revenue), porsi Harga Pokok Penjualan (COGS) adalah {100.0 - m_pct:.1f}%."
                )
            insights.append(
                f"Evaluation Scope: Figures are calculated over {win_label} ({plan.start_date} to {plan.end_date}){scope_txt}."
                if is_en else
                f"Cakupan Evaluasi: Data dihitung untuk rentang waktu {win_label} ({plan.start_date} s.d. {plan.end_date}){scope_txt}."
            )
        else:
            summary = (
                f"From the previous analysis ({ len(last_rows) } rows returned), the data provides a baseline view of your retail operations."
                if is_en else
                f"Berdasarkan hasil data sebelumnya ({len(last_rows)} baris), informasi tersebut memberikan gambaran struktural atas operasional ritel Anda."
            )
            insights = [
                f"Columns analyzed: {', '.join(top_keys)}." if is_en else f"Kolom yang dianalisis: {', '.join(top_keys)}."
            ]

        recommendations = (
            [
                "Granular Drill-Down: Break down the current figure by city (`store_city`) or sales channel (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`) to isolate top-performing branches.",
                "Margin & Assortment Optimization: Focus promotional bundles on high-margin categories and protect stock availability on top-selling SKUs."
            ]
            if is_en else
            [
                "Pembedahan Granular (Drill-Down): Lakukan breakdown dari hasil di atas berdasarkan kota (`per city`) atau channel penjualan (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`) untuk mengidentifikasi cabang terbaik.",
                "Optimasi Margin & Ketersediaan Produk: Fokuskan promosi bundling pada kategori bermargin tinggi dan jaga ketersediaan stok (safety stock) pada produk terlaris."
            ]
        )
        follow_up_options = (
            [
                {"label": "Breakdown by City", "value": "Breakdown per city"},
                {"label": "Breakdown by Sales Channel", "value": "Breakdown per channel"},
                {"label": "Top 5 Products by Revenue", "value": "Top 5 products by revenue last month?"}
            ]
            if is_en else
            [
                {"label": "Breakdown per Kota", "value": "Breakdown per city"},
                {"label": "Breakdown per Channel Penjualan", "value": "Breakdown per channel"},
                {"label": "Lihat Top 5 Produk Revenue Tertinggi", "value": "Top 5 produk berdasarkan revenue bulan lalu?"}
            ]
        )

    # CASE 4: General Advisory / Open Discussion without Prior Turn Rows
    else:
        summary = (
            "As your Enterprise Conversational BI Advisor, I can help you both analyze live database metrics and interpret their business meaning, formulas, and strategic implications."
            if is_en else
            "Sebagai Konsultan & Asisten Conversational BI Anda, saya dapat membantu mengeksekusi data transaksi sekaligus mendiskusikan arti metrik, rumus perhitungan, evaluasi performa, hingga strategi bisnis."
        )
        insights = (
            [
                "Core Financial Metrics Available: GMV (all order statuses), Net Revenue (`status = 'Completed'`), COGS (`qty × unit_cost`), Gross Margin (`Revenue − COGS`), and Cancel Rate (`Cancelled / Total Orders`).",
                "Catalog & Omnichannel Coverage: 28 distinct products across 5 categories (`FMCG`, `Electronics`, `Fashion`, `Home & Living`, `Health & Beauty`), sold across 5 channels (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`).",
                "Interactive Multi-Turn Context: After running any data query, you can ask 'What does this number mean?', 'Is this good or bad?', or 'What strategy should we take?'."
            ]
            if is_en else
            [
                "Metrik Finansial Utama: GMV (seluruh status pesanan), Net Revenue (khusus `status = 'Completed'`), COGS (`qty × unit_cost`), Gross Margin (`Revenue − COGS`), serta Cancel Rate (`Cancelled / Total Pesanan`).",
                "Cakupan Katalog & 5 Kanal: Mencakup 28 produk pada 5 kategori (`FMCG`, `Electronics`, `Fashion`, `Home & Living`, `Health & Beauty`) di 5 kanal (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`).",
                "Diskusi Multi-Turn Interaktif: Setelah menjalankan kueri data apa pun, Anda dapat berdiskusi seperti 'Apa artinya angka ini?', 'Apakah angka ini bagus atau bahaya?', atau 'Strategi apa yang harus dilakukan?'."
            ]
        )
        recommendations = (
            [
                "Start with a Headline KPI: Run one of the baseline queries below, then ask follow-up questions to drill down or discuss strategy."
            ]
            if is_en else
            [
                "Mulai dari Indikator Utama: Jalankan salah satu analisis dasar di bawah ini, lalu ajukan pertanyaan diskusi atau breakdown lanjutan."
            ]
        )
        follow_up_options = (
            [
                {"label": "Cancel Rate This Month", "value": "Cancel rate this month?"},
                {"label": "MTD Revenue & Margin for FMCG in Java", "value": "MTD Revenue and margin for FMCG in Java?"},
                {"label": "Top 5 Products by Revenue Last Month", "value": "Top 5 products by revenue last month?"}
            ]
            if is_en else
            [
                {"label": "Cek Cancel Rate Bulan Ini", "value": "Cancel rate bulan ini?"},
                {"label": "Revenue & Margin FMCG di Jawa (MTD)", "value": "Revenue dan margin MTD untuk FMCG di Jawa?"},
                {"label": "Top 5 Produk Revenue Tertinggi Bulan Lalu", "value": "Top 5 produk berdasarkan revenue bulan lalu?"}
            ]
        )

    assumptions = [
        (
            "Conversational Advisory Mode: Explaining metric definitions, business context, and strategic actions based on verified session data and semantic governance rules."
            if is_en else
            "Mode Diskusi & Konsultasi Analitik: Menjelaskan arti metrik, evaluasi benchmark bisnis, dan rekomendasi strategis berdasarkan konteks data sesi aktif."
        )
    ]

    resp = AgentResponse(
        type="discussion",
        language=lang,
        summary=summary,
        kpis=[],
        table=None,
        chart=ChartConfig(type="none"),
        insights=insights[:4],
        recommendations=recommendations[:3],
        sql=None,
        assumptions=assumptions,
        clarification=ClarificationPayload(
            question=(
                "Continue exploring with one of these analytical drill-downs:"
                if is_en else
                "Lanjutkan diskusi atau eksplorasi data dengan memilih salah satu analisis berikut:"
            ),
            options=follow_up_options,
        ),
        trace={"plan": plan.model_dump(), "row_count": len(last_rows)},
    )
    return {"final_response": resp, "current_step": "Synthesized Conversational Advisory Response"}

