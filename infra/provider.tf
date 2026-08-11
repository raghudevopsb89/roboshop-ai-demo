terraform {
  # optional() in variable types needs 1.3+.
  required_version = ">= 1.3"

  backend "azurerm" {}

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      # Pinned at 4.27+. Originally required because earlier versions hardcoded
      # model.format to "OpenAI" only, so any non-OpenAI format (the old
      # "Mistral AI" deployment) failed at plan time --
      # hashicorp/terraform-provider-azurerm#29143. Only OpenAI-format models
      # are deployed now, but there is no reason to go back.
      version = "~> 4.27"
    }
  }
}

provider "azurerm" {
  features {}
}
