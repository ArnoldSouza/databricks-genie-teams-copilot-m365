/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/main.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Azure resources for a Teams Bot + App Service + packaging for Teams,
              along with environment materialization.
 -----------------------------------------------------------------------------
 Purpose:
   Provision the foundational Azure resources for the “Genie – M365 Agents” bot:
   - Resource Group, Linux App Service Plan, Linux Web App (Python 3.13)
   - Azure AD Application, Service Principal, and Client Secret
   - Azure Bot Service and Teams channel
   - Local packaging of Teams assets and environment file (.env)

 Format:
   Terraform HCL. Variables are provided via *.tfvars. Local helpers assemble
   names, paths, and identifiers. No module boundaries are assumed here.

 Usage:
   - Run via Terraform (init/plan/apply) with appropriate Azure credentials.
   - Ensure companion files exist (e.g., manifest.tftpl, ms_teams_manifest.tftpl,
     env.tftpl) and expected directories (../ms_teams/assets, ../ms_teams/app_package).
   - Secrets are exported to local files under ./secrets and ../.env; treat them
     per your organization’s policies and DO NOT commit rendered outputs.

 Notes:
   - Region short codes are mapped in locals for consistent naming.
   - Web App uses Python 3.13 with an aiohttp entry point; adjust only if your
     application start command changes.
   - Teams packaging writes a manifest and zips assets; ensure downstream tooling
     references the generated ZIP.
 -----------------------------------------------------------------------------
*/

locals {
  # Short region codes for naming; extend if needed.
  loc_codes = {
    brazilsouth = "brs"
    eastus      = "eus"
    eastus2     = "eus2"
    westeurope  = "weu"
    northeurope = "neu"
    centralus   = "cus"
    westus      = "wus"
  }

  # Resolve the short code; fallback to var.location if not mapped.
  loc_code = lookup(local.loc_codes, var.location, var.location)

  # Naming prefix for resources (project-env-region).
  prefix = "${var.project_name}-${var.environment}-${local.loc_code}"

  # Canonical resource names.
  rg_name         = "rg-${local.prefix}"
  asp_name        = "asp-${local.prefix}"
  webapp_name     = "app-${local.prefix}"
  bot_name        = "bot-${local.prefix}"
  webapp_hostname = "${local.webapp_name}.azurewebsites.net"

  # Teams packaging paths.
  assets_dir    = "${path.module}/../ms_teams/assets"
  app_package   = "${path.module}/../ms_teams/app_package"
  zip_path      = "${local.app_package}/dbx-genie-m365-app.zip"
  manifest_uuid = random_uuid.teams_app.result

  # Project root and .env output path.
  project_root = "${path.module}/.."
  env_path     = "${local.project_root}/.env"
}

# Resolve the current ARM tenant/subscription for the caller (Azure Resource Manager).
data "azurerm_client_config" "current" {}

# Resolve the current Azure AD caller (used to assign ownership on the App/Service Principal).
data "azuread_client_config" "current" {}

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
    always_on = false
    # App entry point (aiohttp) listening on 0.0.0.0:8000; adjust if your app changes.
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

  # App settings are merged with Key Vault-backed settings provided elsewhere.
  app_settings = merge(
    {
      "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    },
    local.kv_app_settings
  )

  tags = var.tags
}

# ---------- Azure AD Application / Service Principal / Secret (Single-tenant) ----------
resource "azuread_application" "bot_app" {
  display_name     = var.azuread_app_display_name
  sign_in_audience = "AzureADMyOrg" # single tenant

  web {
    homepage_url = "https://${local.webapp_hostname}"
  }
}

# Service Principal with current user as OWNER
resource "azuread_service_principal" "bot_sp" {
  client_id = azuread_application.bot_app.client_id

  owners = [
    data.azuread_client_config.current.object_id
  ]
}

# Make the current user (who ran `az login`) OWNER of the App Registration
resource "azuread_application_owner" "me_app_owner" {
  application_id  = azuread_application.bot_app.id # object ID of the Application
  owner_object_id = data.azuread_client_config.current.object_id
}

# Password lifetime: 2 years (17520 hours)
resource "azuread_application_password" "bot_secret" {
  application_id = azuread_application.bot_app.id
  display_name   = "terraform-generated"
  end_date       = timeadd(timestamp(), "17520h")
}

# ---------- Azure Bot (Single-Tenant) ----------
resource "azurerm_bot_service_azure_bot" "bot" {
  name                = local.bot_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
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
  location            = var.location
  resource_group_name = azurerm_bot_service_azure_bot.bot.resource_group_name
}

# ---------- Local outputs: credentials and packaging ----------
# Ensure a local ./secrets directory exists (not versioned).
resource "null_resource" "secrets_dir" {
  provisioner "local-exec" {
    command = "mkdir -p ${path.module}/secrets"
  }
}

# Write bot credentials to a local JSON file for operational use.
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

# Ensure ../public exists; used to store a manifest consumed elsewhere.
resource "null_resource" "ensure_public_dir" {
  provisioner "local-exec" {
    command     = "mkdir -p ${path.module}/../public"
    interpreter = ["/bin/bash", "-c"]
  }
}

# Generate manifest.json into ../public using a template file.
resource "local_file" "skill_manifest" {
  depends_on = [null_resource.ensure_public_dir]

  content = templatefile("${path.module}/manifest.tftpl", {
    hostname = azurerm_linux_web_app.webapp.default_hostname
    app_id   = azuread_application.bot_app.client_id
  })

  filename        = "${path.module}/../public/manifest.json"
  file_permission = "0644"
}

# Ensure Teams asset and package directories exist.
resource "null_resource" "ensure_ms_teams_dirs" {
  provisioner "local-exec" {
    command     = "mkdir -p ${local.assets_dir} ${local.app_package}"
    interpreter = ["/bin/bash", "-c"]
  }
}

# Render the Teams app manifest into the assets directory.
resource "local_file" "teams_manifest" {
  depends_on = [null_resource.ensure_ms_teams_dirs]

  filename = "${local.assets_dir}/manifest.json"

  content = templatefile("${path.module}/ms_teams_manifest.tftpl", {
    app_id     = azuread_application.bot_app.client_id
    hostname   = azurerm_linux_web_app.webapp.default_hostname
    uuid_value = local.manifest_uuid
  })
}

# Zip the Teams assets into a distributable package.
data "archive_file" "assets_zip" {
  type        = "zip"
  source_dir  = local.assets_dir
  output_path = local.zip_path

  # Ensure the manifest is written before zipping.
  depends_on = [local_file.teams_manifest]
}

# UUID used inside the Teams manifest template.
resource "random_uuid" "teams_app" {}

# Write a local .env file with sensitive values. This is marked sensitive so
# it doesn't leak into Terraform plan/state outputs. Handle the file securely.
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
