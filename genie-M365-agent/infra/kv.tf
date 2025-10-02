/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/kv.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Azure Key Vault provisioning with recommended practices.
              This pass improves documentation and block comments only; no logic
              or resource arguments were changed.
 -----------------------------------------------------------------------------
 Purpose:
   Provision an Azure Key Vault to store application secrets and configuration.
   Naming convention and security best practices are applied.

 Format:
   Terraform HCL. The Key Vault name is parameterized via local variables.

 Usage:
   - Run via Terraform as part of infra deployment.
   - Adjust variables (e.g., tags, prefix, region) in respective *.tfvars files.
   - Key Vault secrets will be referenced by applications and IaC templates.

 Notes:
   - Naming convention follows: kv-<project>-<env>-<region_code>.
   - RBAC authorization is enabled instead of access policies.
   - Adjust network access settings if deploying in private network environments.
 -----------------------------------------------------------------------------
*/

locals {
  # Naming convention: kv-<project>-<env>-<region_code>
  kv_name = "kv-${local.prefix}"
}

resource "azurerm_key_vault" "kv" {
  name                = local.kv_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Best practices: enable soft-delete and retention
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  # Use RBAC instead of legacy Access Policies
  rbac_authorization_enabled = true

  # Adjust if deploying with private network restrictions
  public_network_access_enabled = true

  tags = var.tags
}
