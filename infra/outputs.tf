# Everything the demo code needs. The key is sensitive, so use
# `terraform output -json` or `make env` to read it.

output "foundry_name" {
  value = module.foundry.name
}

output "openai_v1_endpoint" {
  value = module.foundry.openai_v1_endpoint
}

output "deployment_names" {
  value = module.foundry.deployment_names
}

output "primary_access_key" {
  value     = module.foundry.primary_access_key
  sensitive = true
}

# Paste-ready export block for the demo. `make env` prints this.
#
# Note which model goes in which variable: the values are DEPLOYMENT names
# (the map keys in main.tfvars), not model names -- they only coincide here
# because the tfvars names them identically.
output "env_exports" {
  sensitive = true
  value     = <<-EOT
    export AZURE_BASE="${module.foundry.openai_v1_endpoint}"
    export AZURE_KEY="${module.foundry.primary_access_key}"
    export CHAT_MODEL="${var.chat_deployment_name}"
    export EMBED_MODEL="${var.embed_deployment_name}"
  EOT
}
