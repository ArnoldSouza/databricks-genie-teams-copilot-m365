/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/secrets.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Key Vault secrets provisioning for Azure AD app and Databricks
              integration.
 -----------------------------------------------------------------------------
 Purpose:
   Store sensitive configuration values in Azure Key Vault:
   - Service connection credentials (Client ID, Client Secret, Tenant ID).
   - Databricks identifiers and credentials (space, host, service principal).
   - Databricks personal access token (PAT).

 Format:
   Terraform HCL `azurerm_key_vault_secret` resources. Each secret is scoped
   to a single value and bound to the target Key Vault.

 Usage:
   - Requires prior creation of the Key Vault and role assignments.
   - Consumed by App Services and automation via Key Vault references.
   - Dependencies ensure that upstream resources (apps, secrets, SPs) exist
     before attempting to create Key Vault entries.

 Notes:
   - Naming follows consistent convention: `svc-conn-*` for service connection,
     `databricks-*` for Databricks integration.
   - Secrets are created with depends_on to guarantee order and prevent race
     conditions with identity/secret creation.
   - Rotate and manage secrets per organizational policy.
 -----------------------------------------------------------------------------
*/

# ------------------------------
# Service Connection (Azure AD)
# ------------------------------

# CLIENT ID -> from azuread_application
resource "azurerm_key_vault_secret" "svc_conn_clientid" {
  name         = "svc-conn-clientid"
  value        = azuread_application.bot_app.client_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current, # TF executor has permission to create secrets
    azuread_application.bot_app                 # ensure the application exists before creating the secret
  ]
}

# CLIENT SECRET -> from azuread_application_password
resource "azurerm_key_vault_secret" "svc_conn_clientsecret" {
  name         = "svc-conn-clientsecret"
  value        = azuread_application_password.bot_secret.value
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    azuread_application.bot_app,
    azuread_application_password.bot_secret # ensure the application password is created
  ]
}

# TENANT ID -> from data.azurerm_client_config
resource "azurerm_key_vault_secret" "svc_conn_tenantid" {
  name         = "svc-conn-tenantid"
  value        = data.azurerm_client_config.current.tenant_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

# ------------------------------
# Databricks Integration
# ------------------------------

# Databricks Space ID (provided by variable)
resource "azurerm_key_vault_secret" "databricks_space_id" {
  name         = "databricks-space-id"
  value        = var.databricks_space_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

# Databricks Host (workspace URL)
resource "azurerm_key_vault_secret" "databricks_host" {
  name         = "databricks-host"
  value        = var.databricks_host
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

# Databricks Service Principal Client ID
resource "azurerm_key_vault_secret" "databricks_sp_client_id" {
  name         = "databricks-sp-client-id"
  value        = databricks_service_principal.genie.application_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    databricks_service_principal.genie
  ]
}

# Databricks Service Principal Client Secret
resource "azurerm_key_vault_secret" "databricks_sp_client_secret" {
  name         = "databricks-sp-client-secret"
  value        = databricks_service_principal_secret.genie_oauth.secret
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    databricks_service_principal_secret.genie_oauth
  ]
}

# Databricks Personal Access Token (PAT)
resource "azurerm_key_vault_secret" "databricks_token" {
  name         = "databricks-token"
  value        = var.databricks_token
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}
