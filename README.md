# Enterprise Conversational BI Agent (NLQ → SQL)

[![Evaluation Harness](https://img.shields.io/badge/Evaluation%20Score-10%2F10%20(100%25)-success?style=for-the-badge&logo=checkmarx)](backend/eval/eval_harness.py)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph%20StateGraph-blue?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20DuckDB-336791?style=for-the-badge&logo=postgresql)](db/seed/schema.sql)
[![Frontend](https://img.shields.io/badge/UI%20Design-EY%20Digital%20Design%20System-ffe600?style=for-the-badge&labelColor=2e2e38)](frontend/)

Enterprise-grade Conversational Business Intelligence (BI) agent that translates natural language queries (in Indonesian and English) into safe, validated, schema-aware PostgreSQL queries with rich visual and data-grounded analytical synthesis.

Built for the **AI Engineer Technical Assessment**.

---

## Key Highlights & Verification Results

- **10/10 Technical Scenarios Passed (100%):** Validated across all benchmark queries (ranking, multi-metric joins, time windows, anomaly detection, channel comparison, and multi-turn conversational context).
- **Hybrid Semantic Layer:** Eliminates metric hallucinations by calculating GMV, Revenue, COGS, Margin, and Cancel Rate deterministically at the database view level.
- **5 Balanced Retail Channels:** Synthetic dataset rigorously distributed across 5 channels (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`) at ~20% each.
- **Multi-Turn Context & Anaphora Memory:** Accurately retains state across turns (e.g., *Top 5 produk bulan lalu* → *Ini produknya di kategori apa?* → *Ada berapa kategori produk?*).
- **Multi-Layer Defense Guardrails:** Input regex/injection filter, `sqlglot` AST validation, table/column schema allowlist, outer `LIMIT 1000` cap, and PostgreSQL `bi_readonly` role with `statement_timeout = '10s'`.
- **Hybrid Vector Retrieval & Dynamic Date Templates:** In-memory vector store with stopword-filtered bilingual concept normalization and character n-gram cosine similarity, featuring date placeholders rendered against `AS_OF_DATE`.
- **Bilingual Interface (ID / EN):** One-click toggle between Bahasa Indonesia and English across all UI labels, KPI cards, analytical summaries, and executive reports.
- **Executive Dossier Generator:** Instant print-ready HTML/PDF executive summary reports with audit appendix.

---

## System Architecture

```
User Query (ID / EN)
        │
        ▼
[1. Input Guardrails] ──(Unsafe / DDL)──► Polite Refusal & Safe Recommendation
        │ (Safe)
        ▼
[2. Context & Session Memory] ◄──► [Redis / Session Store] (Entity & Turn History)
        │
        ▼
[3. Intent & Semantic Planning] ──► QueryPlan (Metrics, Dims, Filters, TimeWindow)
        │
        ▼
[4. Hybrid Vector Retrieval] ◄──► [Vector DB / Few-Shot Store] (Dynamic Golden SQL)
        │
        ▼
[5. Semantic SQL Compilation] ──► PostgreSQL Dialect over Semantic Views
        │
        ▼
[6. AST & Security Validation] ──(Error)──► [Self-Correction Retry Loop (Max 2)]
        │ (Approved)
        ▼
[7. Relational DB Execution] ──► PostgreSQL 16 (bi_readonly) / DuckDB Fallback
        │
        ▼
[8. Data-Grounded Synthesis] ──► KPI Cards, Distribution Charts, Insights, Assumptions
        │
        ▼
[9. SSE Streaming Response] ──► Vite React UI + Executive HTML/PDF Dossier
```

For detailed architectural specifications, see [docs/architecture.md](docs/architecture.md).

---

## Database Schema & Semantic Views

### 1. Base Relational Tables
- `customers(customer_id, customer_name, segment, city, region, signup_date)`
- `stores(store_id, store_name, city, region)`
- `products(product_id, product_name, category, brand, unit_cost)`
- `orders(order_id, order_date, customer_id, store_id, channel, status, payment_method)`
- `order_items(order_item_id, order_id, product_id, qty, unit_price, discount)`

### 2. Semantic Views (Zero Hallucination)
- `v_order_lines`: Line-level items pre-joined with customer, store, and product dimensions with standardized metric formulas.
- `v_orders`: Order-level aggregated metrics for accurate order counts, AOV, and cancel rates without double-counting.
- `v_daily_revenue`: Daily summary with 7-day rolling window averages for automated anomaly detection.

### 3. Business Metric Definitions
| Metric | Formal Definition | Semantic View Formula | Implementation Notes |
|---|---|---|---|
| **GMV** | `Σ(qty × unit_price − discount)` | `SUM(oi.qty * oi.unit_price - oi.discount)` | Per line item, all order statuses |
| **Revenue** | GMV for `'Completed'` orders | `SUM(CASE WHEN o.status='Completed' THEN (qty*unit_price-discount) ELSE 0 END)` | Excludes Cancelled, Returned, and Pending |
| **COGS** | `Σ(qty × unit_cost)` for `'Completed'` | `SUM(CASE WHEN o.status='Completed' THEN (qty*unit_cost) ELSE 0 END)` | Direct cost of goods sold |
| **Margin** | `Revenue − COGS` | `Revenue - COGS` | Gross profit margin |
| **Cancel Rate** | `Cancelled Orders / Total Orders` | `ROUND((COUNT(CASE WHEN status='Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2)` | Order-level ratio from `v_orders` |
| **"Bulan Ini / This Month"** | Month-to-Date (MTD) | `order_date >= 'YYYY-MM-01' AND order_date <= AS_OF_DATE` | Default reference date: `2026-10-29` |

---

## Quick Start & Installation

### Prerequisites
- Docker & Docker Compose **OR**
- Python 3.11+ and Node.js 18+ (for local development)

### Option 1: Docker Compose Setup (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/StevenSiahaann/ey-tech-test.git
cd ey-tech-test

# 2. Configure environment variables
cp infra/.env.example .env
# Edit .env with your Gemini API Key or Azure OpenAI credentials

# 3. Launch all services
make up
```

Access points:
- **Web Chat UI:** `http://localhost:3000`
- **FastAPI Backend & Swagger:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432` (`ey_bi`)

### Option 2: Local Development Setup

```bash
# 1. Setup Python Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Generate Synthetic Dataset & Seed Views
python3 db/seed/generate_data.py

# 3. Start Backend Server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

---

## Automated Evaluation & Verification

Run the automated test suites:

```bash
# Run unit and guardrail red-team tests
make test

# Run 10 Technical Test scenarios automated evaluation harness
make eval
```

### Verification Scorecard

| # | Technical Test Scenario | Status | Technical Audit Notes |
|---|---|:---:|---|
| 1 | GMV MTD untuk region Jawa? | **PASSED** | Aggregates `SUM(gmv)` on `v_order_lines`, filters `store_region = 'Jawa'`, evaluated for MTD. |
| 2 | Revenue dan margin MTD untuk FMCG di Jawa? | **PASSED** | Multi-metric query (`SUM(revenue)`, `SUM(margin)`), filters `product_category = 'FMCG'` & `store_region = 'Jawa'`. |
| 3 | Top 5 produk berdasarkan revenue bulan lalu? | **PASSED** | Date window: 1–30 September 2026, groups by product, sorts `DESC LIMIT 5`. |
| 4 | Channel dengan revenue tertinggi di Q1 2025? | **PASSED** | Date window: 1 Jan – 31 Mar 2025, groups by `channel`, sorts `DESC LIMIT 1`. |
| 5 | Cancel rate bulan ini? | **PASSED** | Evaluated on `v_orders` (`Cancelled / Total Orders * 100`) for MTD. |
| 6 | Segment customer dengan margin tertinggi YTD? | **PASSED** | Evaluated from 1 Jan – 29 Oct 2026, ranks `customer_segment` by `total_margin`. |
| 7 | Revenue POS vs E-commerce minggu ini? | **PASSED** | ISO week boundary, multi-value filter `channel IN ('POS', 'E-commerce')`. |
| 8 | Store di Jakarta dengan revenue tertinggi bulan ini? | **PASSED** | Filters `store_city = 'Jakarta'`, ranks stores by revenue `LIMIT 1`. |
| 9 | Multi-step follow-up conversation context | **PASSED** | 3-turn contextual chaining: FMCG Jawa MTD → Breakdown per kota → Top 3 store di kota teratas. |
| 10 | Revenue anomaly: drop >30% vs 7-day average | **PASSED** | Identifies dates from `v_daily_revenue` where daily revenue fell >30% below 7-day rolling average. |

---

## Documented Assumptions

1. **GMV vs Revenue:** GMV follows the specification $\Sigma(\text{qty} \times \text{unit\_price} - \text{discount})$ across all order statuses. Net Revenue strictly accounts for orders with `status = 'Completed'`.
2. **5 Channel Balance:** Synthetic transactions are uniformly balanced (~20% per channel: `POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`).
3. **Region Entity Mapping:** "Region Jawa" maps to `stores.region` (physical branch / fulfillment center). Explicit references to "customer di Jawa" filter `customers.region`.
4. **Timezone & Reference Date:** Standard timezone is `Asia/Jakarta` (WIB) with an anchored reference date of `2026-10-29` (configurable via `AS_OF_DATE`).
5. **Cancel Rate:** Defined as $\frac{\text{Count}(\text{status} = \text{'Cancelled'})}{\text{Count}(\text{total orders})} \times 100$ within the evaluated timeframe.
6. **Revenue Anomaly:** Defined as daily revenue falling below 70% of the preceding 7-day calendar rolling average ($>30\%$ drop).
7. **Cloud Architecture Portability:** Supports both Google Gemini and Azure OpenAI via environment configurations; Redis uses standard key-value and string operations compatible with Azure Cache for Redis.

---

## Documentation Links

- **Architecture Deep-Dive:** [docs/architecture.md](docs/architecture.md)
