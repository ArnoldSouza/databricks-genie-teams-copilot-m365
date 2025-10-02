/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/appsettings_kv.tf
 Version: 0.1.0 (documentation pass, 2025-10-01)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform) – Application settings
              injected from Azure Key Vault into App Service configuration.
 -----------------------------------------------------------------------------
*/

locals {
  # ----------------------------------------------------------------------------
  # Construct the base Key Vault URI for secret references
  # ----------------------------------------------------------------------------
  kv_uri = "https://${azurerm_key_vault.kv.name}.vault.azure.net"

  # ----------------------------------------------------------------------------
  # Application settings for the App Service, pulling values from Key Vault.
  # Each entry corresponds to an environment variable the application expects.
  #
  #   - CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID/SECRET/TENANTID
  #       Used for Microsoft identity (MSAL) connections.
  #
  #   - DATABRICKS_* values
  #       Used for Databricks Genie integration (space, host, OAuth client).
  #
  #   - DATABRICKS_OAUTH_SCOPES
  #       Passed directly from variable list (joined as space-separated string).
  #
  # Note: The @Microsoft.KeyVault(SecretUri=...) syntax is required by Azure
  #       App Service to pull secrets dynamically from Key Vault.
  # ----------------------------------------------------------------------------
  kv_app_settings = {
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_clientid.name})"
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET" = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_clientsecret.name})"
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_tenantid.name})"

    "DATABRICKS_SPACE_ID"      = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_space_id.name})"
    "DATABRICKS_HOST"          = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_host.name})"
    "DATABRICKS_CLIENT_ID"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_sp_client_id.name})"
    "DATABRICKS_CLIENT_SECRET" = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_sp_client_secret.name})"

    # List of OAuth scopes is joined into a single string separated by spaces
    "DATABRICKS_OAUTH_SCOPES" = "${join(" ", var.databricks_oauth_scopes)}"
  }
}
