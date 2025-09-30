terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    azuread = { source = "hashicorp/azuread", version = "~> 2.50" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    local   = { source = "hashicorp/local", version = "~> 2.5" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
    null    = { source = "hashicorp/null", version = "~> 3.2" }
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.91.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

provider "azuread" {}
provider "archive" {}
provider "local" {}
provider "random" {}