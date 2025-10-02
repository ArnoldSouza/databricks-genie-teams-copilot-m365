# Teams App – Manifest Template

This directory contains **`manifest.template.json`**, which is used by **Terraform** to render the final `manifest.json` for the Microsoft Teams app. The rendered manifest is packaged together with the icons from `ms_teams/assets` to create:

- `ms_teams/app_package/dbx-genie-m365-app.zip`

You can upload this ZIP to Microsoft Teams to test or distribute the bot.

---

## How the package is built

1. Terraform reads `manifest.template.json` and replaces placeholders (IDs, endpoints, domains, etc.).
2. The packaging step creates a ZIP whose **root** contains exactly:
   - `manifest.json` (generated)
   - `color.png`
   - `outline.png`
3. The ZIP is written to `ms_teams/app_package/`.  

> To change icons, replace the files in `ms_teams/assets` (keep the filenames).

---

## Upload to Teams (balanced step-by-step)

Choose **one** of the paths below, depending on your role and scenario.

### A) Developer Portal (recommended for developers)
1. Open **Developer Portal for Teams** (web).
2. Go to **Apps** → **Import app**.
3. Select `ms_teams/app_package/dbx-genie-m365-app.zip`.
4. Review details (name, icons, bot, permissions) and **Save**.
5. Use **Preview in Teams** for testing, or proceed to distribution.

Official docs (overview & import):  
https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/teams-developer-portal  

### B) Teams Admin Center (for tenant admins / org distribution)
1. Go to **Teams Admin Center** → **Teams apps** → **Manage apps**.
2. Select **Upload new app** and choose the ZIP.
3. After upload, ensure the app is **Allowed**.
4. (Optional) Assign or update **app permission policies** and **setup policies** to roll out the app.

Official docs (policies & custom apps):  
https://learn.microsoft.com/microsoftteams/teams-custom-app-policies-and-settings

### C) Teams client side-loading (fast local testing)
1. In the **Teams desktop client**, open **Apps** → **Manage your apps** → **Upload an app**.
2. Choose **Upload a custom app** and select the ZIP.

Official docs (upload in client):  
https://learn.microsoft.com/microsoftteams/platform/concepts/deploy-and-publish/apps-upload

---

## Minimal troubleshooting

- **“Upload an app” not visible in Teams client:** Your tenant policy may block custom app uploads. Ask an admin to enable custom app upload (see policies link above).
- **Upload rejected / invalid package:** Confirm the ZIP contains only `manifest.json`, `color.png`, and `outline.png` at the **root** (no subfolders).  
  Packaging guidance: https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/apps-package
- **Icon issues:** Ensure PNG format and sizes supported by Teams (see packaging guidance).
- **Manifest validation errors:** Re-check fields against the current manifest schema.  
  Schema: https://learn.microsoft.com/microsoftteams/platform/resources/schema/manifest-schema

---

## Repository layout

ms_teams/  
├─ assets/  
│ ├─ color.png  
│ └─ outline.png  
├─ manifest_template/  
│ ├─ manifest.template.json  
│ └─ README.md ← (this file)  
└─ app_package/  
└─ dbx-genie-m365-app.zip ← generated  

---

## Notes

- **Do not edit** the generated `manifest.json` directly—edit `manifest.template.json` and Terraform variables/outputs.
- Microsoft portals evolve; if labels or buttons differ slightly from this guide, rely on the official links above for the latest UI.
