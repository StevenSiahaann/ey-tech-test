"""
Schema Registry and Allowlist for Conversational BI Agent.
Used by Prompt Generators and SQL AST Validators to ensure strict schema compliance.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

_METRICS_YAML_PATH = Path(__file__).resolve().parent / "metrics.yaml"
_CACHED_METRICS_REGISTRY: Dict[str, Any] = {}


@dataclass(frozen=True)
class MetricContract:
    name: str
    sql_expr: str
    output_alias: str
    source_view: str
    default_sort: str = "DESC"


METRIC_CONTRACTS: Dict[str, MetricContract] = {
    "gmv": MetricContract("gmv", "SUM(gmv)", "total_gmv", "v_order_lines"),
    "revenue": MetricContract("revenue", "SUM(revenue)", "total_revenue", "v_order_lines"),
    "margin": MetricContract("margin", "SUM(margin)", "total_margin", "v_order_lines"),
    "margin_pct": MetricContract("margin_pct", "ROUND((SUM(margin)::numeric / NULLIF(SUM(revenue), 0)::numeric) * 100, 2)", "margin_pct", "v_order_lines"),
    "cogs": MetricContract("cogs", "SUM(cogs)", "total_cogs", "v_order_lines"),
    "aov": MetricContract("aov", "ROUND((SUM(order_revenue)::numeric / NULLIF(SUM(is_completed), 0)::numeric), 2)", "aov", "v_orders"),
    "cancel_rate": MetricContract("cancel_rate", "ROUND((COUNT(CASE WHEN status = 'Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2)", "cancel_rate_pct", "v_orders"),
    "order_count": MetricContract("order_count", "COUNT(DISTINCT order_id)", "total_orders", "v_orders"),
    "category_count": MetricContract("category_count", "COUNT(DISTINCT product_category)", "total_categories", "v_order_lines"),
    "product_count": MetricContract("product_count", "COUNT(DISTINCT product_id)", "total_products", "v_order_lines"),
    "store_count": MetricContract("store_count", "COUNT(DISTINCT store_id)", "total_stores", "v_order_lines"),
    "channel_count": MetricContract("channel_count", "COUNT(DISTINCT channel)", "total_channels", "v_order_lines"),
}


def get_metric_contract(metric_name: str) -> Optional[MetricContract]:
    return METRIC_CONTRACTS.get(metric_name)


def resolve_primary_sort_alias(metrics: List[str]) -> str:
    """Returns the canonical output alias for the primary metric in the query."""
    if not metrics:
        return "total_revenue"
    primary = metrics[0]
    contract = METRIC_CONTRACTS.get(primary)
    if contract:
        return contract.output_alias
    return "total_revenue"


def reconcile_olap_breakdown_filters(filters: List[Any], dimensions: List[str]) -> List[Any]:
    """
    OLAP Invariant: A dimension being broken down / grouped cannot be restricted by an equality filter
    on the exact same dimension (e.g. breakdown per 'store_region' clears any 'store_region = Jawa' filter).
    Hierarchical drill-downs (e.g. breakdown per 'store_city' while 'store_region = Jawa' is active) are preserved.
    """
    grouping_dims = set(dimensions)
    return [f for f in filters if getattr(f, "field", None) not in grouping_dims]


def get_metrics_registry() -> Dict[str, Any]:
    """
    Loads and caches the canonical metric & dimension definitions from `metrics.yaml` (SSOT).
    Includes a zero-dependency parser fallback if PyYAML is not installed in the environment.
    """
    global _CACHED_METRICS_REGISTRY
    if _CACHED_METRICS_REGISTRY:
        return _CACHED_METRICS_REGISTRY
    try:
        import yaml
        if _METRICS_YAML_PATH.exists():
            data = yaml.safe_load(_METRICS_YAML_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _CACHED_METRICS_REGISTRY = data
                return _CACHED_METRICS_REGISTRY
    except Exception:
        pass

    # Zero-dependency fallback parser for metrics.yaml when PyYAML is not installed
    if _METRICS_YAML_PATH.exists():
        try:
            raw_lines = _METRICS_YAML_PATH.read_text(encoding="utf-8").splitlines()
            parsed: Dict[str, Dict[str, Any]] = {"metrics": {}, "dimensions": {}}
            section = None
            curr_item = None
            for line in raw_lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if indent == 0 and stripped.endswith(":"):
                    sec_name = stripped[:-1].strip()
                    if sec_name in ("metrics", "dimensions"):
                        section = sec_name
                        curr_item = None
                elif indent == 2 and stripped.endswith(":") and section:
                    curr_item = stripped[:-1].strip()
                    parsed[section][curr_item] = {}
                elif indent == 4 and ":" in stripped and section and curr_item:
                    k, v = stripped.split(":", 1)
                    v_clean = v.strip().strip('"').strip("'")
                    parsed[section][curr_item][k.strip()] = v_clean
            _CACHED_METRICS_REGISTRY = parsed
            return _CACHED_METRICS_REGISTRY
        except Exception:
            pass
    return {"metrics": {}, "dimensions": {}}

ALLOWED_SCHEMAS: Dict[str, Dict[str, str]] = {
    "v_order_lines": {
        "order_item_id": "VARCHAR - ID item transaksi",
        "order_id": "VARCHAR - ID pesanan",
        "order_date": "DATE - Tanggal pesanan dilakukan",
        "channel": "VARCHAR - Channel penjualan ('POS', 'E-commerce', 'Marketplace', 'Mobile App', 'Social Commerce')",
        "status": "VARCHAR - Status pesanan ('Completed', 'Cancelled', 'Returned', 'Pending')",
        "payment_method": "VARCHAR - Metode pembayaran",
        "store_id": "VARCHAR - ID toko",
        "store_name": "VARCHAR - Nama toko / cabang",
        "store_city": "VARCHAR - Kota toko (misal: 'Jakarta', 'Surabaya')",
        "store_region": "VARCHAR - Wilayah toko ('Jawa', 'Sumatera', 'Kalimantan', 'Sulawesi', 'Bali & Nusa Tenggara')",
        "customer_id": "VARCHAR - ID pelanggan",
        "customer_name": "VARCHAR - Nama pelanggan",
        "customer_segment": "VARCHAR - Segmen pelanggan ('Consumer', 'Corporate', 'SMB')",
        "customer_city": "VARCHAR - Kota tempat tinggal pelanggan",
        "customer_region": "VARCHAR - Wilayah pelanggan",
        "product_id": "VARCHAR - ID produk",
        "product_name": "VARCHAR - Nama produk",
        "product_category": "VARCHAR - Kategori produk ('FMCG', 'Electronics', 'Fashion', 'Home & Living', 'Health & Beauty')",
        "product_brand": "VARCHAR - Merk / Brand produk",
        "qty": "INTEGER - Jumlah unit dibeli",
        "unit_price": "NUMERIC - Harga jual per unit",
        "discount": "NUMERIC - Nilai potongan diskon pada item (nominal)",
        "unit_cost": "NUMERIC - Biaya modal per unit",
        "gmv": "NUMERIC - Nilai GMV = (qty * unit_price - discount)",
        "revenue": "NUMERIC - Net Revenue = GMV jika status='Completed', selain itu 0",
        "cogs": "NUMERIC - COGS = (qty * unit_cost) jika status='Completed', selain itu 0",
        "margin": "NUMERIC - Gross Margin = Revenue - COGS"
    },
    "v_orders": {
        "order_id": "VARCHAR - ID pesanan",
        "order_date": "DATE - Tanggal transaksi",
        "channel": "VARCHAR - Channel ('POS', 'E-commerce', 'Marketplace', 'Mobile App', 'Social Commerce')",
        "status": "VARCHAR - Status ('Completed', 'Cancelled', 'Returned', 'Pending')",
        "payment_method": "VARCHAR - Metode pembayaran",
        "store_id": "VARCHAR - ID toko",
        "store_name": "VARCHAR - Nama toko",
        "store_city": "VARCHAR - Kota toko",
        "store_region": "VARCHAR - Wilayah toko",
        "customer_id": "VARCHAR - ID pelanggan",
        "customer_name": "VARCHAR - Nama pelanggan",
        "customer_segment": "VARCHAR - Segmen pelanggan",
        "customer_city": "VARCHAR - Kota pelanggan",
        "customer_region": "VARCHAR - Wilayah pelanggan",
        "total_items": "INTEGER - Jumlah item berbeda dalam pesanan",
        "total_units": "INTEGER - Total kuantitas barang",
        "order_gmv": "NUMERIC - Total GMV pesanan",
        "order_revenue": "NUMERIC - Total revenue pesanan",
        "order_cogs": "NUMERIC - Total modal pesanan",
        "order_margin": "NUMERIC - Total margin pesanan",
        "is_completed": "INTEGER - 1 jika Completed, 0 jika tidak",
        "is_cancelled": "INTEGER - 1 jika Cancelled, 0 jika tidak"
    },
    "v_daily_revenue": {
        "order_date": "DATE - Tanggal",
        "daily_revenue": "NUMERIC - Total revenue hari tersebut",
        "avg_revenue_prev_7d": "NUMERIC - Rata-rata revenue 7 hari kalender sebelumnya",
        "pct_change_vs_7d_avg": "NUMERIC - Persentase perubahan vs rata-rata 7 hari sebelumnya",
        "is_anomaly_drop_over_30pct": "BOOLEAN - True jika revenue turun lebih dari 30% vs rata-rata 7 hari sebelumnya",
        "total_orders": "INTEGER - Total seluruh order hari itu",
        "completed_orders": "INTEGER - Total order completed",
        "cancelled_orders": "INTEGER - Total order cancelled",
        "cancel_rate_pct": "NUMERIC - Persentase cancel rate (cancelled / total * 100)"
    },
    # Base tables also available if needed
    "customers": {
        "customer_id": "VARCHAR", "customer_name": "VARCHAR", "segment": "VARCHAR",
        "city": "VARCHAR", "region": "VARCHAR", "signup_date": "DATE"
    },
    "stores": {
        "store_id": "VARCHAR", "store_name": "VARCHAR", "city": "VARCHAR", "region": "VARCHAR"
    },
    "products": {
        "product_id": "VARCHAR", "product_name": "VARCHAR", "category": "VARCHAR",
        "brand": "VARCHAR", "unit_cost": "NUMERIC"
    },
    "orders": {
        "order_id": "VARCHAR", "order_date": "DATE", "customer_id": "VARCHAR",
        "store_id": "VARCHAR", "channel": "VARCHAR", "status": "VARCHAR", "payment_method": "VARCHAR"
    },
    "order_items": {
        "order_item_id": "VARCHAR", "order_id": "VARCHAR", "product_id": "VARCHAR",
        "qty": "INTEGER", "unit_price": "NUMERIC", "discount": "NUMERIC"
    }
}


def get_allowed_tables() -> Set[str]:
    return set(ALLOWED_SCHEMAS.keys())


def get_allowed_columns_for_table(table_name: str) -> Set[str]:
    tbl = table_name.lower().strip()
    return set(ALLOWED_SCHEMAS.get(tbl, {}).keys())


def get_schema_prompt_text() -> str:
    """Produces structured markdown text of schema and SSOT metrics for LLM system prompt."""
    lines = ["## Database Schema (Semantic Views & Tables)"]
    for table_name in ["v_order_lines", "v_orders", "v_daily_revenue"]:
        lines.append(f"\n### View: `{table_name}`")
        for col, desc in ALLOWED_SCHEMAS[table_name].items():
            lines.append(f"- `{col}`: {desc}")

    reg = get_metrics_registry().get("metrics", {})
    if reg:
        lines.append("\n## Canonical Metric Definitions (from `metrics.yaml` SSOT)")
        for m_key, m_info in reg.items():
            lines.append(
                f"- `{m_key}` ({m_info.get('name', m_key)}): view `{m_info.get('source_view')}`, "
                f"formula `{m_info.get('view_field')}` — {m_info.get('assumption', '')}"
            )
    return "\n".join(lines)
