# Template for a new person's environment.
#
# Do not apply this directory directly -- it is not an environment. Scaffold
# your own copy, which substitutes ENV_PLACEHOLDER:
#
#   make new-env ENV=<yourname>
#
# env-dev/ is a separate, hand-maintained environment that is already deployed.
# It is NOT this template, though it now deploys the same two models.

env = "ENV_PLACEHOLDER"

# Sweden Central, matching env-dev.
#
# env-dev is pinned here for a historical reason (a Mistral model that is no
# longer deployed) and cannot move without recreating the account. A NEW
# environment has no such constraint: both models below are first-party with
# broad regional coverage, so you may put this closer to azure-services/infra
# (Denmark East) if you prefer.
#
# Verify before applying, because availability and SKUs vary per model AND per
# region:  make models RG=denmark-east-rg ENV=<yourname>
location = "swedencentral"

# Reusing the existing resource group. A resource group is only a container --
# it can hold resources from any region.
resource_group_name = "denmark-east-rg"

# Must be globally unique (it becomes the *.openai.azure.com subdomain).
# Leave "" to get roboshop-<env>-foundry; set explicitly if that name is taken.
foundry_name = ""

# The map key is the DEPLOYMENT name -- that is the string the demo code sends
# in the `model` field, not the model name.
#
# Keep these first-party (model_format = "OpenAI"). A Marketplace/partner model
# such as Ministral-3B needs a Marketplace purchase accepted on the
# subscription before apply will succeed, and the one we tried was hard-capped
# by Azure at capacity = 1 -- too little to serve a RAG prompt without 429
# RateLimitReached, and worse inside a tool-calling loop.
model_deployments = {
  # Chat, first-party. Tool-calling capable, which rag-demo-4/ask_live.py needs.
  # capacity 50 is enough for a RAG-sized prompt; lower it if several people
  # share one subscription's quota in this region.
  "gpt-5-mini" = {
    model_name    = "gpt-5-mini"
    model_format  = "OpenAI"
    model_version = "2025-08-07"
    sku_name      = "GlobalStandard"
    capacity      = 50
  }

  # Embeddings. This replaces nomic-embed-text, which Azure does not host --
  # see the README. First-party (no Marketplace subscription needed).
  # 1536-dim, so the index MUST be rebuilt if you switch to it.
  #
  # sku MUST be GlobalStandard here: in swedencentral this model offers only
  # GlobalStandard and DataZoneStandard. (text-embedding-3-large and ada-002
  # do offer Standard in the same region -- it varies per model, not just per
  # region, so check with `make models` rather than assuming.)
  "text-embedding-3-small" = {
    model_name    = "text-embedding-3-small"
    model_format  = "OpenAI"
    model_version = "1"
    sku_name      = "GlobalStandard"
    capacity      = 10
  }
}

# Add the RHEL VM's system-assigned identity object ID here to drop the API key
# entirely:
#   az vm identity show -g <rg> -n <vm> --query principalId -o tsv
inference_principal_ids = []

# Which deployment each demo variable points at. These are deployment names
# (the map keys above), not model names.
chat_deployment_name  = "gpt-5-mini"
embed_deployment_name = "text-embedding-3-small"
