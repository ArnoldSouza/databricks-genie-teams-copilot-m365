# CLIENT ID -> vem do azuread_application
resource "azurerm_key_vault_secret" "svc_conn_clientid" {
  name         = "svc-conn-clientid"
  value        = azuread_application.bot_app.client_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current, # quem aplica o TF pode criar segredos
    azuread_application.bot_app                 # garante criação do app antes do segredo
  ]
}

# CLIENT SECRET -> vem do azuread_application_password
resource "azurerm_key_vault_secret" "svc_conn_clientsecret" {
  name         = "svc-conn-clientsecret"
  value        = azuread_application_password.bot_secret.value
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    azuread_application.bot_app,
    azuread_application_password.bot_secret # garante criação/rotina do secret
  ]
}

# TENANT ID -> vem do data.azurerm_client_config
resource "azurerm_key_vault_secret" "svc_conn_tenantid" {
  name         = "svc-conn-tenantid"
  value        = data.azurerm_client_config.current.tenant_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

resource "azurerm_key_vault_secret" "databricks_space_id" {
  name         = "databricks-space-id"
  value        = var.databricks_space_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

resource "azurerm_key_vault_secret" "databricks_host" {
  name         = "databricks-host"
  value        = var.databricks_host
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}

resource "azurerm_key_vault_secret" "databricks_sp_client_id" {
  name         = "databricks-sp-client-id"
  value        = databricks_service_principal.genie.application_id
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    databricks_service_principal.genie
  ]
}

resource "azurerm_key_vault_secret" "databricks_sp_client_secret" {
  name         = "databricks-sp-client-secret"
  value        = databricks_service_principal_secret.genie_oauth.secret
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current,
    databricks_service_principal_secret.genie_oauth
  ]
}

resource "azurerm_key_vault_secret" "databricks_token" {
  name         = "databricks-token"
  value        = var.databricks_token
  key_vault_id = azurerm_key_vault.kv.id

  depends_on = [
    azurerm_role_assignment.kv_officer_current
  ]
}
