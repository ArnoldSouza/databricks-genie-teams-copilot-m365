/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/providers.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Provider configurations and version constraints for Azure, Databricks,
              and supporting HashiCorp providers. Documentation-only pass; no logic
              or version requirements were changed.
 -----------------------------------------------------------------------------
 Purpose:
   Define Terraform provider requirements and configure connections to:
   - Azure Resource Manager (azurerm)
   - Azure Active Directory (azuread)
   - Databricks (databricks provider)
   - Supporting HashiCorp providers (random, local, archive, null)

 Format:
   Terraform HCL. Providers are pinned with version constraints to ensure
   reproducibility. Variables are used for sensitive connection details.

 Usage:
   - Run `terraform init` to download and install the required providers.
   - Ensure `var.subscription_id`, `var.databricks_host`, and `var.databricks_token`
     are provided (via tfvars, env vars, or Terraform Cloud/Workspaces).
   - Avoid committing tokens or credentials into version control.

 Notes:
   - `azurerm` requires `features {}` block, even if empty.
   - `databricks` provider supports both host+token and AAD auth; here host+token
     is used for simplicity, but enterprise setups may prefer service principals.
   - Version pinning uses conservative ranges (`~>` or `>=`) to balance stability
     and ability to upgrade.
 -----------------------------------------------------------------------------
*/

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.91.0"
    }
  }
}

# Azure Resource Manager provider
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# Databricks provider (host + PAT token authentication)
provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

# Azure AD provider
provider "azuread" {}

# Supporting providers
provider "archive" {}
provider "local" {}
provider "random" {}
