variable "name" {
  description = "Foundry resource name. Also used as the custom subdomain, so it must be GLOBALLY unique across Azure."
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  description = "Region for the Foundry resource. Must be a region where every model in model_deployments is offered -- this is NOT necessarily the region your other infra lives in."
  type        = string
}

variable "model_deployments" {
  description = <<-EOT
    Map of deployment name -> model spec. The map key becomes the deployment
    name, which is what you pass in the `model` field of an inference request.

    model_format values seen in the catalogue: "OpenAI", "Mistral AI",
    "Microsoft", "Meta", "Cohere", "DeepSeek", "xAI", "AI21 Labs", "Core42".
    Run `make models` to see the exact values valid in your region.
  EOT

  type = map(object({
    model_name    = string
    model_format  = string
    model_version = string
    sku_name      = optional(string, "GlobalStandard")
    capacity      = optional(number, 1)
  }))
}

variable "inference_principal_ids" {
  description = "Object IDs granted inference rights on the resource (e.g. the RHEL VM's system-assigned identity). Empty = key auth only."
  type        = list(string)
  default     = []
}

variable "inference_role_name" {
  description = "Built-in role granted to inference_principal_ids. Foundry's RBAC role names were recently renamed (Azure AI User -> Foundry User), so this is a variable rather than hardcoded."
  type        = string
  default     = "Cognitive Services OpenAI User"
}

variable "tags" {
  type    = map(string)
  default = {}
}
