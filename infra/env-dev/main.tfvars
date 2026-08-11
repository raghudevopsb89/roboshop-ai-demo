env = "dev"

# Sweden Central, NOT Denmark East.
#
# azure-services/infra runs in Denmark East, but Ministral-3B is not offered
# there -- its Global Standard availability list covers francecentral,
# germanywestcentral, italynorth, norwayeast, polandcentral, spaincentral,
# swedencentral, switzerlandnorth/west, uksouth, ukwest and westeurope.
# Sweden Central is the closest listed region to the existing infra.
#
# Verify before applying:  make models
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
  # Chat. Tool-calling capable, which demo 3 needs. Partner/Marketplace model:
  # see the Marketplace caveat in the README before applying.
  # capacity MUST be 1 -- Azure rejects anything else for this model with
  # "InvalidCapacity: ... should be at least 1 and no more than 1". The
  # AIServices.GlobalStandard.MaaS pool shows 600 units available, but that is
  # a subscription-wide pool, not a per-deployment ceiling.
  #
  # Consequence, and it is a real one: throughput is low enough that a RAG turn
  # (five retrieved chunks of context) can trip 429 RateLimitReached. common.py
  # backs off and honours Retry-After, so it recovers, but a full
  # `python3 ask_rag.py` over all five questions will be slow and may still
  # throttle. Swap chat_deployment_name to a first-party model if you need the
  # demo to run briskly -- see README.
  "Ministral-3B" = {
    model_name    = "Ministral-3B"
    model_format  = "Mistral AI"
    model_version = "1"
    sku_name      = "GlobalStandard"
    capacity      = 1
  }

  # Chat, first-party. Added because Ministral-3B's mandatory capacity=1 is not
  # enough throughput to serve a RAG prompt -- see the note above. This is the
  # deployment rag-demo-4 uses by default.
  #
  # Keeping both is useful rather than redundant: Ministral-3B is a 3B model
  # like the local llama3.2:3b, so it shows the same small-model failure modes,
  # while this one shows what a capable model does with the identical prompt.
  # Flip between them with CHAT_MODEL=... at the shell.
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

# rag-demo-4 defaults to the first-party model: Ministral-3B is capped at
# capacity=1, too little throughput for a RAG-sized prompt.
chat_deployment_name = "gpt-5-mini"
