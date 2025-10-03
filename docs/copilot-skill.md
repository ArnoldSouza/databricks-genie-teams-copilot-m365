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
