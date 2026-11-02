"""
Dynamic Semantic Dimension Catalog for Conversational BI Agent.
Discovers and caches discrete categorical dimensions directly from the database
(e.g., store regions, product categories, store cities, channels, customer segments).
Supports multi-value entity linking (IN operator for comparisons like "POS vs E-commerce"
or "Jakarta vs Surabaya") and strict word-boundary matching.
"""

import difflib
import time
import logging
import re
from typing import Dict, List, Set, Optional, Tuple
from backend.app.stores.pg_executor import execute_readonly_sql
from backend.app.agent.state import FilterItem

logger = logging.getLogger(__name__)

# Cache duration in seconds (1 hour default)
CACHE_TTL_SECONDS = 3600

_catalog_cache: Optional[Dict[str, List[str]]] = None
_last_fetch_time: float = 0.0

# Colloquial abbreviations / bilingual aliases mapped to canonical database values
DIMENSION_ALIASES: Dict[str, Dict[str, str]] = {
    "store_region": {
        "java": "Jawa",
        "sumatra": "Sumatera",
        "borneo": "Kalimantan",
        "celebes": "Sulawesi",
        "bali": "Bali & Nusa Tenggara",
        "nusa tenggara": "Bali & Nusa Tenggara",
    },
    "store_city": {
        "jkt": "Jakarta",
        "dki jakarta": "Jakarta",
        "sby": "Surabaya",
        "bdg": "Bandung",
        "jogja": "Yogyakarta",
        "yogya": "Yogyakarta",
        "mks": "Makassar",
        "smg": "Semarang",
    },
    "channel": {
        "ecommerce": "E-commerce",
        "e-commerce": "E-commerce",
        "toko online": "E-commerce",
        "pos": "POS",
        "point of sale": "POS",
        "toko fisik": "POS",
        "mobile app": "Mobile App",
        "aplikasi": "Mobile App",
        "social commerce": "Social Commerce",
        "marketplace": "Marketplace",
    },
    "product_category": {
        "fmcg": "FMCG",
        "elektronik": "Electronics",
        "electronics": "Electronics",
        "fashion": "Fashion",
        "busana": "Fashion",
        "home & living": "Home & Living",
        "rumah tangga": "Home & Living",
        "health & beauty": "Health & Beauty",
        "kecantikan": "Health & Beauty",
    },
    "customer_segment": {
        "consumer": "Consumer",
        "konsumen": "Consumer",
        "ritel": "Consumer",
        "corporate": "Corporate",
        "korporat": "Corporate",
        "smb": "SMB",
        "umkm": "SMB",
    },
    "payment_method": {
        "credit card": "Credit Card",
        "kartu kredit": "Credit Card",
        "debit card": "Debit Card",
        "kartu debit": "Debit Card",
        "e-wallet": "E-Wallet",
        "ewallet": "E-Wallet",
        "dompet digital": "E-Wallet",
        "qris": "E-Wallet",
        "bank transfer": "Bank Transfer",
        "transfer bank": "Bank Transfer",
        "virtual account": "Bank Transfer",
        "cod": "COD",
        "bayar di tempat": "COD",
        "cash": "Cash",
        "tunai": "Cash",
    },
}


def get_dimension_catalog(force_refresh: bool = False) -> Dict[str, List[str]]:
    """
    Returns the dynamic dimension catalog fetched from the database with TTL caching.
    Keys: 'store_region', 'product_category', 'store_city', 'channel', 'customer_segment',
          'payment_method', 'product_brand', 'product_name', 'store_name'
    """
    global _catalog_cache, _last_fetch_time
    now = time.time()

    if not force_refresh and _catalog_cache is not None and (now - _last_fetch_time) < CACHE_TTL_SECONDS:
        return _catalog_cache

    catalog: Dict[str, List[str]] = {
        "store_region": [],
        "product_category": [],
        "store_city": [],
        "channel": [],
        "customer_segment": [],
        "payment_method": [],
        "product_brand": [],
        "product_name": [],
        "store_name": [],
    }

    try:
        r_regions = execute_readonly_sql("SELECT DISTINCT region FROM stores WHERE region IS NOT NULL ORDER BY region;")
        if r_regions.success and r_regions.rows:
            catalog["store_region"] = [r["region"] for r in r_regions.rows if r.get("region")]

        r_cats = execute_readonly_sql("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category;")
        if r_cats.success and r_cats.rows:
            catalog["product_category"] = [r["category"] for r in r_cats.rows if r.get("category")]

        r_cities = execute_readonly_sql("SELECT DISTINCT city FROM stores WHERE city IS NOT NULL ORDER BY city;")
        if r_cities.success and r_cities.rows:
            catalog["store_city"] = [r["city"] for r in r_cities.rows if r.get("city")]

        r_channels = execute_readonly_sql("SELECT DISTINCT channel FROM orders WHERE channel IS NOT NULL ORDER BY channel;")
        if r_channels.success and r_channels.rows:
            catalog["channel"] = [r["channel"] for r in r_channels.rows if r.get("channel")]

        r_segments = execute_readonly_sql("SELECT DISTINCT segment FROM customers WHERE segment IS NOT NULL ORDER BY segment;")
        if r_segments.success and r_segments.rows:
            catalog["customer_segment"] = [r["segment"] for r in r_segments.rows if r.get("segment")]

        r_payments = execute_readonly_sql("SELECT DISTINCT payment_method FROM orders WHERE payment_method IS NOT NULL ORDER BY payment_method;")
        if r_payments.success and r_payments.rows:
            catalog["payment_method"] = [r["payment_method"] for r in r_payments.rows if r.get("payment_method")]

        r_brands = execute_readonly_sql("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand;")
        if r_brands.success and r_brands.rows:
            catalog["product_brand"] = [r["brand"] for r in r_brands.rows if r.get("brand")]

        r_prods = execute_readonly_sql("SELECT DISTINCT product_name FROM products WHERE product_name IS NOT NULL ORDER BY product_name;")
        if r_prods.success and r_prods.rows:
            catalog["product_name"] = [r["product_name"] for r in r_prods.rows if r.get("product_name")]

        r_stores = execute_readonly_sql("SELECT DISTINCT store_name FROM stores WHERE store_name IS NOT NULL ORDER BY store_name;")
        if r_stores.success and r_stores.rows:
            catalog["store_name"] = [r["store_name"] for r in r_stores.rows if r.get("store_name")]

        if any(catalog.values()):
            _catalog_cache = catalog
            _last_fetch_time = now
            logger.info(f"Refreshed dynamic dimension catalog with {sum(len(v) for v in catalog.values())} distinct entities.")
            return _catalog_cache
    except Exception as e:
        logger.warning(f"Failed to query database for dynamic dimension catalog: {e}")

    if _catalog_cache is None:
        # Bootstrap fallback if database is unreachable on initial boot
        _catalog_cache = {
            "store_region": ["Jawa", "Sumatera", "Kalimantan", "Sulawesi", "Bali & Nusa Tenggara"],
            "product_category": ["FMCG", "Electronics", "Fashion", "Home & Living", "Health & Beauty"],
            "store_city": ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Makassar", "Palembang", "Denpasar"],
            "channel": ["POS", "E-commerce", "Marketplace", "Mobile App", "Social Commerce"],
            "customer_segment": ["Consumer", "Corporate", "SMB"],
            "payment_method": ["Bank Transfer", "COD", "Cash", "Credit Card", "Debit Card", "E-Wallet"],
            "product_brand": [],
            "product_name": [],
            "store_name": [],
        }

    return _catalog_cache


_NEGATION_CLAUSE_RE = re.compile(
    r'\b(?:selain|kecuali|bukan|di\s+luar|tanpa|tidak\s+termasuk|exclude|excluding|except|other\s+than|not\s+in)\b'
    r'(?!.*\b(?:untuk|pada|di\s+(?!luar)|for|in|with)\b)'
)


def _is_negated_at(msg_lower: str, match_start: int) -> bool:
    """Checks whether the entity match at `match_start` falls inside an active negation clause."""
    prefix = msg_lower[max(0, match_start - 55):match_start]
    return bool(_NEGATION_CLAUSE_RE.search(prefix))


def extract_dimension_filters(message: str) -> List[FilterItem]:
    """
    Extracts canonical FilterItems from user message using the dynamic dimension catalog.
    Supports both inclusion ('=', 'IN') and negation/exclusion ('!=', 'NOT IN'):
    - Single positive match -> FilterItem(field=..., operator="=", value="...")
    - Multiple positive matches -> FilterItem(field=..., operator="IN", value=["...", "..."])
    - Single negated match ("selain Jawa", "except FMCG") -> FilterItem(field=..., operator="!=", value="...")
    - Multiple negated matches -> FilterItem(field=..., operator="NOT IN", value=["...", "..."])
    Preserves order of appearance in the user's message.
    """
    catalog = get_dimension_catalog()
    msg_lower = message.lower()
    filters: List[FilterItem] = []

    for field, values in catalog.items():
        found_with_pos: List[tuple[int, str, bool]] = []
        seen_canonical: Set[str] = set()

        # 1. Check canonical values from DB (longest first to avoid partial overlap like Bali vs Bali & Nusa Tenggara)
        sorted_vals = sorted(values, key=len, reverse=True)
        for val in sorted_vals:
            pattern = r'(?<![a-z0-9])' + re.escape(val.lower()) + r'(?![a-z0-9])'
            m = re.search(pattern, msg_lower)
            if m and val not in seen_canonical:
                found_with_pos.append((m.start(), val, _is_negated_at(msg_lower, m.start())))
                seen_canonical.add(val)

        # 2. Check bilingual/colloquial aliases
        aliases = DIMENSION_ALIASES.get(field, {})
        for alias, canonical_val in sorted(aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if canonical_val in seen_canonical:
                continue
            pattern = r'(?<![a-z0-9])' + re.escape(alias.lower()) + r'(?![a-z0-9])'
            m = re.search(pattern, msg_lower)
            if m:
                found_with_pos.append((m.start(), canonical_val, _is_negated_at(msg_lower, m.start())))
                seen_canonical.add(canonical_val)

        if found_with_pos:
            # Sort by appearance position in user query
            found_with_pos.sort(key=lambda x: x[0])
            pos_vals = [v for _, v, is_neg in found_with_pos if not is_neg]
            neg_vals = [v for _, v, is_neg in found_with_pos if is_neg]

            if pos_vals:
                if len(pos_vals) == 1:
                    filters.append(FilterItem(field=field, operator="=", value=pos_vals[0]))
                else:
                    filters.append(FilterItem(field=field, operator="IN", value=pos_vals))

            if neg_vals:
                if len(neg_vals) == 1:
                    filters.append(FilterItem(field=field, operator="!=", value=neg_vals[0]))
                else:
                    filters.append(FilterItem(field=field, operator="NOT IN", value=neg_vals))

    # 3. Fuzzy Entity Linking for Minor Typos (e.g. "Surabya" -> "Surabaya", "Jakrta" -> "Jakarta")
    matched_fields = {f.field for f in filters}
    words = re.findall(r'[a-zA-Z]{5,}', message)
    stop_fuzzy = {
        "revenue", "margin", "produk", "product", "products", "kategori", "category", "categories",
        "channel", "channels", "bulan", "month", "minggu", "tahun", "tertinggi", "terendah",
        "terbesar", "terlaris", "highest", "lowest", "berdasarkan", "untuk", "region", "wilayah",
        "store", "stores", "cabang", "pelanggan", "customer", "segment", "segmen", "pesanan",
        "order", "orders", "cancel", "cancelled", "anomali", "anomaly", "average", "perbandingan",
        "bandingkan", "compare", "breakdown", "rincian", "daftar", "berapa", "jumlah", "total",
        "kemarin", "yesterday", "terakhir", "januari", "februari", "maret", "april", "agustus",
        "september", "oktober", "november", "desember", "metode", "pembayaran", "payment",
        "strategi", "definisi", "artinya", "maksudnya", "penjualan", "omset", "omzet", "transaksi",
        "sekarang", "besok", "lusa", "kapan", "siapa", "kenapa", "mengapa", "bagaimana", "gimana",
        "apakah", "tentang", "seperti", "adalah", "apapun", "dimana", "kemana", "darimana",
        "pukul", "waktu", "tanggal", "menit", "detik", "namun", "tetapi", "karena", "antara",
        "hanya", "sudah", "belum", "sedang", "masih", "akan", "dapat", "bisa", "tolong",
        "mohon", "silakan", "terima", "kasih", "thanks", "thank", "hello", "today", "tomorrow",
        "current", "clock", "date", "which", "where", "what", "when", "about"
    }
    for field in ("store_city", "store_region", "product_category", "product_brand"):
        if field in matched_fields:
            continue
        canon_map = {v.lower(): v for v in catalog.get(field, []) if len(v) >= 5}
        if not canon_map:
            continue
        for w in words:
            wl = w.lower()
            if wl in stop_fuzzy or wl in canon_map:
                continue
            close = difflib.get_close_matches(wl, list(canon_map.keys()), n=1, cutoff=0.86)
            if close:
                resolved_val = canon_map[close[0]]
                pos_idx = msg_lower.find(wl)
                op = "!=" if (pos_idx >= 0 and _is_negated_at(msg_lower, pos_idx)) else "="
                filters.append(FilterItem(field=field, operator=op, value=resolved_val))
                matched_fields.add(field)
                break

    return filters


_KNOWN_UNLISTED_LOCATIONS = {
    "papua", "jayapura", "sorong", "merauke", "timika",
    "maluku", "ambon", "ternate",
    "aceh", "banda aceh", "lhokseumawe",
    "lampung", "bandar lampung",
    "riau", "pekanbaru", "dumai", "batam", "kepulauan riau", "bintan",
    "bengkulu", "jambi", "bangka", "belitung", "pangkalpinang",
    "banten", "tangerang", "serang", "cilegon", "bogor", "depok", "bekasi",
    "cirebon", "tasikmalaya", "sukabumi", "karawang", "purwokerto", "tegal",
    "solo", "surakarta", "magelang", "pekalongan", "salatiga", "kudus",
    "malang", "kediri", "madiun", "jember", "banyuwangi", "gresik", "sidoarjo",
    "kupang", "lombok", "mataram", "bima", "labuan bajo",
    "pontianak", "singkawang", "palangkaraya", "tarakan",
    "manado", "palu", "kendari", "gorontalo",
    "singapore", "singapura", "malaysia", "kuala lumpur", "bangkok", "tokyo",
}


def detect_unresolved_location_mention(message: str, active_filters: List[FilterItem]) -> Optional[str]:
    """
    Detects if the user explicitly asked for a specific geographic location after 'di <X>', 'kota <X>', or 'region <X>'
    that does not exist in the database catalog (e.g. 'GMV di Papua bulan ini' or 'Revenue di Malang'),
    preventing silent fallback to national/unfiltered totals while never triggering on generic question words
    like 'di daerah mana saja?'.
    """
    msg_lower = message.lower()
    # Never trigger if the user is asking 'which region/city/area?' ('mana', 'mana saja', 'apa saja')
    if re.search(r'\b(?:di\s+)?(?:daerah|wilayah|region|kota|city|area|lokasi|cabang|toko|tempat|provinsi|pulau)\s+(?:mana|apa)\b', msg_lower):
        return None

    has_loc_filter = any(f.field in ("store_city", "store_region", "store_name") for f in active_filters)
    if has_loc_filter:
        return None

    # 1. Check known unlisted Indonesian/regional locations after 'di', 'kota', 'region', 'wilayah', 'cabang', 'untuk'
    for loc in sorted(_KNOWN_UNLISTED_LOCATIONS, key=len, reverse=True):
        pattern = r'\b(?:di(?:\s+kota|\s+region|\s+wilayah|\s+daerah)?|kota|region|wilayah|daerah|cabang|untuk)\s+' + re.escape(loc) + r'\b'
        m = re.search(pattern, msg_lower)
        if m:
            return loc.title()

    # 2. Check explicitly typed proper location after 'di kota <ProperName>' or 'di region <ProperName>' (case-sensitive Capitalized word)
    m_explicit = re.search(
        r'\b(?:di\s+kota|di\s+region|di\s+wilayah|di\s+daerah|kota|region|wilayah)\s+([A-Z][a-zA-Z]{2,})\b',
        message,
    )
    if m_explicit:
        cand = m_explicit.group(1).strip()
        if cand.lower() not in {
            "mana", "apa", "ini", "itu", "tadi", "atas", "bawah", "tertinggi", "terendah",
            "terbesar", "terlaris", "bulan", "minggu", "tahun", "indonesia", "nasional",
            "semua", "seluruh", "daerah", "wilayah", "region", "kota", "area", "lokasi",
            "kategori", "channel", "kanal", "segmen", "toko", "store", "database", "katalog",
            "sistem", "q1", "q2", "q3", "q4", "mtd", "ytd", "pos", "fmcg", "saja", "aja"
        }:
            return cand
    return None
