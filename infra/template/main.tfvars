# Template for a new person's environment.
#
# Do not apply this directory directly -- it is not an environment. Scaffold
# your own copy, which substitutes ENV_PLACEHOLDER:
#
#   make new-env ENV=<yourname>
#
# env-dev/ is a separate, hand-maintained environment that is already deployed.
# It is NOT this template, and it carries an extra model (see below).

env = "ENV_PLACEHOLDER"

# Sweden Central, matching env-dev.
#
# Note the original reason for this region no longer applies here: it was
# chosen because Ministral-3B is not offered in Denmark East, and this template
# does not deploy Ministral-3B. Both models below are first-party OpenAI models
# with much broader regional coverage, so you may move this closer to
# azure-services/infra (Denmark East) if you prefer.
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
# Ministral-3B is deliberately NOT here, though env-dev has it. Two reasons:
# Azure hard-caps it at capacity = 1, which throttles a RAG turn with 429
# RateLimitReached and throttles a tool-calling loop harder still; and being a
# Marketplace (Mistral AI) model, it needs a Marketplace subscription accepted
# on the subscription before apply will succeed. It exists in env-dev only to
# demo small-model failure modes next to a capable model -- see
# rag-demo-4/README.md section 3. To opt back in, add it with capacity = 1 and
# accept the Marketplace terms first.
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
