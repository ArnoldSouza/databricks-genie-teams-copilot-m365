# Publish Microsoft Teams app

Terraform may generate `ms_teams/app_package/dbx-genie-m365-app.zip`. You can use it as‑is or customize the manifest.

## Options

- **Sideload for testing** (developer tenants):
  - Teams client → **Apps** → **Manage your apps** → **Upload an app** → **Upload a custom app**.
- **Organizational catalog publish**:
  - Submit your package to the org catalog following your tenant policies.
- **Azure Bot quick preview**:
  - In Azure, open your **Bot** → **Channels** → *Open in Teams* (when available).

For details, see official Teams docs (linked in References).


---

### GIFs (placeholders)

1. **Sideload app (developer flow)**  
   ![GIF – Sideload](gifs/teams-01-sideload.gif)

2. **Organization catalog publish**  
   ![GIF – Org catalog](gifs/teams-02-org-catalog.gif)

3. **Preview via Azure Bot channels**  
   ![GIF – Open in Teams](gifs/teams-03-open-in-teams.gif)

4. **Developer portal preview**  
   ![GIF – Dev portal preview](gifs/teams-04-dev-portal.gif)
