# Using the Bot in Microsoft Teams
*Databricks Genie – M365 Agents*

This guide shows **how end-users, testers, and admins can install and use the bot inside Microsoft Teams**—from first sign-in to asking questions and sharing answers with your team.

---

## TL;DR (Quick Cheat-Sheet)
- **Install**: Upload the ZIP (`ms_teams/app_package/dbx-genie-m365-app.zip`) or install from your org catalog.
- **Open**: In Teams, search for the app name → **Open** → **Pin** for quick access.
- **Ask**: Type a plain-English question (e.g., *“Show me the list of tables you have”*).
- **Stuck?** Type `help` or see **Troubleshooting** below.

---

## 1) What you need (Prerequisites)
- You can **install custom apps** (sideload) OR your admin has **published** the app to the **Org catalog**.
- Your account has the **necessary data permissions** (e.g., access to the target Databricks/Unity Catalog objects used by Genie).

> **Note**  
> If you see *“Access denied / not authorized”*, you likely need access to the underlying data or workspace. See **Troubleshooting**.

---

## 2) Install options (Admins & Testers)

### Option A — Sideload for testing (developer tenants)
1. In Teams (desktop or web), go to **Apps** → **Manage your apps**.
2. Click **Upload an app** → **Upload a custom app**.
3. Select `ms_teams/app_package/dbx-genie-m365-app.zip`.
4. Follow the prompts to install.

### Option B — Publish to the organizational catalog
1. Submit the ZIP to your **Teams app catalog** following your tenant’s process.
2. End users will find it in **Apps** → **Built for your org**.

### Option C — Quick preview via Azure Bot
- In **Azure Portal** → your **Bot resource** → **Channels** → **Open in Teams**.

---

## 3) Use in a 1:1 chat (Personal scope)
Use the bot like a chat assistant:

**Examples**
- “List the top 10 customers by revenue in 2024.”
- “Create a quick summary of monthly sales growth vs last year.”
- “Which SKUs had negative margins last quarter? Show a short table.”
- “Explain the variance in OPEX for Q2 in simple terms.”

**Bot responses may include**
- A concise **answer** (text).
- A **table snippet** or **bulleted highlights**.
- A **link to open in Genie** (to explore the full result).
- A short **“how this was computed”** note or references (when available).

> **Pro-tip**  
> Keep prompts **specific**. Add filters/timeframes, e.g., “by region”, “top 5”, “from Jan–Jun 2025”.

---

## 4) Use in a Team/Channel (Collaboration)
1. Add the app to your **Team** (administrator/member with permissions).
2. In a channel, **@mention the bot** and ask your question:
   - `@Genie show inventory turns for the Pará site in 2024`
3. The bot replies in-thread so your team can discuss.

**Good patterns in channels**
- Ask a **short question** and follow up with replies for iteration.
- When you get a good result, **react** and **summarize** the decision or next steps.

## 5) Troubleshooting

| Symptom | Likely cause | What to try |
|---|---|---|
| “Access denied” / “Not authorized” | You don’t have access to required data/workspace | Request access to the Databricks objects/Unity Catalog; share error details with your admin |
| Empty or vague answers | Prompt too broad | Add timeframe, fields, filters, and desired output shape (table vs summary) |

---

## 6) Privacy & security notes
- The bot uses **Microsoft Entra** and honors your **RBAC** and **data permissions**.
- Questions and responses may be logged for **auditing, support, and product improvement** (per your org policy).
- Never paste secrets or personal data into prompts.

---

## 7) Uninstall / Reinstall
- **Personal**: In **Apps** → **Manage your apps** → find the app → **More** → **Uninstall**.  
- **Team**: In the Team’s **Manage apps**, remove the app (requires proper permissions).  
- Reinstall from **Org catalog** or **Upload a custom app** as needed.

---

## 8) GIFs (placeholders)

1. **Sideload app (developer flow)**  
   ![GIF – Sideload](gifs/teams-01-sideload.gif)

2. **Organization catalog publish**  
   ![GIF – Org catalog](gifs/teams-02-org-catalog.gif)

3. **Preview via Azure Bot channels**  
   ![GIF – Open in Teams](gifs/teams-03-open-in-teams.gif)

4. **Developer portal preview**  
   ![GIF – Dev portal preview](gifs/teams-04-dev-portal.gif)

