/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/rbac.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Azure RBAC assignments for Key Vault access (Officer/User).
 -----------------------------------------------------------------------------
 Purpose:
   Define Azure role assignments (RBAC) required for:
   - The current Terraform principal to manage Key Vault secrets (Officer).
   - The Web App’s managed identity to read secrets from Key Vault (User).

 Format:
   Terraform HCL role assignments bound to the Key Vault scope.

 Usage:
   - Ensure the Key Vault and Web App resources exist before applying RBAC.
   - The Web App assignment depends on the Web App identity being provisioned.
   - Keep these roles minimal and scoped only to what the workload needs.

 Notes:
   - “Key Vault Secrets Officer” allows creation/update of secrets at the vault scope.
   - “Key Vault Secrets User” grants read access to secrets (no write/delete).
   - Consider rotating identities/secrets periodically per your security policy.
 -----------------------------------------------------------------------------
*/

# The identity applying Terraform retains Secrets Officer to create/update secrets.
resource "azurerm_role_assignment" "kv_officer_current" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Web App (Managed Identity) -> read-only access to Key Vault secrets.
resource "azurerm_role_assignment" "kv_webapp_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.webapp.identity[0].principal_id

  # Ensure the Web App identity exists before binding RBAC.
  depends_on = [azurerm_linux_web_app.webapp]
}
