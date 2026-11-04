variable "project_name" {
  description = "Workload identifier prefix for all Azure resources."
  type        = string
  default     = "ey-conv-bi"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase alphanumeric characters and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Primary Azure region for resource deployment."
  type        = string
  default     = "southeastasia"
}

variable "openai_location" {
  description = "Azure region for Azure OpenAI Service (must support GPT-4o deployments)."
  type        = string
  default     = "eastus"
}

variable "postgres_sku_name" {
  description = "SKU for Azure Database for PostgreSQL Flexible Server."
  type        = string
  default     = "B_Standard_B2s"
}

variable "postgres_storage_mb" {
  description = "Storage size in MB for PostgreSQL Flexible Server."
  type        = number
  default     = 32768
}

variable "postgres_admin_username" {
  description = "Administrator login for PostgreSQL Flexible Server."
  type        = string
  default     = "bi_admin"
}

variable "postgres_admin_password" {
  description = "Administrator password for PostgreSQL Flexible Server (if null, a strong random password is generated and stored in Key Vault)."
  type        = string
  default     = null
  sensitive   = true
}

variable "enable_redis" {
  description = "Whether to provision managed Azure Cache for Redis. If false, backend uses built-in high-performance in-memory session cache ($0 cost)."
  type        = bool
  default     = false
}

variable "redis_sku_name" {
  description = "SKU tier for Azure Cache for Redis (Basic, Standard, Premium)."
  type        = string
  default     = "Standard"
}

variable "redis_family" {
  description = "SKU family for Azure Cache for Redis (C for Basic/Standard, P for Premium)."
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Cache size capacity for Azure Cache for Redis."
  type        = number
  default     = 1
}

variable "enable_azure_openai" {
  description = "Whether to provision an Azure OpenAI Cognitive Services account and GPT-4o deployment."
  type        = bool
  default     = true
}

variable "openai_model_name" {
  description = "Azure OpenAI model name to deploy."
  type        = string
  default     = "gpt-4o"
}

variable "openai_model_version" {
  description = "Version of the Azure OpenAI model."
  type        = string
  default     = "2024-08-06"
}

variable "llm_provider" {
  description = "Default active LLM provider injected into Container App ('azure_openai' or 'gemini')."
  type        = string
  default     = "azure_openai"
}

variable "gemini_api_key" {
  description = "Optional Google Gemini API key for multi-provider fallback."
  type        = string
  default     = ""
  sensitive   = true
}

variable "container_image" {
  description = "Initial container image for the Conversational BI Agent (FastAPI + React SPA)."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "container_cpu" {
  description = "vCPU allocation for the Container App."
  type        = number
  default     = 1.0
}

variable "container_memory" {
  description = "Memory allocation for the Container App."
  type        = string
  default     = "2Gi"
}

variable "min_replicas" {
  description = "Minimum number of Container App replicas."
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum number of Container App replicas."
  type        = number
  default     = 5
}

variable "log_retention_days" {
  description = "Retention period (in days) for Azure Log Analytics Workspace and security audit logs."
  type        = number
  default     = 30
}

variable "as_of_date" {
  description = "Anchored evaluation reference date (YYYY-MM-DD) for deterministic MTD/YTD resolution."
  type        = string
  default     = "2026-10-29"
}

variable "tags" {
  description = "Standard enterprise resource tags."
  type        = map(string)
  default = {
    Workload   = "Conversational-BI-Data-Agent"
    ManagedBy  = "Terraform"
    CostCenter = "AI-Analytics"
    Security   = "ReadOnly-Guardrails-Enforced"
  }
}

