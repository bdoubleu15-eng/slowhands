# Cursor Agent Web Access

## Accessing the Web Interface
- Visit `https://cursor.com/agents`
- Sign in with your Cursor account
- Connect GitHub to enable codebase access
- Start a task in the web UI

## General Configuration
- **Secrets**: Dashboard → Cloud Agents → Secrets
- **Rules**: Dashboard Settings → Rules or add `.cursorrules` to the repo
- **Plan Mode**: Enable for complex tasks to require a plan before edits
- **Security**: Manage approval requirements under Agents settings

## Enterprise Browser Controls
- Dashboard → MCP Configuration → toggle browser features
- Configure origin allowlist for approved sites
- Review network/proxy settings if using corporate proxies (e.g., Zscaler)

## Browser Tools (Cursor Agent)
Agent can control a browser for UI testing, screenshots, console logs, and network
traffic. Capabilities include navigation, clicking, typing, scrolling, and
screenshot capture. Browser actions require approval by default and can be
allow‑listed or auto‑run in settings. For enterprise, browser access is governed
by MCP allowlist/denylist and origin allowlist.  
Source: [Cursor Browser docs](https://cursor.com/docs/agent/browser)

## Available Browser Capabilities
- Navigate / back / forward / refresh
- Click / double‑click / hover
- Type / fill forms
- Scroll
- Screenshots
- Console output
- Network traffic
Source: [Cursor Browser docs](https://cursor.com/docs/agent/browser)

## Refresh / Reconnect Steps
- Restart Cursor (closes/reopens MCP connections)
- Reopen the workspace
- Re‑launch the agent panel
- Verify browser tools are enabled in settings

## Notes
- Web access settings are managed in the Cursor web dashboard, not in this repo.
- Link your VCS in the web UI for agent access to GitHub repositories.
