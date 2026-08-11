# Foundry infra for the RAG demos

Deploys a Microsoft Foundry resource plus model deployments, so the demos can
run against a hosted endpoint instead of local Ollama.

```bash
make dev-plan      # review
make dev           # apply
make env           # paste-ready exports for the demo scripts
make dev-destroy   # tear down
```

State lives alongside `azure-services` in the same storage account, under key
`roboshop-ai-demo/dev/terraform.tfstate`.

## What gets created

| Resource | Notes |
|---|---|
| `azurerm_cognitive_account` (kind `AIServices`, S0) | The Foundry resource. Foundry has **no F0/free SKU** — billable from the first request. |
| `azurerm_cognitive_deployment` × N | One per entry in `model_deployments`. Serverless SKUs, so **no idle cost** — per-token only. |
| `azurerm_role_assignment` (optional) | Keyless inference for a managed identity. Off by default. |

## One Foundry per person

`foundry_name` becomes the `*.openai.azure.com` subdomain, so it must be unique
across **all of Azure**, and the remote state key is per-environment. Two people
running `make dev` would collide on both. So everyone gets their own env:

```bash
make new-env ENV=raghu        # scaffolds env-raghu/ from env-dev/
ENV=raghu make plan           # review
ENV=raghu make apply
ENV=raghu make profile        # -> ../rag-demo-4/profiles/raghu.env (gitignored)
ENV=raghu make destroy
```

`new-env` copies `env-dev/` and changes exactly two things — the state key
(`roboshop-ai-demo/<env>/terraform.tfstate`) and `env`, which drives
`roboshop-<env>-foundry`. Region and model deployments are inherited, so read
the caveats below before applying.

`ENV` defaults to `dev`, so `make dev` and the existing `roboshop-dev-foundry`
state behave exactly as before. `make new-env ENV=dev` is refused — `env-dev/`
is the shared template.

`output`, `env` and `profile` re-run `terraform init` for the selected `ENV`,
because `.terraform/` otherwise still points at whichever environment was used
last, and reading someone else's state is the exact failure this prevents.

## Read this before `make dev`

### 1. `nomic-embed-text` is not deployable on Azure

It's an Ollama-distributed model and is not in the Foundry catalogue in any
serverless form. The nearest Nomic entry, `nomic-ai/modernbert-embed-base`,
only deploys to **managed compute** — a dedicated GPU endpoint billed per VM
hour, running whether or not anyone asks a question. That is the expensive
deployment shape and is not worth it for a 37-chunk index.

So this stack deploys `text-embedding-3-small` in the embedding slot instead.

**You do not have to use it.** Keeping embeddings on local Ollama is a
perfectly good choice, and arguably the better one here:

- your index stays 768-dim, so it doesn't need rebuilding;
- `HYBRID_ALPHA=0.4` in `rag-demo-2/ask_rag.py` was tuned against
  `nomic-embed-text`'s narrow 0.81–0.86 cosine band. Azure's embeddings are
  L2-normalised with a much wider spread, so that constant will need
  re-measuring if you switch.

To keep embeddings local, delete the `text-embedding-3-small` entry from
`model_deployments` and set `embed_deployment_name = ""`.

**If you do switch:** re-run `build_index.py`. Vectors from a 768-dim and a
1536-dim model are not comparable, and `cosine()` in `common.py` uses `zip()`,
which silently truncates to the shorter vector rather than erroring — you'd get
plausible-looking garbage scores instead of a crash.

### 2. Ministral-3B is a Marketplace model

It's a partner/community model, not first-party, which means:

- It bills through **Azure Marketplace**, not Azure meters.
- Your subscription needs `Microsoft.SaaS/register/action` and the
  `Microsoft.MarketplaceOrdering/*` permissions. Subscription **Owner** or
  **Contributor** covers these.
- **Free-trial, student, and credit-only subscriptions cannot purchase
  Marketplace SaaS offers.** If you're on the $200 trial credit, this apply will
  fail with a Marketplace eligibility error.

If that blocks you, swap to a first-party model — `gpt-5.1-mini`, format
`OpenAI` — which has none of these restrictions. That's a one-line change in
`env-dev/main.tfvars`.

### 3. The region is deliberately not Denmark East

`azure-services/infra` runs in Denmark East. Ministral-3B is not offered there;
its Global Standard region list covers `francecentral`, `germanywestcentral`,
`italynorth`, `norwayeast`, `polandcentral`, `spaincentral`, `swedencentral`,
`switzerlandnorth`, `switzerlandwest`, `uksouth`, `ukwest`, `westeurope`. This
stack defaults to `swedencentral`, the closest listed region.

The resource group is still `denmark-east-rg` — a resource group is only a
container and can hold resources from any region.

This split doesn't cost you anything: inference is a public endpoint the VM
reaches outbound. Only the MySQL/Cosmos stores need to be VNet-private, and
this stack doesn't touch the VNet.

### 4. Model coordinates drift

`model_name` / `model_format` / `model_version` / `sku_name` vary by region and
change as models are retired. Before editing `model_deployments`:

```bash
make models RG=denmark-east-rg NAME=roboshop-dev-foundry
```

SKU support varies **per model**, not just per region — don't assume that
because one model takes `Standard` in a region, its siblings do. In
`swedencentral`, `text-embedding-3-large` and `text-embedding-ada-002` offer
`Standard`, but `text-embedding-3-small` offers only `GlobalStandard` and
`DataZoneStandard`. Getting this wrong fails at apply time, not plan time,
with `InvalidResourceProperties: The specified SKU ... is not supported in this
region`.

Requires `azurerm` provider **4.27+**. Earlier versions hardcoded
`model.format` to `OpenAI`, so the `Mistral AI` deployment fails at plan time.

## Wiring it into the demos

```bash
eval "$(make -s env)"
```

That sets `AZURE_BASE`, `AZURE_KEY`, `CHAT_MODEL`, `EMBED_MODEL`.

`AZURE_BASE` is the **OpenAI-compatible** route
(`https://<name>.openai.azure.com/openai/v1`) — not the account's default
`*.cognitiveservices.azure.com` endpoint and not a project endpoint. It uses
implicit versioning, so there's no `api-version` parameter.

Smoke-test before changing any Python:

```bash
curl -s -X POST "$AZURE_BASE/chat/completions" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $AZURE_KEY" \
  -d "{\"model\":\"$CHAT_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"say ok\"}]}"
```

`rag-demo-4/common.py` speaks this endpoint directly. Demos 1–3 stay on Ollama;
there is no shim, they are separate folders.

## Cost

Serverless deployments cost nothing while idle — there is no VM behind them.
A full demo run is a few thousand tokens. The thing to avoid is **managed
compute** deployments (any Hugging Face catalogue model, e.g.
Qwen3-Coder-Next), which rent GPU VMs by the hour until deleted.
