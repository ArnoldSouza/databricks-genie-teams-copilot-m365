# Copilot Studio skill (two patterns)

## Simple Genie skill
- **Input**: `prompt`
- **Output**: `answer`
- **Use when**: a quick “ask Genie” step is enough.

## Advanced Genie skill (recommended)
- **Inputs**: `prompt`, optional `context`
- **Outputs (5)**:
  1. `elapsedMs`
  2. `error`
  3. `response`
  4. `status`
  5. `traceId`

**How to wire**
1. Copilot Studio → Plugins/Skills → **Add skill**.
2. Choose **External web service** and point to your bot:
   - Base URL: `https://<your-webapp>.azurewebsites.net/`
   - Message endpoint: `/api/messages`
3. Configure OAuth using your App Registration (client id/secret, tenant id).
4. Map intents/actions (e.g., list spaces, switch space, list conversations, query tables).
5. Restrict access with Microsoft Entra groups aligned to your SAP/Datasphere/Databricks RBAC.
6. Test and add guardrails/content filters where needed.


## Walkthrough GIFs (placeholders)

1. **Add external web service skill**  
   ![GIF – Add skill](gifs/cps-01-add-skill.gif)

2. **Configure OAuth**  
   ![GIF – OAuth config](gifs/cps-02-oauth-config.gif)

3. **Map intents/actions**  
   ![GIF – Map actions](gifs/cps-03-map-actions.gif)

4. **Test the skill**  
   ![GIF – Test skill](gifs/cps-04-test.gif)


# Copilot Studio Skill — Databricks Genie (two patterns)
*How to wire Genie into Copilot Studio as an External Web Service with a Simple and an Advanced skill.*

This guide helps **makers/admins** connect your Genie web app to **Microsoft Copilot Studio** so copilots can call Genie inside flows, topics, or actions.

---

## TL;DR (Cheat-Sheet)
- **Pattern A (Simple)** → Input: `prompt` → Output: `answer`.  
- **Pattern B (Advanced)** → Inputs: `prompt` → Outputs: `elapsedMs`, `error`, `response`, `status`, `traceId`.
- In Copilot Studio: **Plugins → Add** → **External web service** → point to your web app → **OAuth (client credentials)** → map I/O → test.

---

## 1) Prerequisites
- A **deployed Genie web app** reachable at `https://<YOUR_WEBAPP>.azurewebsites.net/`.
- **OAuth (Microsoft Entra)** App Registration with:
  - `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`
  - (Recommended) **App role** like `Genie.Query` and an **Application ID URI** (e.g., `api://<YOUR_APP_ID>`).
- The web app exposes either:
  - **Clean JSON endpoints** for Simple/Advanced (recommended; examples below), **or**
  - A Bot Framework `/api/messages` endpoint (only if you’ve implemented a skill-compatible protocol).

> **Note**  
> For Copilot Studio **External web service**, a clean JSON API with OAuth 2.0 Client Credentials is the most straightforward.

---

## 2) Pick your pattern

| Pattern | Inputs | Outputs | When to use |
|---|---|---|---|
| **Simple Genie skill** | `prompt` | `answer` | Quick “ask Genie” step, no diagnostics needed |
| **Advanced Genie skill** | `prompt` | `elapsedMs`, `error`, `response`, `status`, `traceId` | Recommended for production; enables guardrails, observability, retries |

