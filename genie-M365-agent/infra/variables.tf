/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/variables.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Variable definitions for Azure, Databricks, and project settings.
 -----------------------------------------------------------------------------
 Purpose:
   Centralize input variables for Terraform deployment:
   - Subscription, project conventions, and environment
   - Azure SKUs, tags, app registration, and bot configuration
   - Databricks workspace connection (host, token, space, catalog/schema)

 Format:
   Terraform variable blocks (`variable "..." {}`) with type, description,
   sensitivity, and defaults as appropriate.

 Usage:
   - Values are provided in `terraform.tfvars` or via CLI/environment variables.
   - Sensitive values (tokens, secrets, IDs) are marked as `sensitive = true`
     to prevent accidental exposure in Terraform plans/logs.

 Notes:
   - Defaults are defined only where sensible (OAuth scopes, optional schema/catalog).
   - Ensure values in tfvars or environment match the expected types.
 -----------------------------------------------------------------------------
*/

# ------------------------------
# Azure Subscription / Conventions
# ------------------------------

variable "subscription_id" {
  description = "Azure Subscription ID used for all azurerm resources."
  type        = string
}

variable "project_name" {
  description = "Short project name (e.g., genie-chatbot). Used in resource naming."
  type        = string
}

variable "environment" {
  description = "Environment short code (e.g., tst, dev, prd)."
  type        = string
}

variable "location" {
  description = "Azure region (e.g., brazilsouth)."
  type        = string
}

# ------------------------------
# Resource SKUs
# ------------------------------

variable "sku_name" {
  description = "App Service Plan SKU (e.g., F1, B1, P1v3)."
  type        = string
}

variable "bot_sku" {
  description = "Azure Bot Service SKU (e.g., F0)."
  type        = string
}

# ------------------------------
# Tags
# ------------------------------

variable "tags" {
  description = "Resource tags. Example: { owner = email, product = project_name }"
  type        = map(string)
}

# ------------------------------
# Azure AD Application / Bot
# ------------------------------

variable "azuread_app_display_name" {
  description = "Display name for the Azure AD App Registration used by the Bot."
  type        = string
}

variable "bot_display_name" {
  description = "Display name for the Bot."
  type        = string
}

# ------------------------------
# Databricks Workspace / OAuth
# ------------------------------

variable "databricks_space_id" {
  description = "Databricks Genie Space ID."
  type        = string
  sensitive   = true
}

variable "databricks_host" {
  description = "Databricks workspace host URL (e.g., https://adb-XXXXX.XX.azuredatabricks.net)."
  type        = string
  sensitive   = true
}

variable "databricks_token" {
  description = "Databricks Personal Access Token (PAT)."
  type        = string
  sensitive   = true
}

variable "databricks_oauth_scopes" {
  description = "OAuth scopes requested for the Databricks-managed service principal."
  type        = list(string)
  default     = ["all-apis", "sql", "offline_access"]
}

# ------------------------------
# Databricks Warehouse / Catalog / Schema
# ------------------------------

variable "databricks_sql_warehouse_id" {
  description = "ID of the SQL Warehouse used by Genie (e.g., 6a3f431e969b35e9)."
  type        = string
  default     = null
}

variable "databricks_catalog_name" {
  description = "Databricks catalog containing Genie data (e.g., _databricks_demos)."
  type        = string
  default     = null
}

variable "databricks_schema_name" {
  description = "Databricks schema within the catalog for Genie data (e.g., genie_data)."
  type        = string
  default     = null
}
