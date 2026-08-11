# Remote state for a new person's environment. ENV_PLACEHOLDER is substituted
# by `make new-env ENV=<yourname>`, giving each person their own state blob in
# the shared backend container.
resource_group_name  = "denmark-east-rg"
storage_account_name = "rdevopsb89"
container_name       = "tfstates"
key                  = "roboshop-ai-demo/ENV_PLACEHOLDER/terraform.tfstate"
