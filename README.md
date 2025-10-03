# Databricks Genie – M365 Agents

<!-- badges: start -->
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![Terraform](https://img.shields.io/badge/Terraform-IaC-623CE4)
![Databricks](https://img.shields.io/badge/Databricks-Unity%20Catalog-orange)
![Project Type](https://img.shields.io/badge/type-solution-informational)
![Last Updated](https://img.shields.io/github/last-commit/ArnoldSouza/databricks-genie-teams-copilot-m365?label=last%20updated&color=brightgreen)
<!-- badges: end -->

# Databricks Genie — M365 Agents

> Bring **Databricks Genie** (natural-language analytics over your Databricks datasets) directly into **Microsoft 365**—via **Teams** and **Copilot Studio**—with secure OAuth (service principal), Terraform IaC, and a business-friendly chat UX.

---

## 🎯 Solution at a glance

This project **exposes Databricks Genie inside Microsoft Teams** and can also be wired into **Copilot Studio** as a **skill**. Genie is Databricks’ GenAI interface that lets people ask **natural-language questions** about tabular datasets and get **interpretable answers** (including SQL). By meeting users **where they already are** (Teams), adoption gets easier and more consistent across the business.

**What’s especially powerful here:**

- ✅ **Teams chat surface** that business users already know, making Genie **approachable** for data exploration.
- 🔌 **Copilot Studio skill integration**, enabling **bot-to-bot handoff**:
  - **Simple skill**: Free-form conversation (echo/Genie) - Execute a free-form prompt against Genie (Databricks) and returns a text result.
  - **Advanced skill**: Runs a free-form prompt and return **5 outputs** (`elapseMs`, `error`, `response`, `status`, `references`, `traceId`) to plug neatly into your Copilot flows.
- 🔐 **Service principal + OAuth** (no runtime PATs) to reach Databricks Unity Catalog.
- 🧰 **Terraform IaC** to deploy and configure Azure resources consistently.

> **This work is a contribution built on top of the original project by _Luiz Carrossoni_ and _Ryan Bates_.**  
> Upstream reference: <https://github.com/carrossoni/DatabricksGenieBOT/tree/main>

**Author**  
Copyright (c) 2025 **Arnold Souza**  
Contact: <arnoldporto@gmail.com> · <https://www.linkedin.com/in/arnoldsouza/>

---

## 🧩 What’s new vs. upstream

- Migrated from **Azure Bot Framework SDK** → **Microsoft 365 Agents SDK**.
- **Service principal + OAuth** to access Databricks (replaces runtime PATs).
- **Terraform** to provision and wire all **Azure** resources.
- **UX/engine**:
  - Friendlier **Welcome**, **Help**, and **Config** menus.
  - **Reset** conversation; visible **app version**.
  - Smart table answers (SQL included when relevant; **auto-limit** columns/rows).
  - **List/switch** Genie Spaces; **list/switch** conversations.
- Cleaner defaults and configuration separation.

---

## 🏗️ Architecture

```mermaid
flowchart TB
  subgraph Azure
    RG[(Resource Group)]
    ASP[App Service Plan]
    MI[Managed Identity]
    BOT[Arure Bot]
    MFS[Api/manifest.json]
    KV[Key Vault]
    APP[Web App]
  end

  subgraph Databricks[Azure Databricks]
    DSP[(Service Principal)]
    UC[Unity Catalog]
    CT[Catalog]
    SC[Database]
    TB[Tables]
    VL[Volumes]
    SPC[Genie Space]
    WH[SQL Warehouse]
  end

  subgraph Teams
    APPK[App Package]
    CHAT[Chatbot]
  end

  subgraph Copilot[Copilot Studio]
    SKI[Skill]
    TOP[Topic/Tool]
    Chatt[Chatbot]
  end

  IaC[[Terraform]] --> RG
  RG --> ASP
  ASP --> APP
  BOT --> MFS
  APP <--> MI <--> KV
  APP --> BOT

  IaC --> DSP
  DSP --> UC
  UC -->|Use Catalog| CT
  CT --> |Use Schema |SC
  SC --> |Select |TB
  SC --> |Read Volume|VL
  DSP --> |Can Run| SPC
  DSP --> |Can Use| WH

  APPK --> CHAT

  MFS --> SKI
  SKI --> TOP
  TOP --> Chatt
  Chatt -->|Teams Channel| CHAT

  BOT -->|Distribute| APPK

  ```

---

## 🔄 Runtime message flow (who talks to whom)

```mermaid
sequenceDiagram
  participant User as Teams User
  participant Teams as Microsoft Teams
  participant Bot as Azure Bot
  participant App as App Service (Aiohttp)
  participant SDK as M365 Agents SDK
  participant KV as Azure Key Vault
  participant DBX as Databricks (Unity Catalog)

  User->>Teams: Sends message
  Teams->>Bot: Deliver incoming activity
  Bot->>App: POST /api/messages
  App->>SDK: Construct agent turn
  SDK->>KV: Fetch secrets / settings
  SDK->>DBX: Query (OAuth client credentials)
  DBX-->>SDK: Results (answer + SQL when applicable)
  SDK-->>App: Response payload
  App-->>Bot: Reply activity
  Bot-->>Teams: Send message back
  Teams-->>User: Render answer


```

---

## 🖼️ Feature gallery (placeholders)

> Save your screenshots into **`docs/images/`** with these filenames:

| Feature | Screenshot |
|---|---|
| **Welcome & Help menus** | ![Welcome and Help](docs/images/01-welcome-help.png) |
| **Config & Reset** | ![Config and Reset](docs/images/02-config-reset.png) |
| **Genie Q&A in Teams** | ![Genie Q&A in Teams](docs/images/03-genie-qa-teams.png) |
| **Smart tables (SQL + truncate)** | ![Smart tables](docs/images/04-smart-tables-sql-limit.png) |
| **List & switch Spaces** | ![Spaces switch](docs/images/05-list-switch-spaces.png) |
| **List & switch conversations** | ![Conversations switch](docs/images/06-list-switch-conversations.png) |
| **Copilot Advanced Skill (5 outputs)** | ![Copilot skill](docs/images/07-copilot-advanced-skill.png) |
| **Terraform apply (Azure)** | ![Terraform apply](docs/images/08-terraform-apply.png) |

> Tip: Prefer 1280×720 (or similar) for consistent display.

---

## 🧠 Copilot Studio skills (two patterns)

**Simple Genie skill**  
- **Input**: `prompt`  
- **Output**: `answer`  
- **Use when**: you just need a quick “ask Genie” step in a Copilot flow.

**Advanced Genie skill (recommended)**  
- **Inputs**: `prompt`, optional `context`  
- **Outputs (5)**:
  1. `elapsedMs` 
  2. `error`
  3. `response`  
  4. `status`
  5. `traceID`

This makes it easy to branch on `status`, surface/log `error`, display `response`.

---

## ✅ Compatibility matrix

| Component | Version |
|---|---|
| Python | **3.13.7** |
| Terraform | **1.13.3** |
| Azure CLI | **2.77.0** |
| Agents Playground (CLI) | **0.2.18** |
| DevTunnel | **1.0.1435+d49a94cc24** |
| Cloud | **Azure** (Unix-like OS recommended for IaC/CLI: macOS, Linux, or WSL) |

⚠️ **Attention:** This project can only run on Unix-like OS for IaC/CLI: macOS, Linux, or WSL (Windows Subsystem for Linux).

> Runtime libraries are pinned in `genie-M365-agent/requirements.txt`.

---

## 🚀 Quick start

### 1) Databricks (pre-deploy)
1. Import: `genie-M365-agent/examples/notebooks/Genie Spaces - F1 Dataset Ingestion & Delta Tables.ipynb`
2. In the notebook, Edit variables in **(2) Configuration (Python)**: `CATALOG`, `SCHEMA`, `VOLUME`, `CATALOG_MANAGED_LOCATION`
3. Run the notebook (requires privileges to create catalog/schema/volume/tables)
4. Create a **Genie Space** via UI and copy the `<room-id>` from the URL

### 2) Azure (Terraform)
Ensure you have permissions to create **Resource Groups**, **Cloud Resources**, **Service Principals**, and **Managed Identities**.  
For bootstrap, it is necessary a **Databricks PAT** (Workspace Admin + edit on target catalog/schema). Keep it only in `terraform.tfvars`.

```bash
cd genie-M365-agent/infra
terraform init
terraform validate
terraform plan -out plan.tfplan
terraform apply "plan.tfplan"
```

### 3) Local run & test (optional)

```bash
cd genie-M365-agent
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m aiohttp.web -H 0.0.0.0 -P 8000 src.main:create_app
```

Agents Playground:

```bash
agentsplayground -e "http://localhost:3978/api/messages" \
    --channel "emulator" \
    --client-id "<CLIENT_ID>" \
    --client-secret "<CLIENT_SECRET>" \
    --tenant-id "<TENANT_ID>"
```

Optional **DevTunnel**:

```bash
devtunnel host -a -p 3978
```

- If using DevTunnel for testing, update:
    - Your **Bot** message endpoint to: `https://<your dev tunnel>/api/messages`
    - Your **App Registration** Home Page URL to: `https://<your dev tunnel>`
- Remember: **Revert** both to the App Service URL before going live.

---

## 🔐 Security & secrets

- Use **Azure Key Vault** (or environment variables). **Never commit secrets.**
- Databricks runtime access uses **OAuth client credentials** with a **Service Principal**.
- For Terraform bootstrap, a **Databricks PAT** is required. Store it **only** in `terraform.tfvars` locally or in a secure CI secret store.

---

## 📚 Deep-dive docs

- `docs/DATABRICKS-PREDEPLOY.md` — Prepare Databricks (notebook, Space, URL/room-id).
- `docs/DEPLOY-AZURE.md` — Terraform deployment (variables, outputs, checklist).
- `docs/SETUP-ENV.md` — Python venv, dependencies, local run.
- `docs/TEST-LOCAL.md` — Teams/Web Chat testing + DevTunnel/revert.
- `docs/DEPLOY-MANUAL.md` — Manual Azure deployment (no Terraform).
- `docs/TUTORIAL-COPILOT-SKILL.md` — *(Placeholder)*: Use this agent as a Copilot skill.
- `docs/TUTORIAL-TEAMS-APP-PACKAGE.md` — *(Placeholder)*: Package/sideload the Teams app zip.

---

## 🙌 Acknowledgements & license

- Original authors: **Luiz Carrossoni** and **Ryan Bates** — <https://github.com/carrossoni/DatabricksGenieBOT/tree/main>  
- This contribution: **Arnold Souza**

**License:** MIT — see [LICENSE](LICENSE)

