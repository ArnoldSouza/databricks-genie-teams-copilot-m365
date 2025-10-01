variable "subscription_id" {
  description = "Azure Subscription ID usada pelos resources azurerm."
  type        = string
}

variable "project_name" {
  description = "Nome curto do projeto (ex.: genie-chatbot)."
  type        = string
}

variable "environment" {
  description = "Ambiente curto (ex.: tst, dev, prd)."
  type        = string
}

variable "location" {
  description = "Região do Azure (ex.: brazilsouth)."
  type        = string
}

variable "sku_name" {
  description = "SKU do App Service Plan (ex.: F1, B1, P1v3)."
  type        = string
}

variable "bot_sku" {
  description = "SKU do Azure Bot (ex.: F0)."
  type        = string
}

variable "tags" {
  description = "Tags a aplicar. Ex.: { owner = email, product = nome }"
  type        = map(string)
}

variable "azuread_app_display_name" {
  description = "Display name do App Registration (Entra ID) usado pelo Bot."
  type        = string
}

variable "bot_display_name" {
  description = "Display name do Bot."
  type        = string
}

variable "databricks_space_id" {
  description = "ID do espaço do Databricks (Genie Space)"
  type        = string
  sensitive   = true
}

variable "databricks_host" {
  description = "Host do workspace Databricks (ex.: https://adb-XXXXX.XX.azuredatabricks.net)"
  type        = string
  sensitive   = true
}

variable "databricks_token" {
  description = "Token de acesso ao Databricks"
  type        = string
  sensitive   = true
}

variable "databricks_oauth_scopes" {
  description = "Escopos OAuth a solicitar para o service principal gerenciado pelo Databricks"
  type        = list(string)
  default     = ["all-apis", "sql", "offline_access"]
}

variable "databricks_sql_warehouse_id" {
  description = "ID do SQL Warehouse que o Genie deve usar (ex.: 6a3f431e969b35e9)"
  type        = string
  default     = null
}

variable "databricks_catalog_name" {
  description = "Catálogo que contém os dados do Genie (ex.: _databricks_demos)"
  type        = string
  default     = null
}

variable "databricks_schema_name" {
  description = "Schema dentro do catálogo para o Genie (ex.: genie_data)"
  type        = string
  default     = null
}