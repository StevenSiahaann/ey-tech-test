# Azure Infrastructure-as-Code (Terraform) — Conversational BI Agent

Production-grade Terraform configuration to provision the complete **Enterprise Conversational BI Agent (NLQ → SQL)** stack on **Microsoft Azure**.

## Provisioned Architecture Components

| Azure Resource | Terraform Resource | Purpose in Conversational BI Architecture |
|---|---|---|
| **Resource Group** | `azurerm_resource_group.main` | Logical lifecycle boundary for all workload assets |
| **Managed Identity** | `azurerm_user_assigned_identity.app_identity` | Zero-trust passwordless RBAC for ACR pull & Key Vault secret access |
| **Azure Container Apps** | `azurerm_container_app.bi_agent` | Serverless auto-scaling hosting (`1..5` replicas) for FastAPI + React SPA with `/api/health` liveness/readiness probes |
| **Azure Container Registry** | `azurerm_container_registry.acr` | Private Docker image registry for the multi-stage application container |
| **Azure Database for PostgreSQL 16** | `azurerm_postgresql_flexible_server.postgres` | Relational analytical engine hosting base tables, `v_order_lines`, `v_orders`, `v_daily_revenue`, and `pgvector` extension |
| **Azure Cache for Redis** | `azurerm_redis_cache.redis` | Low-latency multi-turn session state & entity digest store (TLS 1.2 enforced, `volatile-lru`) |
| **Azure OpenAI Service** | `azurerm_cognitive_account.openai` + `gpt4o` | Enterprise LLM endpoint (`gpt-4o`) for Commander query planning, SQL compilation, and advisory synthesis |
| **Azure Key Vault** | `azurerm_key_vault.kv` | RBAC-governed secret management for database DSNs, Redis keys, and API tokens |
| **Log Analytics & App Insights** | `azurerm_log_analytics_workspace.logs` | Centralized log aggregation and 30-day retention for application & security audit logs |

---

## Quick Start (Provisioning Steps)

### 1. Authenticate with Azure CLI
```bash
az login
az account set --subscription "<YOUR_AZURE_SUBSCRIPTION_ID>"
```

### 2. Configure Variables
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars as needed (e.g., location, gemini_api_key, container_image)
```

### 3. Initialize, Validate & Apply
```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

### 4. Build & Push Application Image to ACR
```bash
ACR_SERVER=$(terraform output -raw acr_login_server)
az acr login --name "${ACR_SERVER%%.*}"

docker build -t "$ACR_SERVER/ey-conv-bi:latest" ../..
docker push "$ACR_SERVER/ey-conv-bi:latest"

# Update Container App with the pushed image
terraform apply -var="container_image=$ACR_SERVER/ey-conv-bi:latest"
```

### 5. Seed PostgreSQL Schema, Views & Read-Only Role
```bash
PG_FQDN=$(terraform output -raw postgresql_fqdn)
psql "postgresql://bi_admin:<PASSWORD>@${PG_FQDN}:5432/ey_bi?sslmode=require" \
  -f ../../db/01_schema.sql \
  -f ../../db/seed/seed_data.sql \
  -f ../../db/02_views.sql \
  -f ../../db/03_roles.sql
```

