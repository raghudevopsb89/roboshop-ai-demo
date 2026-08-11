variable "env" {
  type = string
}

# NOTE: this is deliberately NOT the same location as azure-services/infra
# (Denmark East). Model availability varies per region -- check with
# `make models` before adding one. See README.
variable "location" {
  description = "Region for the Foundry resource."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group to place the Foundry resource in. Reusing denmark-east-rg is fine -- a resource group is just a container and can hold resources from other regions."
  type        = string
}

variable "foundry_name" {
  description = "Foundry resource name. Doubles as the custom subdomain, so it must be globally unique across Azure. Append something if you hit a name clash."
  type        = string
  default     = ""
}

variable "model_deployments" {
  type = map(object({
    model_name    = string
    model_format  = string
    model_version = string
    sku_name      = optional(string, "GlobalStandard")
    capacity      = optional(number, 1)
  }))
}

variable "inference_principal_ids" {
  description = "Object IDs allowed to call inference without a key (e.g. the RHEL VM's managed identity)."
  type        = list(string)
  default     = []
}

# These two only feed the env_exports output -- they select which of the
# deployments above the demo should use for chat and for embeddings. Both must
# be keys of model_deployments.
variable "chat_deployment_name" {
  type    = string
  default = "gpt-5-mini"
}

variable "embed_deployment_name" {
  description = "Set to \"\" if you are keeping embeddings on local Ollama (nomic-embed-text)."
  type        = string
  default     = "text-embedding-3-small"
}
