# Microsoft Foundry (formerly Azure AI Foundry) resource + model deployments.
#
# A bare Foundry resource is enough to serve inference -- projects and hubs are
# only needed for the playground and Agent Service, which this demo doesn't use.
# That keeps this module to two resource types.
#
# kind = "AIServices" is what makes this a Foundry resource rather than a
# single-service Cognitive Services account. S0 is the only option: Foundry does
# NOT support the F0 (free) SKU, so this is billable from the first request.

resource "azurerm_cognitive_account" "main" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  kind                = "AIServices"
  sku_name            = "S0"

  # Required for token-based (Entra ID) auth and for the *.openai.azure.com and
  # *.services.ai.azure.com hostnames to resolve. Must be GLOBALLY unique.
  custom_subdomain_name = var.name

  # Inference is a public endpoint. The MySQL/Cosmos stores stay private inside
  # workstation-vnet; the VM reaches Foundry outbound over the internet.
  public_network_access_enabled = true

  # Lets the resource itself hold an identity later (e.g. for Key Vault refs).
  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# One deployment per model. A deployment is just a named alias onto a model --
# for serverless SKUs (GlobalStandard / Standard) there is no VM behind it and
# no idle cost, only per-token billing.
#
# The exact name/format/version/sku triple is REGION-DEPENDENT and drifts as
# models are retired. Run `make models` to list what your region actually
# offers before changing these.
resource "azurerm_cognitive_deployment" "main" {
  for_each = var.model_deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.main.id

  model {
    format  = each.value.model_format
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

# Optional: let the RHEL VM's managed identity call inference without an API
# key. Leave inference_principal_ids empty to stay on key auth.
resource "azurerm_role_assignment" "inference" {
  for_each = toset(var.inference_principal_ids)

  scope                = azurerm_cognitive_account.main.id
  role_definition_name = var.inference_role_name
  principal_id         = each.value
}
