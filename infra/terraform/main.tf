# ============================================================================
# Azure Enterprise Infrastructure for Conversational BI Agent (NLQ -> SQL)
# ============================================================================
# Provisions:
# 1. Resource Group & User-Assigned Managed Identity (Zero-Trust RBAC)
# 2. Azure Log Analytics Workspace & Application Insights (Log Rotation & Telemetry)
# 3. Azure Key Vault (Secret Governance for DB, Redis, and LLM Credentials)
# 4. Azure Container Registry (ACR)
# 5. Azure Database for PostgreSQL Flexible Server (PostgreSQL 16 + pgvector)
# 6. Azure Cache for Redis (TLS 1.2 enforced, 24h Session Context Memory)
# 7. Azure OpenAI Service (GPT-4o Deployment)
# 8. Azure Container Apps Environment & Auto-Scaling Container App
# ============================================================================

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}

resource "random_password" "pg_password" {
  count            = var.postgres_admin_password == null ? 1 : 0
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

locals {
  name_prefix  = "${var.project_name}-${var.environment}"
  compact_name = replace("${var.project_name}${var.environment}${random_string.suffix.result}", "-", "")
  pg_password  = var.postgres_admin_password != null ? var.postgres_admin_password : random_password.pg_password[0].result
  common_tags = merge(var.tags, {
    Environment = var.environment
    Project     = var.project_name
  })
}

# ----------------------------------------------------------------------------
# 1. Resource Group & Managed Identity
# ----------------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name_prefix}-${random_string.suffix.result}"
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_user_assigned_identity" "app_identity" {
  name                = "id-${local.name_prefix}-app"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.common_tags
}

# ----------------------------------------------------------------------------
# 2. Observability & Log Rotation / Retention (Log Analytics + App Insights)
# ----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "law-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  daily_quota_gb      = 5
  tags                = local.common_tags
}

resource "azurerm_application_insights" "appinsights" {
  name                = "appi-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.logs.id
  application_type    = "web"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

# ----------------------------------------------------------------------------
# 3. Azure Container Registry (ACR)
# ----------------------------------------------------------------------------
resource "azurerm_container_registry" "acr" {
  name                = substr("acr${local.compact_name}", 0, 50)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = local.common_tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app_identity.principal_id
}

# ----------------------------------------------------------------------------
# 4. Azure Database for PostgreSQL Flexible Server (PostgreSQL 16 + pgvector)
# ----------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                   = "psql-${local.name_prefix}-${random_string.suffix.result}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = var.postgres_admin_username
  administrator_password = local.pg_password
  sku_name               = var.postgres_sku_name
  storage_mb             = var.postgres_storage_mb
  backup_retention_days  = 7
  zone                   = "1"
  tags                   = local.common_tags
}

resource "azurerm_postgresql_flexible_server_database" "ey_bi" {
  name      = "ey_bi"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  collation = "en_US.utf8"
  charset   = "UTF8"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  value     = "VECTOR,PG_STAT_STATEMENTS"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.postgres.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# ----------------------------------------------------------------------------
# 5. Azure Cache for Redis (Multi-Turn Session & Entity Digest Store)
# ----------------------------------------------------------------------------
resource "azurerm_redis_cache" "redis" {
  count               = var.enable_redis ? 1 : 0
  name                = "redis-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku_name
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }

  tags = local.common_tags
}

# ----------------------------------------------------------------------------
# 6. Azure OpenAI Service & GPT-4o Deployment
# ----------------------------------------------------------------------------
resource "azurerm_cognitive_account" "openai" {
  count                 = var.enable_azure_openai ? 1 : 0
  name                  = "oai-${local.name_prefix}-${random_string.suffix.result}"
  location              = var.openai_location
  resource_group_name   = azurerm_resource_group.main.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${local.name_prefix}-${random_string.suffix.result}"
  tags                  = local.common_tags
}

resource "azurerm_cognitive_deployment" "gpt4o" {
  count                = var.enable_azure_openai ? 1 : 0
  name                 = var.openai_model_name
  cognitive_account_id = azurerm_cognitive_account.openai[0].id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  scale {
    type     = "Standard"
    capacity = 30
  }
}

# ----------------------------------------------------------------------------
# 7. Azure Key Vault (Centralized Secret Storage)
# ----------------------------------------------------------------------------
resource "azurerm_key_vault" "kv" {
  name                       = substr("kv-${local.name_prefix}-${random_string.suffix.result}", 0, 24)
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
  tags                       = local.common_tags
}

resource "azurerm_role_assignment" "kv_admin_current" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "kv_secrets_user_app" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app_identity.principal_id
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "postgres-admin-password"
  value        = local.pg_password
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin_current]
}

resource "azurerm_key_vault_secret" "database_ro_dsn" {
  name         = "database-url-ro"
  value        = local.postgres_ro_dsn
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin_current]
}

resource "azurerm_key_vault_secret" "gemini_key" {
  count        = var.gemini_api_key != "" ? 1 : 0
  name         = "gemini-api-key"
  value        = var.gemini_api_key
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin_current]
}

# ----------------------------------------------------------------------------
# 8. Azure Container Apps Environment & Application Deployment
# ----------------------------------------------------------------------------
resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.name_prefix}-${random_string.suffix.result}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = local.common_tags
}

locals {
  postgres_ro_dsn = "postgresql://${var.postgres_admin_username}:${urlencode(local.pg_password)}@${azurerm_postgresql_flexible_server.postgres.fqdn}:5432/${azurerm_postgresql_flexible_server_database.ey_bi.name}?sslmode=require"
  redis_tls_url   = var.enable_redis ? "rediss://:${urlencode(azurerm_redis_cache.redis[0].primary_access_key)}@${azurerm_redis_cache.redis[0].hostname}:${azurerm_redis_cache.redis[0].ssl_port}/0" : ""
  openai_endpoint = var.enable_azure_openai ? azurerm_cognitive_account.openai[0].endpoint : ""
  openai_api_key  = var.enable_azure_openai ? azurerm_cognitive_account.openai[0].primary_access_key : ""
}

resource "azurerm_container_app" "bi_agent" {
  name                         = "ca-${local.name_prefix}"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app_identity.id]
  }

  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }

  secret {
    name  = "database-url-ro"
    value = local.postgres_ro_dsn
  }

  secret {
    name  = "redis-url"
    value = local.redis_tls_url != "" ? local.redis_tls_url : "none"
  }

  secret {
    name  = "azure-openai-api-key"
    value = local.openai_api_key != "" ? local.openai_api_key : "not-configured"
  }

  secret {
    name  = "gemini-api-key"
    value = var.gemini_api_key != "" ? var.gemini_api_key : "not-configured"
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "conversational-bi-agent"
      image  = var.container_image
      cpu    = var.container_cpu
      memory = var.container_memory

      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "APP_TIMEZONE"
        value = "Asia/Jakarta"
      }
      env {
        name  = "AS_OF_DATE"
        value = var.as_of_date
      }
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = local.openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = var.openai_model_name
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-openai-api-key"
      }
      env {
        name        = "GEMINI_API_KEY"
        secret_name = "gemini-api-key"
      }
      env {
        name        = "DATABASE_URL_RO"
        secret_name = "database-url-ro"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "LOG_MAX_BYTES"
        value = "10485760"
      }
      env {
        name  = "LOG_BACKUP_COUNT"
        value = "5"
      }
      env {
        name  = "LOG_AUDIT_RETENTION_DAYS"
        value = tostring(var.log_retention_days)
      }
    }
  }
}

