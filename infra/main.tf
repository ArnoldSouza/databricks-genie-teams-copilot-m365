locals {
  # Códigos curtos por região para nomes
  loc_codes = {
    brazilsouth = "brs"
    eastus      = "eus"
    eastus2     = "eus2"
    westeurope  = "weu"
    northeurope = "neu"
    centralus   = "cus"
    westus      = "wus"
  }

  loc_code = lookup(local.loc_codes, var.location, var.location)
  prefix   = "${var.project_name}-${var.environment}-${local.loc_code}"

  rg_name         = "rg-${local.prefix}"
  asp_name        = "asp-${local.prefix}"
  webapp_name     = "app-${local.prefix}"
  bot_name        = "bot-${local.prefix}"
  webapp_hostname = "${local.webapp_name}.azurewebsites.net"

  assets_dir    = "${path.module}/../ms_teams/assets"
  app_package   = "${path.module}/../ms_teams/app_package"
  zip_path      = "${local.app_package}/dbx-genie-m365-app.zip"
  manifest_uuid = random_uuid.teams_app.result

  project_root = "${path.module}/.."
  env_path     = "${local.project_root}/.env"
}


# Para obter o tenant_id atual
data "azurerm_client_config" "current" {}

# ---------- Resource Group ----------
resource "azurerm_resource_group" "rg" {
  name     = local.rg_name
  location = var.location
  tags     = var.tags
}

# ---------- App Service Plan (Linux) ----------
resource "azurerm_service_plan" "asp" {
  name                = local.asp_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  os_type  = "Linux"
  sku_name = var.sku_name

  tags = var.tags
}

# ---------- Linux Web App (Publish: code, Python 3.13) ----------
resource "azurerm_linux_web_app" "webapp" {
  name                = local.webapp_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = azurerm_service_plan.asp.id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on        = false
    app_command_line = "python3 -m aiohttp.web -H 0.0.0.0 -P 8000 src.main:create_app"

    application_stack {
      python_version = "3.13"
    }
  }

  logs {
    http_logs {
      file_system {
        retention_in_days = 3
        retention_in_mb   = 35
      }
    }
  }

  app_settings = merge(
    {
      "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    },
    local.kv_app_settings
  )

  tags = var.tags
}

# ---------- Azure AD Application / SP / Secret (Single-tenant) ----------
resource "azuread_application" "bot_app" {
  display_name     = var.azuread_app_display_name
  sign_in_audience = "AzureADMyOrg" # single tenant

  web {
    homepage_url = "https://${local.webapp_hostname}"
  }
}

resource "azuread_service_principal" "bot_sp" {
  client_id = azuread_application.bot_app.client_id
}

# 2 anos (17520 horas)
resource "azuread_application_password" "bot_secret" {
  application_id    = azuread_application.bot_app.id
  display_name      = "terraform-generated"
  end_date_relative = "17520h"
}

# ---------- Azure Bot (Single-Tenant) ----------
resource "azurerm_bot_service_azure_bot" "bot" {
  name                = local.bot_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = "global"
  sku                 = var.bot_sku

  display_name = var.bot_display_name

  microsoft_app_id        = azuread_application.bot_app.client_id
  microsoft_app_tenant_id = data.azurerm_client_config.current.tenant_id
  microsoft_app_type      = "SingleTenant"

  endpoint = "https://${azurerm_linux_web_app.webapp.default_hostname}/api/messages"
}

# ---------- Teams Channel ----------
resource "azurerm_bot_channel_ms_teams" "bot_teams" {
  bot_name            = azurerm_bot_service_azure_bot.bot.name
  location            = "global"
  resource_group_name = azurerm_bot_service_azure_bot.bot.resource_group_name
}

# ---------- Exportar credenciais em arquivo local (NÃO versionado) ----------
resource "null_resource" "secrets_dir" {
  provisioner "local-exec" {
    command = "mkdir -p ${path.module}/secrets"
  }
}

resource "local_file" "bot_credentials" {
  filename = "${path.module}/secrets/bot_credentials.json"
  content = jsonencode({
    client_id     = azuread_application.bot_app.client_id
    client_secret = azuread_application_password.bot_secret.value
    tenant_id     = data.azurerm_client_config.current.tenant_id
    endpoint      = "https://${azurerm_linux_web_app.webapp.default_hostname}/api/messages"
  })
  depends_on = [null_resource.secrets_dir]
}

# Garante que a pasta ../public exista (rodando a partir de infra/)
resource "null_resource" "ensure_public_dir" {
  provisioner "local-exec" {
    command     = "mkdir -p ${path.module}/../public"
    interpreter = ["/bin/bash", "-c"]
  }
}

# Manifest.json (gera/sobrescreve em ../public)
resource "local_file" "skill_manifest" {
  depends_on = [null_resource.ensure_public_dir]

  content = templatefile("${path.module}/manifest.tftpl", {
    hostname = azurerm_linux_web_app.webapp.default_hostname
    app_id   = azuread_application.bot_app.client_id
  })

  filename        = "${path.module}/../public/manifest.json"
  file_permission = "0644"
}

resource "null_resource" "ensure_ms_teams_dirs" {
  provisioner "local-exec" {
    command     = "mkdir -p ${local.assets_dir} ${local.app_package}"
    interpreter = ["/bin/bash", "-c"]
  }
}

resource "local_file" "teams_manifest" {
  depends_on = [null_resource.ensure_ms_teams_dirs]

  filename = "${local.assets_dir}/manifest.json"

  content = templatefile("${path.module}/ms_teams_manifest.tftpl", {
    # mapeamentos conforme você pediu:
    app_id     = azuread_application.bot_app.client_id
    hostname   = azurerm_linux_web_app.webapp.default_hostname
    uuid_value = local.manifest_uuid
  })
}

data "archive_file" "assets_zip" {
  type        = "zip"
  source_dir  = local.assets_dir
  output_path = local.zip_path

  # garante que o manifest foi escrito antes de zipar
  depends_on = [local_file.teams_manifest]
}

resource "random_uuid" "teams_app" {}

# Recurso que escreve o .env de forma SENSÍVEL (não vaza no state/plan)
resource "local_sensitive_file" "project_env" {
  filename        = local.env_path
  file_permission = "0600"

  content = templatefile("${path.module}/env.tftpl", {
    client_id     = azuread_application.bot_app.client_id
    client_secret = azuread_application_password.bot_secret.value
    tenant_id     = data.azurerm_client_config.current.tenant_id

    databricks_space_id      = var.databricks_space_id
    databricks_host          = var.databricks_host
    databricks_client_id     = databricks_service_principal.genie.application_id
    databricks_client_secret = databricks_service_principal_secret.genie_oauth.secret
    databricks_oauth_scopes  = join(" ", var.databricks_oauth_scopes)
  })
}