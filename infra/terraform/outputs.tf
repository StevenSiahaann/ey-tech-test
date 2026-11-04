output "resource_group_name" {
  description = "Name of the provisioned Azure Resource Group."
  value       = azurerm_resource_group.main.name
}

output "application_url" {
  description = "Public HTTPS URL of the deployed Conversational BI Agent on Azure Container Apps."
  value       = "https://${azurerm_container_app.bi_agent.ingress[0].fqdn}"
}

output "acr_login_server" {
  description = "Azure Container Registry (ACR) login server endpoint."
  value       = azurerm_container_registry.acr.login_server
}

output "postgresql_fqdn" {
  description = "Fully Qualified Domain Name of the Azure Database for PostgreSQL Flexible Server."
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
}

output "postgresql_database_name" {
  description = "Name of the analytical PostgreSQL database."
  value       = azurerm_postgresql_flexible_server_database.ey_bi.name
}

output "redis_hostname" {
  description = "Hostname of the Azure Cache for Redis instance."
  value       = var.enable_redis ? azurerm_redis_cache.redis[0].hostname : null
}

output "azure_openai_endpoint" {
  description = "Endpoint URL for the provisioned Azure OpenAI Service."
  value       = var.enable_azure_openai ? azurerm_cognitive_account.openai[0].endpoint : null
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Azure Log Analytics Workspace storing rotated container & audit logs."
  value       = azurerm_log_analytics_workspace.logs.id
}

output "key_vault_uri" {
  description = "URI of the Azure Key Vault."
  value       = azurerm_key_vault.kv.vault_uri
}

