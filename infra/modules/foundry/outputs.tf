output "name" {
  value = azurerm_cognitive_account.main.name
}

output "id" {
  value = azurerm_cognitive_account.main.id
}

# The OpenAI-compatible base URL. This is what the demo code should call --
# NOT the account's default *.cognitiveservices.azure.com endpoint, and NOT a
# project endpoint. The /openai/v1/ route uses implicit versioning, so there is
# no api-version query parameter to keep in sync.
output "openai_v1_endpoint" {
  value = "https://${azurerm_cognitive_account.main.custom_subdomain_name}.openai.azure.com/openai/v1"
}

# Same surface, alternate hostname. Both are accepted; kept here because some
# Foundry docs and samples use this form.
output "services_endpoint" {
  value = "https://${azurerm_cognitive_account.main.custom_subdomain_name}.services.ai.azure.com/openai/v1"
}

output "primary_access_key" {
  value     = azurerm_cognitive_account.main.primary_access_key
  sensitive = true
}

# Deployment names, which are what you pass as `model` in an inference request.
output "deployment_names" {
  value = keys(azurerm_cognitive_deployment.main)
}

output "identity_principal_id" {
  value = azurerm_cognitive_account.main.identity[0].principal_id
}
