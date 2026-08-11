# Per-person environments.
#
# Everyone has their own Foundry account, so each person gets their own tfvars
# directory, their own remote state key, and their own resource name -- the
# name becomes the *.openai.azure.com subdomain, so it must be globally unique
# across all of Azure, not just this subscription.
#
#   make new-env ENV=raghu      scaffold env-raghu/ from env-dev/
#   ENV=raghu make plan         review
#   ENV=raghu make apply        deploy
#   ENV=raghu make profile      write ../rag-demo-4/profiles/raghu.env
#   ENV=raghu make destroy      tear down
#
# ENV defaults to dev, so `make dev` and friends behave exactly as before and
# the existing roboshop-dev-foundry state is untouched.

ENV ?= dev
DIR := env-$(ENV)
PROFILE_DIR := ../rag-demo-4/profiles

common:
	@test -d $(DIR) || { \
	  echo "no such environment: $(DIR)"; \
	  echo "create it with:  make new-env ENV=$(ENV)"; exit 1; }
	rm -f .terraform/terraform.tfstate

apply: common
	terraform init -backend-config=$(DIR)/state.tfvars
	terraform apply -auto-approve -var-file=$(DIR)/main.tfvars

plan: common
	terraform init -backend-config=$(DIR)/state.tfvars
	terraform plan -var-file=$(DIR)/main.tfvars

destroy: common
	terraform init -backend-config=$(DIR)/state.tfvars
	terraform destroy -auto-approve -var-file=$(DIR)/main.tfvars

# Original target names, kept so existing docs and muscle memory still work.
# They honour ENV too, so `ENV=raghu make dev` applies raghu, not dev.
dev dev-apply: apply
dev-plan: plan
dev-destroy: destroy

# Scaffold a new person's environment from env-dev as the template.
new-env:
	@test "$(ENV)" != "dev" || { \
	  echo "ENV=dev is the shared template -- pick your own name:"; \
	  echo "  make new-env ENV=<yourname>"; exit 1; }
	@test ! -d $(DIR) || { echo "$(DIR) already exists"; exit 1; }
	@mkdir -p $(DIR)
	@sed 's|^key  *=.*|key                  = "roboshop-ai-demo/$(ENV)/terraform.tfstate"|' \
	  env-dev/state.tfvars > $(DIR)/state.tfvars
	@sed 's|^env  *=.*|env = "$(ENV)"|' env-dev/main.tfvars > $(DIR)/main.tfvars
	@echo "created $(DIR)/"
	@grep -H '^key' $(DIR)/state.tfvars
	@grep -H '^env' $(DIR)/main.tfvars
	@echo "-> foundry_name will be roboshop-$(ENV)-foundry (must be globally unique)"
	@echo "-> check region + model availability in $(DIR)/main.tfvars, then:"
	@echo "   ENV=$(ENV) make plan"

# init is re-run because .terraform points at whichever env was used last --
# without it these would happily read someone else's state.
output: common
	@terraform init -backend-config=$(DIR)/state.tfvars >/dev/null
	@terraform output

# Paste-ready exports:  eval "$$(ENV=raghu make -s env)"
env: common
	@terraform init -backend-config=$(DIR)/state.tfvars >/dev/null
	@terraform output -raw env_exports

# Write those exports straight into a gitignored profile the demos can load
# with ROBOSHOP_PROFILE=$(ENV). Refuses to clobber an existing one, since you
# will have added MYSQL_*/MONGO_URL to it by hand.
profile: common
	@test ! -e $(PROFILE_DIR)/$(ENV).env || test -n "$(FORCE)" || { \
	  echo "$(PROFILE_DIR)/$(ENV).env exists -- FORCE=1 to overwrite"; exit 1; }
	@mkdir -p $(PROFILE_DIR)
	@terraform init -backend-config=$(DIR)/state.tfvars >/dev/null
	@terraform output -raw env_exports > $(PROFILE_DIR)/$(ENV).env.tmp
	@mv $(PROFILE_DIR)/$(ENV).env.tmp $(PROFILE_DIR)/$(ENV).env
	@echo "wrote $(PROFILE_DIR)/$(ENV).env"
	@echo "add MYSQL_* and MONGO_URL for ask_live.py -- see profiles/example.env"

# Model name/format/version/sku are region-dependent and drift as models are
# retired. Run this BEFORE editing model_deployments -- it lists exactly what
# the deployed resource's region will accept.
#
#   make models RG=denmark-east-rg ENV=raghu
NAME ?= roboshop-$(ENV)-foundry
models:
	@test -n "$(RG)" || { echo "usage: make models RG=<resource-group> [ENV=<name>]"; exit 1; }
	az cognitiveservices account list-models -g $(RG) -n $(NAME) \
	  | jq -r '.[] | "\(.name)\t\(.format)\t\(.version)\t\(.skus[0].name)"' \
	  | sort | column -t

.PHONY: common apply plan destroy dev dev-apply dev-plan dev-destroy \
        new-env output env profile models
