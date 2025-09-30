locals {
  kv_uri = "https://${azurerm_key_vault.kv.name}.vault.azure.net"

  kv_app_settings = {
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_clientid.name})"
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET" = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_clientsecret.name})"
    "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.svc_conn_tenantid.name})"

    "DATABRICKS_SPACE_ID" = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_space_id.name})"
    "DATABRICKS_HOST"     = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_host.name})"
    "DATABRICKS_TOKEN"    = "@Microsoft.KeyVault(SecretUri=${local.kv_uri}/secrets/${azurerm_key_vault_secret.databricks_token.name})"
  }
}
