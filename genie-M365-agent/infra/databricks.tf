/*
 -----------------------------------------------------------------------------
 Project: Databricks Genie – M365 Agents
 File: databricks-genie-M365_agents/infra/databricks.tf
 Version: 0.1.0 (documentation pass, 2025-10-01)
 Author: Arnold Souza (arnoldporto@gmail.com | https://www.linkedin.com/in/arnoldsouza/)
 License: MIT
 Derived from: Luiz Carrossoni and Ryan Bates — see: https://github.com/carrossoni/DatabricksGenieBOT/tree/main
 Description: Infrastructure as Code (Terraform).
              This pass improves documentation and block comments only; no logic
              or resource arguments were changed.
 -----------------------------------------------------------------------------
*/

# -----------------------------------------------------------------------------
# 1) Service Principal in the Databricks workspace
#    - Enabled for workspace and SQL access.
# -----------------------------------------------------------------------------
resource "databricks_service_principal" "genie" {
  display_name          = "Genie M365 Integration"
  active                = true
  workspace_access      = true
  databricks_sql_access = true
}

# -----------------------------------------------------------------------------
# 2) OAuth Client Secret for the Service Principal
#    - Used by the application to authenticate (OAuth M2M flow).
# -----------------------------------------------------------------------------
resource "databricks_service_principal_secret" "genie_oauth" {
  service_principal_id = databricks_service_principal.genie.id
}

# -----------------------------------------------------------------------------
# 3a) Grant CAN_RUN on the configured Genie Space via REST API
#     Notes:
#       - Uses a local-exec provisioner (bash + curl) to call Permissions API.
#       - Reads current permissions; if CAN_RUN is already present for the SP,
#         exits successfully (idempotent behavior).
#       - Otherwise, PATCHes the permissions to add CAN_RUN.
#       - Re-runs based on 'triggers' (timestamp + relevant inputs).
#     Requirements:
#       - var.databricks_token must be a PAT with workspace and catalog
#         permission to manage the objects.
# -----------------------------------------------------------------------------
resource "null_resource" "grant_space_can_run" {
  triggers = {
    # force re-execution when something relevant changes
    always_run = timestamp()
    host       = var.databricks_host
    space      = var.databricks_space_id
    spn        = databricks_service_principal.genie.application_id
    # if you use a PAT for infra, include the token hash to detect changes
    token_hash = md5(var.databricks_token)
  }

  # ensure bash
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<-EOT
      set -euo pipefail

      HOST="${var.databricks_host}"
      TOKEN="${var.databricks_token}"
      SPACE="${var.databricks_space_id}"
      # For the Permissions API, this is the Service Principal Application (client) ID (GUID)
      SPN="${databricks_service_principal.genie.application_id}"

      # Remove trailing slash (escape with $$ in HCL)
      HOST="$${HOST%/}"

      CURRENT="$(mktemp)"
      TMP="$(mktemp)"
      trap 'rm -f "$CURRENT" "$TMP"' EXIT

      # Read current state (ignore error if 404)
      curl -fsS -o "$CURRENT" \
        -X GET "$HOST/api/2.0/permissions/genie/$SPACE" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        || true

      # If SP already has CAN_RUN, exit successfully
      if python3 - "$SPN" "$CURRENT" <<'PY'
import json, sys
spn, path = sys.argv[1], sys.argv[2]
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except Exception:
    sys.exit(1)
for ace in payload.get("access_control_list", []):
    if ace.get("service_principal_name") == spn:
        perms = [p.get("permission_level") for p in ace.get("all_permissions", []) if p.get("permission_level")]
        if "CAN_RUN" in perms:
            sys.exit(0)
sys.exit(1)
PY
      then
        printf 'Service principal %s already has CAN_RUN on space %s\n' "$SPN" "$SPACE"
        exit 0
      fi

      # Build PATCH body (no jq dependency)
      BODY=$(
        printf '%s' '{"access_control_list":[{"service_principal_name":"'"$SPN"'","permission_level":"CAN_RUN"}]}'
      )

      HTTP_CODE=$(curl -sS -w '%%{http_code}' -o "$TMP" \
        -X PATCH "$HOST/api/2.0/permissions/genie/$SPACE" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$BODY")

      printf 'PATCH /api/2.0/permissions/genie/%s -> HTTP %s\n' "$SPACE" "$HTTP_CODE"
      head -c 400 "$TMP" || true; echo

      case "$HTTP_CODE" in
        2??) exit 0 ;;
        *)   exit 1 ;;
      esac
    EOT
  }
}

# -----------------------------------------------------------------------------
# 3b) Grant CAN_USE on a specific SQL Warehouse
#     - Conditional via count when var.databricks_sql_warehouse_id is null.
# -----------------------------------------------------------------------------
resource "databricks_permissions" "warehouse_can_use" {
  count = var.databricks_sql_warehouse_id == null ? 0 : 1

  sql_endpoint_id = var.databricks_sql_warehouse_id

  access_control {
    service_principal_name = databricks_service_principal.genie.application_id
    permission_level       = "CAN_USE"
  }

  depends_on = [databricks_service_principal.genie]
}

# -----------------------------------------------------------------------------
# 3c) Grant catalog privileges
#     - Grants USE_CATALOG to the Service Principal.
# -----------------------------------------------------------------------------
resource "databricks_grants" "catalog" {
  count = var.databricks_catalog_name == null ? 0 : 1

  catalog = var.databricks_catalog_name

  grant {
    principal  = databricks_service_principal.genie.application_id
    privileges = ["USE_CATALOG"]
  }

  depends_on = [databricks_service_principal.genie]
}

# -----------------------------------------------------------------------------
# 3d) Grant schema privileges
#     - Grants USE_SCHEMA, SELECT, EXECUTE, READ_VOLUME on the target schema.
# -----------------------------------------------------------------------------
resource "databricks_grants" "schema" {
  count = var.databricks_catalog_name == null || var.databricks_schema_name == null ? 0 : 1

  schema = "${var.databricks_catalog_name}.${var.databricks_schema_name}"

  grant {
    principal  = databricks_service_principal.genie.application_id
    privileges = ["USE_SCHEMA", "SELECT", "EXECUTE", "READ_VOLUME"]
  }

  depends_on = [databricks_service_principal.genie, databricks_grants.catalog]
}

# -----------------------------------------------------------------------------
# 4) Export Client ID / Secret to a local file (developer convenience)
#    - Writes a minimal JSON with SP display name, client_id and client_secret.
#    - File and directory permissions are restricted for safety.
# -----------------------------------------------------------------------------
resource "null_resource" "secrets_dir_genie" {
  provisioner "local-exec" {
    command = "mkdir -p ./secrets"
  }
}

resource "local_file" "genie_sp_credentials" {
  filename = "./secrets/genie_m365_integration.json"
  content = jsonencode({
    service_principal_name = databricks_service_principal.genie.display_name
    client_id              = databricks_service_principal.genie.application_id
    client_secret          = databricks_service_principal_secret.genie_oauth.secret
    note                   = "Generated by Terraform"
  })
  depends_on = [
    null_resource.secrets_dir_genie,
    databricks_service_principal_secret.genie_oauth
  ]

  # Restrictive permissions for security
  file_permission      = "0600"
  directory_permission = "0700"
}
