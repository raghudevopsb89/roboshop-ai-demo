env = "dev"

# Sweden Central, NOT Denmark East.
#
# This region was originally forced by Ministral-3B, which is not offered in
# Denmark East. That model is gone now, and both remaining models are
# first-party with broad regional coverage -- but this resource is already
# DEPLOYED here. Changing location would destroy and recreate the Foundry
# account and every deployment in it, so leave it alone unless you mean that.
#
# Verify availability before adding any model:  make models
location = "swedencentral"

# Reusing the existing resource group. A resource group is only a container --
# it can hold resources from any region.
resource_group_name = "denmark-east-rg"

# Must be globally unique (it becomes the *.openai.azure.com subdomain).
# Leave "" to get roboshop-dev-foundry; set explicitly if that name is taken.
foundry_name = ""

# The map key is the DEPLOYMENT name -- that is the string the demo code sends
# in the `model` field, not the model name.
model_deployments = {
  # Chat, first-party. Tool-calling capable, which rag-demo-4/ask_live.py needs.
  # This is the deployment rag-demo-4 uses.
  #
  # A Ministral-3B deployment used to sit here as a small-model counterpart to
  # this one. It was removed: Azure hard-caps it at capacity = 1, which is too
  # little to serve a RAG prompt (429 RateLimitReached) and worse for a
  # tool-calling loop, and being a Marketplace model it needed a subscription
  # purchase step before apply would succeed. Nothing depends on it now.
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

chat_deployment_name = "gpt-5-mini"
