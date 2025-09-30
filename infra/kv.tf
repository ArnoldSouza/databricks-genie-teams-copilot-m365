locals {
  # segue seu padrão: kv-<project>-<env>-<region_code>
  kv_name = "kv-${local.prefix}"
}

resource "azurerm_key_vault" "kv" {
  name                = local.kv_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # boas práticas
  soft_delete_retention_days = 90
  purge_protection_enabled   = true

  # usaremos RBAC em vez de Access Policies
  rbac_authorization_enabled = true

  # ajuste se você usa rede privada
  public_network_access_enabled = true

  tags = var.tags
}
