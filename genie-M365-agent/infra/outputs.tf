/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/outputs.tf
 Version: 0.1.0 (documentation pass, 2025-10-02)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              Outputs for core Azure resources, Bot credentials, Teams packaging,
              and environment file locations. 
 -----------------------------------------------------------------------------
 Purpose:
   Define Terraform outputs for inspection and integration:
   - Resource names and hostnames
   - Bot credentials (Client ID, secret file path)
   - Teams manifest and ZIP package
   - Generated .env file path

 Format:
   Terraform HCL output blocks with descriptions.

 Usage:
   - After running `terraform apply`, view outputs via `terraform output`.
   - Sensitive values are not exposed directly (secrets are written to files).
   - Use these outputs for integration in CI/CD pipelines or manual validation.

 Notes:
   - Do not rely on outputs to distribute secrets; use secure secret stores instead.
   - Paths reference files generated locally (not checked into version control).
 -----------------------------------------------------------------------------
*/

# ------------------------------
# Core Azure resources
# ------------------------------
output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "app_service_plan_name" {
  value = azurerm_service_plan.asp.name
}

output "web_app_name" {
  value = azurerm_linux_web_app.webapp.name
}

output "web_app_default_hostname" {
  value = azurerm_linux_web_app.webapp.default_hostname
}

# ------------------------------
# Bot credentials
# ------------------------------
output "bot_app_client_id" {
  description = "Microsoft App ID (Client ID) of the Bot."
  value       = azuread_application.bot_app.client_id
}

# Outputs only the path of the secret file (does not expose secret inline).
output "bot_app_secret_file" {
  description = "Local file (not versioned) containing the client_secret."
  value       = local_file.bot_credentials.filename
}

# ------------------------------
# Teams packaging and manifests
# ------------------------------
output "manifest_path" {
  description = "Manifest file used in Copilot Studio Skill."
  value       = local_file.skill_manifest.filename
}

output "teams_zip_path" {
  description = "Path to the generated Teams package (ZIP)."
  value       = local.zip_path
}

output "teams_manifest_path" {
  description = "Path to the generated Teams manifest.json file."
  value       = local_file.teams_manifest.filename
}

# ------------------------------
# Environment file (.env)
# ------------------------------
output "project_env_path" {
  description = "Path to the generated .env file (contains sensitive values)."
  value       = local_sensitive_file.project_env.filename
}
