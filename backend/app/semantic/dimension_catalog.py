"""
Dynamic Semantic Dimension Catalog for Conversational BI Agent.
Discovers and caches discrete categorical dimensions directly from the database
(e.g., store regions, product categories, store cities, channels, customer segments).
Supports multi-value entity linking (IN operator for comparisons like "POS vs E-commerce"
or "Jakarta vs Surabaya") and strict word-boundary matching.
"""

import time
import logging
import re
from typing import Dict, List, Set, Optional
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
    }
}


def get_dimension_catalog(force_refresh: bool = False) -> Dict[str, List[str]]:
    """
    Returns the dynamic dimension catalog fetched from the database with TTL caching.
    Keys: 'store_region', 'product_category', 'store_city', 'channel', 'customer_segment'
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
        "customer_segment": []
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
            "customer_segment": ["Consumer", "Corporate", "SMB"]
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

    return filters
