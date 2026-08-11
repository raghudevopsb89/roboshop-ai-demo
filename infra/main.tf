# Foundry resource + model deployments for the roboshop-ai-demo RAG demos.
#
# This stack is intentionally separate from azure-services/infra: the databases
# there are private to workstation-vnet and live in Denmark East, whereas model
# inference is a public endpoint that must sit in a region where the models are
# actually offered. Nothing here touches the VNet.
#
# To fold it into azure-services instead, drop modules/foundry into that repo
# and add the matching `module "foundry"` block -- the module takes no VNet
# inputs, so it lifts across unchanged.

locals {
  foundry_name = var.foundry_name != "" ? var.foundry_name : "roboshop-${var.env}-foundry"
}

module "foundry" {
  source = "./modules/foundry"

  name                    = local.foundry_name
  resource_group_name     = var.resource_group_name
  location                = var.location
  model_deployments       = var.model_deployments
  inference_principal_ids = var.inference_principal_ids

  tags = {
    project = "roboshop-ai-demo"
    env     = var.env
  }
}
