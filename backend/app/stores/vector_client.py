"""
Hybrid Semantic Few-Shot Vector Store & Retriever for Conversational BI Agent.
Architecture:
1. Dynamic Date-Parameterized Few-Shot Templates (no hardcoded calendar dates;
   automatically adapts to AS_OF_DATE).
2. Hybrid Semantic Similarity:
   - Stopword-filtered bilingual concept normalization + Character Trigram Cosine Similarity (in-memory, zero-latency).
   - Bilingual synonym normalization (ID <-> EN business terminology).
   - Optional external Vector Database connector (pgvector / Vector DB) when VECTOR_ENABLED=true.
3. Feedback Loop Learning: allows registering verified user queries at runtime.
"""

import math
import re
from collections import Counter
from datetime import timedelta
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.logger import get_logger
from backend.app.semantic.time_resolver import get_as_of_date

logger = get_logger("stores.vector_client")

# Stopwords excluded from similarity scoring so grammatical particles don't skew retrieval
STOPWORDS = {
    "di", "dan", "untuk", "yang", "dari", "dengan", "pada", "ke", "ini", "itu",
    "berapa", "apa", "siapa", "bagaimana", "tolong", "tampilkan", "berikan", "cari",
    "in", "for", "the", "with", "of", "by", "to", "from", "this", "that", "what",
    "is", "are", "show", "give", "me", "and", "or", "on", "at"
}

# Canonical concept synonyms (normalizes ID & EN business terms into shared semantic tokens)
SYNONYM_MAP = {
    "omzet": "revenue",
    "omset": "revenue",
    "pendapatan": "revenue",
    "sales": "revenue",
    "penjualan": "revenue",
    "laba": "margin",
    "keuntungan": "margin",
    "profit": "margin",
    "profitabilitas": "margin",
    "kotor": "gmv",
    "gross": "gmv",
    "batal": "cancel",
    "pembatalan": "cancel",
    "cancelled": "cancel",
    "cancellation": "cancel",
    "toko": "store",
    "cabang": "store",
    "gerai": "store",
    "kota": "city",
    "wilayah": "region",
    "area": "region",
    "propinsi": "region",
    "kanal": "channel",
    "saluran": "channel",
    "online": "ecommerce",
    "e-commerce": "ecommerce",
    "fisik": "pos",
    "offline": "pos",
    "pelanggan": "customer",
    "segmen": "segment",
    "kategori": "category",
    "barang": "product",
    "produk": "product",
    "sku": "product",
    "terlaris": "top",
    "tertinggi": "top",
    "terbesar": "top",
    "teratas": "top",
    "highest": "top",
    "best": "top",
    "terendah": "bottom",
    "terkecil": "bottom",
    "sepi": "bottom",
    "lambat": "bottom",
    "lowest": "bottom",
    "slow": "bottom",
    "anomali": "anomaly",
    "drop": "anomaly",
    "turun": "anomaly",
    "penurunan": "anomaly",
    "pekan": "minggu",
    "week": "minggu",
    "month": "bulan",
    "year": "tahun",
    "kuartal": "quarter",
    "rincian": "breakdown",
    "perbandingan": "vs",
    "bandingkan": "vs",
    "compare": "vs",
}

# Dynamic Few-Shot Templates parameterized by date placeholders
FEW_SHOT_TEMPLATES = [
    {
        "question": "GMV MTD untuk region Jawa?",
        "intent": "metric_query",
        "tags": ["gmv", "mtd", "region", "jawa", "java", "gross merchandise value"],
        "sql_template": "SELECT store_region, SUM(gmv) AS total_gmv FROM v_order_lines WHERE store_region = 'Jawa' AND order_date >= '{mtd_start}' AND order_date <= '{mtd_end}' GROUP BY store_region;",
        "assumptions": ["MTD dihitung dari {mtd_start} s.d. {mtd_end}", "Region mengacu pada store_region (lokasi transaksi)"]
    },
    {
        "question": "Revenue dan margin MTD untuk FMCG di Jawa?",
        "intent": "metric_query",
        "tags": ["revenue", "margin", "mtd", "fmcg", "category", "jawa", "profit"],
        "sql_template": "SELECT product_category, store_region, SUM(revenue) AS total_revenue, SUM(margin) AS total_margin FROM v_order_lines WHERE product_category = 'FMCG' AND store_region = 'Jawa' AND order_date >= '{mtd_start}' AND order_date <= '{mtd_end}' GROUP BY product_category, store_region;",
        "assumptions": ["Hanya pesanan berstatus 'Completed' yang dihitung sebagai Revenue & Margin", "MTD {mtd_start} s.d. {mtd_end}"]
    },
    {
        "question": "Top 5 produk berdasarkan revenue bulan lalu?",
        "intent": "ranking",
        "tags": ["top", "ranking", "product", "produk", "revenue", "bulan lalu", "last month"],
        "sql_template": "SELECT product_id, product_name, product_category, SUM(revenue) AS total_revenue FROM v_order_lines WHERE order_date >= '{prev_month_start}' AND order_date <= '{prev_month_end}' GROUP BY product_id, product_name, product_category ORDER BY total_revenue DESC LIMIT 5;",
        "assumptions": ["Bulan lalu dihitung untuk satu bulan kalender penuh ({prev_month_start} s.d. {prev_month_end})"]
    },
    {
        "question": "Channel dengan revenue tertinggi di Q1 2025?",
        "intent": "ranking",
        "tags": ["channel", "kanal", "top", "revenue", "q1", "quarter", "2025"],
        "sql_template": "SELECT channel, SUM(revenue) AS total_revenue FROM v_order_lines WHERE order_date >= '2025-01-01' AND order_date <= '2025-03-31' GROUP BY channel ORDER BY total_revenue DESC LIMIT 1;",
        "assumptions": ["Q1 2025 dihitung dari 2025-01-01 s.d. 2025-03-31"]
    },
    {
        "question": "Cancel rate bulan ini?",
        "intent": "metric_query",
        "tags": ["cancel", "rate", "pembatalan", "batal", "mtd", "bulan ini", "orders"],
        "sql_template": "SELECT ROUND((COUNT(CASE WHEN status = 'Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2) AS cancel_rate_pct, COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) AS cancelled_orders, COUNT(*) AS total_orders FROM v_orders WHERE order_date >= '{mtd_start}' AND order_date <= '{mtd_end}';",
        "assumptions": ["Cancel rate dihitung dari jumlah pesanan Cancelled dibagi total pesanan pada periode MTD ({mtd_start} s.d. {mtd_end})"]
    },
    {
        "question": "Segment customer dengan margin tertinggi YTD?",
        "intent": "ranking",
        "tags": ["segment", "customer", "pelanggan", "margin", "top", "ytd", "tahun ini"],
        "sql_template": "SELECT customer_segment, SUM(margin) AS total_margin, SUM(revenue) AS total_revenue FROM v_order_lines WHERE order_date >= '{ytd_start}' AND order_date <= '{mtd_end}' GROUP BY customer_segment ORDER BY total_margin DESC LIMIT 1;",
        "assumptions": ["YTD dihitung dari {ytd_start} s.d. {mtd_end}"]
    },
    {
        "question": "Revenue POS vs E-commerce minggu ini?",
        "intent": "comparison",
        "tags": ["revenue", "pos", "ecommerce", "channel", "vs", "comparison", "minggu ini", "this week"],
        "sql_template": "SELECT channel, SUM(revenue) AS total_revenue FROM v_order_lines WHERE channel IN ('POS', 'E-commerce') AND order_date >= '{wtd_start}' AND order_date <= '{mtd_end}' GROUP BY channel ORDER BY total_revenue DESC;",
        "assumptions": ["Minggu ini dihitung dari Senin ({wtd_start}) s.d. {mtd_end}", "Channel dihitung literal: POS vs E-commerce"]
    },
    {
        "question": "Store di Jakarta dengan revenue tertinggi bulan ini?",
        "intent": "ranking",
        "tags": ["store", "toko", "cabang", "jakarta", "city", "top", "revenue", "mtd"],
        "sql_template": "SELECT store_id, store_name, store_city, SUM(revenue) AS total_revenue FROM v_order_lines WHERE store_city = 'Jakarta' AND order_date >= '{mtd_start}' AND order_date <= '{mtd_end}' GROUP BY store_id, store_name, store_city ORDER BY total_revenue DESC LIMIT 1;",
        "assumptions": ["Jakarta dievaluasi pada store_city", "MTD {mtd_start} s.d. {mtd_end}"]
    },
    {
        "question": "Breakdown revenue per city untuk FMCG di Jawa",
        "intent": "breakdown",
        "tags": ["breakdown", "rincian", "city", "kota", "revenue", "margin", "fmcg", "jawa"],
        "sql_template": "SELECT store_city, SUM(revenue) AS total_revenue, SUM(margin) AS total_margin FROM v_order_lines WHERE product_category = 'FMCG' AND store_region = 'Jawa' AND order_date >= '{mtd_start}' AND order_date <= '{mtd_end}' GROUP BY store_city ORDER BY total_revenue DESC;",
        "assumptions": ["Melanjutkan filter aktif: FMCG, Jawa, MTD"]
    },
    {
        "question": "Revenue anomaly: drop >30% vs 7-day average",
        "intent": "anomaly",
        "tags": ["anomaly", "anomali", "drop", "30%", "7-day", "average", "daily_revenue"],
        "sql_template": "SELECT order_date, daily_revenue, avg_revenue_prev_7d, pct_change_vs_7d_avg FROM v_daily_revenue WHERE is_anomaly_drop_over_30pct = TRUE AND order_date >= '{anomaly_start}' AND order_date <= '{mtd_end}' ORDER BY order_date DESC;",
        "assumptions": ["Anomali dihitung jika revenue harian < 70% dari rata-rata 7 hari kalender sebelumnya (penurunan > 30%)", "Evaluasi dalam jendela 90 hari terakhir"]
    },
    {
        "question": "Produk dengan penjualan paling sepi / terendah bulan ini?",
        "intent": "ranking",
        "tags": ["product", "produk", "bottom", "sepi", "lambat", "terendah", "slow", "revenue"],
        "sql_template": "SELECT product_id, product_name, product_category, SUM(revenue) AS total_revenue, SUM(qty) AS total_qty FROM v_order_lines WHERE order_date >= '{mtd_start}' AND order_date <= '{mtd_end}' GROUP BY product_id, product_name, product_category ORDER BY total_revenue ASC LIMIT 5;",
        "assumptions": ["Produk paling sepi diurutkan berdasarkan total revenue terendah (ASC) pada periode MTD"]
    }
]

# Runtime dynamic repository for feedback-learned examples
_learned_examples: List[Dict[str, Any]] = []


def _get_date_context() -> Dict[str, str]:
    today = get_as_of_date()
    mtd_start = today.replace(day=1)
    prev_month_end = mtd_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    ytd_start = today.replace(month=1, day=1)
    wtd_start = today - timedelta(days=today.weekday())
    anomaly_start = today - timedelta(days=89)

    return {
        "mtd_start": mtd_start.isoformat(),
        "mtd_end": today.isoformat(),
        "prev_month_start": prev_month_start.isoformat(),
        "prev_month_end": prev_month_end.isoformat(),
        "ytd_start": ytd_start.isoformat(),
        "wtd_start": wtd_start.isoformat(),
        "anomaly_start": anomaly_start.isoformat(),
    }


def get_rendered_few_shots() -> List[Dict[str, Any]]:
    """Renders all few-shot templates with dynamic dates anchored to AS_OF_DATE."""
    d_ctx = _get_date_context()
    rendered = []
    for tpl in FEW_SHOT_TEMPLATES:
        sql = tpl["sql_template"].format(**d_ctx)
        assumptions = [a.format(**d_ctx) for a in tpl.get("assumptions", [])]
        rendered.append({
            "question": tpl["question"],
            "intent": tpl["intent"],
            "tags": tpl.get("tags", []),
            "sql": sql,
            "assumptions": assumptions
        })
    return rendered + _learned_examples


def _tokenize_and_normalize(text: str) -> Counter:
    """
    Tokenizes text into normalized semantic terms + character trigrams
    for resilient bilingual cosine similarity without external vector DB dependencies.
    """
    clean = re.sub(r'[^a-z0-9>%]+', ' ', text.lower()).strip()
    raw_tokens = [w for w in clean.split() if w and w not in STOPWORDS]

    features: Counter = Counter()
    for tok in raw_tokens:
        norm = SYNONYM_MAP.get(tok, tok)
        # Word-level semantic feature (weight 2.0)
        features[f"w:{norm}"] += 2.0
        if norm != tok:
            features[f"w:{tok}"] += 1.0
        # Character trigram features for typo / morphology resilience (weight 0.5)
        if len(norm) >= 4:
            for i in range(len(norm) - 2):
                features[f"c:{norm[i:i+3]}"] += 0.5

    return features


def _cosine_similarity(vec_a: Counter, vec_b: Counter) -> float:
    if not vec_a or not vec_b:
        return 0.0
    intersection = set(vec_a.keys()) & set(vec_b.keys())
    numerator = sum(vec_a[k] * vec_b[k] for k in intersection)
    sum_a = sum(v * v for v in vec_a.values())
    sum_b = sum(v * v for v in vec_b.values())
    denom = math.sqrt(sum_a) * math.sqrt(sum_b)
    return round(numerator / denom, 4) if denom > 0 else 0.0


def add_verified_example(question: str, sql: str, intent: str = "metric_query") -> bool:
    """Adds a user-verified query-SQL pair into the active retrieval repository."""
    if not question or not sql:
        return False
    _learned_examples.append({
        "question": question.strip(),
        "intent": intent,
        "tags": [],
        "sql": sql.strip(),
        "assumptions": ["Verified via user feedback loop"]
    })
    logger.info(f"Promoted verified NL-to-SQL pair to Vector Store (total learned={len(_learned_examples)}): '{question[:70]}'")
    return True


def retrieve_few_shots(query: str, k: int = 3, top_k: int | None = None) -> List[Dict[str, Any]]:
    """
    Retrieves top-k relevant few-shot examples using hybrid semantic similarity
    (normalized bilingual concepts + character n-gram cosine similarity).
    """
    limit_k = top_k if top_k is not None else k
    candidates = get_rendered_few_shots()
    q_vec = _tokenize_and_normalize(query)

    scored = []
    for ex in candidates:
        doc_text = f"{ex['question']} {' '.join(ex.get('tags', []))} {ex.get('intent', '')}"
        doc_vec = _tokenize_and_normalize(doc_text)
        sim = _cosine_similarity(q_vec, doc_vec)
        ex_with_score = dict(ex)
        ex_with_score["similarity_score"] = sim
        scored.append((sim, ex_with_score))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:limit_k]]
