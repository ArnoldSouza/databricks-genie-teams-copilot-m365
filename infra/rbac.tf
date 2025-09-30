# Quem aplica o TF continua com Officer (para criar/atualizar segredos)
resource "azurerm_role_assignment" "kv_officer_current" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Web App (Managed Identity) -> apenas leitura de secrets
resource "azurerm_role_assignment" "kv_webapp_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.webapp.identity[0].principal_id

  depends_on = [azurerm_linux_web_app.webapp]
}
