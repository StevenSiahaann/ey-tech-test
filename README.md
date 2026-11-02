# Enterprise Conversational BI Agent (NLQ → SQL)

[![Evaluation Harness](https://img.shields.io/badge/Evaluation%20Score-10%2F10%20(100%25)-success?style=for-the-badge&logo=checkmarx)](backend/eval/eval_harness.py)
[![Unit & Multi-Turn Tests](https://img.shields.io/badge/Unit%20%26%20Context%20Tests-28%2F28%20Passed-success?style=for-the-badge)](backend/tests/)
[![LangGraph](https://img.shields.io/badge/Orchestrator-Commander%20%2B%205%20Specialists-blue?style=for-the-badge)](backend/app/agent/graph.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20DuckDB-336791?style=for-the-badge&logo=postgresql)](db/01_schema.sql)
[![Terraform Azure](https://img.shields.io/badge/IaC-Terraform%20Azure-7B42BC?style=for-the-badge&logo=terraform)](infra/terraform/)
[![Frontend](https://img.shields.io/badge/UI%20Design-EY%20Digital%20Design%20System-ffe600?style=for-the-badge&labelColor=2e2e38)](frontend/)

Enterprise-grade Conversational Business Intelligence (BI) and Analytical Advisory Agent that translates natural language questions (in Bahasa Indonesia and English) into safe, AST-validated, schema-aware PostgreSQL queries—while supporting proactive ambiguity confirmation, multi-turn context chaining, and interactive executive discussions.

Built for the **AI Engineer Technical Assessment**.

---

## Key Highlights & Verification Results

- **10/10 Technical Scenarios Passed (100%) & 28/28 Unit Tests Passed:** Verified across all benchmark queries (ranking, multi-metric joins, time windows, anomaly detection, channel comparison, negation filters, proactive clarification, domain glossary discussion, structured log rotation, and multi-turn conversational context).
- **Hierarchical Multi-Agent Architecture (Commander + 5 Specialized Sub-Agents):**
  1. **Commander & Contextual Query Rewriter (`plan_query`):** Performs deictic/anaphoric resolution, morphological normalization (`-nya` suffix handling), and rewrites follow-ups into self-contained `standalone_query` representations.
  2. **`ClarificationGuardSpecialist`:** Proactively intercepts 5 classes of ambiguity (*Scope Ambiguity on Follow-Up*, *KPI Metric Ambiguity*, *Incomplete Entity Fragment*, *Orphan Deictic Reference*, and *Domain Scope Guardrail*) and presents clickable confirmation chips instead of guessing.
  3. **`ConversationalAdvisorSpecialist`:** Engages in interactive analytical discussions (e.g., *"Ini berarti apa artinya cancel rate?"*, *"Saya pengen tau dulu definisi dari POS"*, *"Apa bedanya GMV sama Net Revenue?"*, *"Strategi apa supaya cancel rate turun?"*) grounded in active session numbers and a comprehensive domain glossary (`POS`, `FMCG`, `MTD`/`YTD`, `GMV`, `SKU`) plus dynamic LLM advisory synthesis.
  4. **`CatalogMetadataSpecialist`:** Handles master catalog counts and entity listings (5 product categories, 28 SKUs, 12 stores, 5 sales channels) over all-time scope.
  5. **`AnalyticalSQLSpecialist`:** Compiles and verifies complex multi-metric aggregations, rankings, comparisons, and negation filters (`!=`, `NOT IN`) with post-LLM semantic alignment enforcement.
  6. **`AnomalyDiagnosticSpecialist`:** Evaluates 7-day rolling window revenue drops (`>30%`) on `v_daily_revenue`.
- **Hybrid Semantic Layer (Zero Metric Hallucination):** Pre-calculates GMV, Net Revenue, COGS, Gross Margin, and Cancel Rate deterministically at the database view level (`v_order_lines`, `v_orders`, `v_daily_revenue`).
- **5 Balanced Retail Channels:** Synthetic dataset uniformly distributed across 5 omnichannel touchpoints (`POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`) at ~20% each.
- **5-Layer Defense-in-Depth Guardrails:** Input credential/injection/DDL filter, `sqlglot` AST validation, table/column schema allowlist, outer `LIMIT 1000` cap, and PostgreSQL `bi_readonly` role with `statement_timeout = '10s'`.
- **Structured Step-by-Step Logging & Dual Log Rotation (`backend/app/core/logger.py`):** Context-propagated (`session_id`, `request_id`, `step`) logging across every pipeline step with size-based rotation (`RotatingFileHandler`, 10 MB × 5 backups on `logs/agent_app.log`) and daily time-based rotation (`TimedRotatingFileHandler`, 30-day retention on `logs/security_audit.log`).
- **Production Azure Infrastructure-as-Code (`infra/terraform/`):** Complete Terraform stack provisioning Azure Container Apps, Azure Database for PostgreSQL 16 Flexible Server (`pgvector`), Azure Cache for Redis, Azure OpenAI (`gpt-4o`), Azure Key Vault, Managed Identity, and Azure Log Analytics Workspace.
- **Continuous Few-Shot Learning (Vector Store Promotion):** Users can rate answers with 👍 / 👎 in the UI (`/api/feedback`), automatically promoting verified NL-to-SQL pairs into the hybrid vector store and logging scores to Langfuse.
- **Bilingual Interface (ID / EN) & Executive Dossier Generator:** One-click toggle between Bahasa Indonesia and English across all UI labels, KPI cards, charts, and print-ready HTML/PDF executive reports.

---

## Multi-Agent System Architecture

```
User Query (Bahasa Indonesia / English)
        │
        ▼
[1. Input Guardrails] ──(Unsafe / DDL / Injection)──► Polite Refusal & Safe Suggestions
        │ (Safe)
        ▼
[2. Context & Session Memory] ◄──► [Redis / Session Store] (Turn History & Entity Digest)
        │
        ▼
[3. Commander & Contextual Query Rewriter]
        ├──► Standalone Query Synthesis & Morphological Normalization
        │
        ├──► [ClarificationGuardSpecialist] ──(Ambiguous / Out-of-Scope)──► Proactive Confirmation Chips
        │
        ├──► [ConversationalAdvisorSpecialist] ──(Conceptual / Strategy Discussion)──► Grounded Advisory Card
        │
        ▼ (Data Retrieval Intent)
[4. Hybrid Vector Retrieval] ◄──► [Vector Store] (Dynamic Date-Rendered Golden SQL)
        │
        ▼
[5. Specialist SQL Compilation]
        ├──► [CatalogMetadataSpecialist] (Catalog Counts & Distinct Listings)
        ├──► [AnalyticalSQLSpecialist]   (Rankings, Breakdowns, Comparisons, Negations)
        └──► [AnomalyDiagnosticSpecialist] (7-Day Rolling Window Drop >30%)
        │
        ▼
[6. AST & Security Validation (sqlglot)] ──(Error)──► [Self-Correction Retry Loop (Max 2)]
        │ (Approved)
        ▼
[7. Relational DB Execution] ──► PostgreSQL 16 (bi_readonly) / Automatic DuckDB Engine
        │
        ▼
[8. Data-Grounded Synthesis] ──► KPI Cards, Distribution Charts, Insights, Recommendations
        │
        ▼
[9. SSE Streaming & Feedback Loop] ──► Vite React UI + 👍/👎 Vector Store Promotion
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
- `v_orders`: Order-level aggregated metrics for accurate order counts, AOV, and cancel rates without line-item double-counting.
- `v_daily_revenue`: Daily summary with 7-day rolling window averages for automated anomaly detection.

### 3. Business Metric Governance
| Metric | Formal Definition | Semantic View Formula | Implementation Notes |
|---|---|---|---|
| **GMV** | `Σ(qty × unit_price − discount)` | `SUM(oi.qty * oi.unit_price - oi.discount)` | Per line item across all order statuses (`Completed`, `Cancelled`, `Returned`) |
| **Net Revenue** | GMV for `'Completed'` orders | `SUM(CASE WHEN o.status='Completed' THEN (qty*unit_price-discount) ELSE 0 END)` | Strictly excludes `Cancelled` and `Returned` orders |
| **COGS** | `Σ(qty × unit_cost)` for `'Completed'` | `SUM(CASE WHEN o.status='Completed' THEN (qty*unit_cost) ELSE 0 END)` | Direct cost of goods sold for completed orders |
| **Gross Margin** | `Net Revenue − COGS` | `Revenue - COGS` | Realized gross profit margin |
| **Cancel Rate** | `(Cancelled Orders / Total Orders) × 100` | `ROUND((COUNT(CASE WHEN status='Cancelled' THEN 1 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 2)` | Order-level percentage from `v_orders` |
| **"Bulan Ini / This Month"** | Month-to-Date (MTD) | `order_date >= 'YYYY-MM-01' AND order_date <= AS_OF_DATE` | Default anchored reference date: `2026-10-29` |

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
# Edit .env with your GEMINI_API_KEY (or Azure OpenAI credentials)

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

### Option 3: Cloud / Render Single-Container Deployment
The repository includes a multi-stage `Dockerfile` that builds the React SPA (`frontend/dist`) and serves both the UI and FastAPI backend from a single container:
- **Minimum Required Environment Variable:** `GEMINI_API_KEY` (or Azure OpenAI credentials).
- **Zero-Config Analytical Engine Fallback:** If `DATABASE_URL` (PostgreSQL) is not provisioned in the cloud environment, the container automatically initializes its embedded **DuckDB** analytical engine from the seeded CSV dataset and creates all 3 semantic views (`v_order_lines`, `v_orders`, `v_daily_revenue`) at startup.

### Option 4: Enterprise Azure Provisioning with Terraform (`infra/terraform/`)
Provision the full Azure enterprise topology (Azure Container Apps, Azure Database for PostgreSQL 16 Flexible Server with `pgvector`, Azure Cache for Redis, Azure OpenAI Service `gpt-4o`, Azure Key Vault, User-Assigned Managed Identity, and Azure Log Analytics Workspace):

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```
See [infra/terraform/README.md](infra/terraform/README.md) for full Azure deployment details.

---

## Automated Evaluation & Verification

Run the automated test suites:

```bash
# Run all 28 unit, multi-turn context, discussion, logging, and guardrail red-team tests
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v

# Run the 10 Technical Test scenarios automated evaluation harness
PYTHONPATH=. python3 backend/eval/eval_harness.py
```

### Verification Scorecard

| # | Technical Test Scenario | Status | Technical Audit Notes |
|---|---|:---:|---|
| 1 | GMV MTD untuk region Jawa? | **PASSED** | Aggregates `SUM(gmv)` on `v_order_lines`, filters `store_region = 'Jawa'`, evaluated for MTD. |
| 2 | Revenue dan margin MTD untuk FMCG di Jawa? | **PASSED** | Multi-metric query (`SUM(revenue)`, `SUM(margin)`), filters `product_category = 'FMCG'` & `store_region = 'Jawa'`. |
| 3 | Top 5 produk berdasarkan revenue bulan lalu? | **PASSED** | Date window: 1–30 September 2026, groups by product, sorts `DESC LIMIT 5`. |
| 4 | Channel dengan revenue tertinggi di Q1 2025? | **PASSED** | Date window: 1 Jan – 31 Mar 2025, groups by `channel`, sorts `DESC LIMIT 1`. |
| 5 | Cancel rate bulan ini? | **PASSED** | Evaluated on `v_orders` (`COUNT(status = 'Cancelled') / COUNT(*) × 100`) for MTD. |
| 6 | Segment customer dengan margin tertinggi YTD? | **PASSED** | Evaluated from 1 Jan – 29 Oct 2026, ranks `customer_segment` by `total_margin`. |
| 7 | Revenue POS vs E-commerce minggu ini? | **PASSED** | ISO week boundary, multi-value filter `channel IN ('POS', 'E-commerce')`. |
| 8 | Store di Jakarta dengan revenue tertinggi bulan ini? | **PASSED** | Filters `store_city = 'Jakarta'`, ranks stores by revenue `LIMIT 1`. |
| 9 | Multi-step follow-up conversation context | **PASSED** | 3-turn contextual chaining: FMCG Jawa MTD → Breakdown per kota → Top 3 store di kota teratas. |
| 10 | Revenue anomaly: drop >30% vs 7-day average | **PASSED** | Identifies dates from `v_daily_revenue` where daily revenue fell >30% below 7-day rolling average. |

---

## Documented Assumptions

1. **GMV vs Net Revenue:** GMV follows the specification `Σ(qty × unit_price − discount)` across all order statuses (`Completed`, `Cancelled`, `Returned`). Net Revenue and Gross Margin strictly account for orders with `status = 'Completed'`.
2. **5 Channel Balance:** Synthetic transactions are uniformly balanced (~20% per channel: `POS`, `E-commerce`, `Marketplace`, `Mobile App`, `Social Commerce`).
3. **Region Entity Mapping:** `"Region Jawa"` maps to `stores.region` (physical branch / fulfillment center). Explicit references to `"customer di Jawa"` filter `customers.region`.
4. **Timezone & Reference Date:** Standard timezone is `Asia/Jakarta` (WIB) with an anchored reference date of `2026-10-29` (configurable via `AS_OF_DATE`).
5. **Cancel Rate:** Defined as `(COUNT(status = 'Cancelled') / COUNT(total_orders)) × 100` from `v_orders` within the evaluated timeframe.
6. **Revenue Anomaly:** Defined as daily revenue falling below 70% of the preceding 7-day calendar rolling average (`>30%` drop).
7. **Cloud Architecture Portability:** Supports both Google Gemini and Azure OpenAI via environment configurations; Redis uses standard key-value and string operations compatible with Azure Cache for Redis (with automatic in-memory fallback).

---

## Documentation Links

- **Architecture Deep-Dive:** [docs/architecture.md](docs/architecture.md)
- **Azure Terraform IaC Guide:** [infra/terraform/README.md](infra/terraform/README.md)
