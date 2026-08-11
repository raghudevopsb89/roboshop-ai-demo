terraform {
  # optional() in variable types needs 1.3+.
  required_version = ">= 1.3"

  backend "azurerm" {}

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      # 4.27+ is required: earlier versions hardcoded model.format to "OpenAI"
      # only, which makes the Ministral-3B deployment ("Mistral AI") fail at
      # plan time. See hashicorp/terraform-provider-azurerm#29143.
      version = "~> 4.27"
    }
  }
}

provider "azurerm" {
  features {}
}
