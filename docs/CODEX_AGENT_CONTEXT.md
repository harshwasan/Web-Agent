# Codex Agent Context

This document is intended to be safe, compact background context for the in-app Codex agent.

## Current architecture

The embedded agent runs through `web_ui.py` and is exposed to the browser through `/api/codex/chat`.

Important files:

- `web_ui.py`: backend routes, Codex/Claude request helpers, DB helper, and app APIs
- `static/codex_extension.js`: Codex drawer UI, action approval flow, auto-run loop, stop button, and chat rendering
- `static/yahoo_app_agent.js`: browser action bridge and UI context collector
- `sql_io.py`: SQL Server helpers for EOD and indicator data
- `yf_runner.py`: batch pipeline orchestration for catchup and rebuild flows

## Agent flow

1. Browser sends messages and compact app context to `/api/codex/chat`.
2. Backend compacts history and injects stable project context.
3. Codex returns strict JSON with `message` and `actions`.
4. Frontend either asks approval or auto-runs the actions.
5. Action results are sent back as follow-up context until Codex returns a final no-action answer.

The backend now also runs a verifier pass on no-action answers. That verifier should catch:

- false completion
- missing deliverables
- contradictions with earlier evidence
- unsupported file-save claims
- conclusions that ignore one of the requested sources

If the Codex CLI has MCP servers configured in `~/.codex/config.toml`, the embedded agent can use them during reasoning. In this setup, `jcodemunch` is the preferred MCP for fast codebase exploration.

HTML/DOM is not injected into every prompt by default. If visible UI summaries are not enough, the agent should use `fetchDomHtml` on demand.
`fetchDomHtml` supports paged reads via `offset` and `limit`; the agent should fetch only the chunk it needs and continue paging only when the returned chunk is truncated.
If the host page exposes an `Agent Workspace`, the agent can update it live with `renderAgentHtml` without refreshing the page.
If the agent needs to keep existing workspace content and add more below it, it should use `appendAgentHtml`.
When reporting DOM inspection results to the user, summarize the relevant state (e.g. runner status, button states) in plain language; do not paste raw HTML or long DOM chunks unless the user explicitly asks for details.
After the UI starts a background command (Run or a quick action), the runner status pill (#prog) switches to "running..." and the active jobs list is refreshed; to confirm a job started, check the pill text or open "Active Jobs" (or trigger Refresh Jobs) and inspect the jobs list in the DOM.

## DB freshness conventions

When users ask whether the DB is current through the latest completed trading day, use the actual source-of-truth table instead of guessing.

Known conventions in this project:

- `dbo.AlphaEOD` is the usual EOD source of truth
- `dbo.AlphaEOD` date column is `[Date]`
- `dbo.MACD` date column is `[TradeDate]`
- `dbo.RSI` date column is `[TradeDate]`
- `dbo.ATR` and `dbo.EMA` are indicator tables and should be checked explicitly rather than assumed

Do not assume:

- `dbo.YahooEOD` is authoritative
- every table uses the same date column
- a missing branch in a UNION means zero stale rows

## Query rules

- Only single-statement read-only queries that start with `SELECT` or `WITH` are allowed through the DB helper. CTE-based `WITH ... SELECT ...` queries are allowed.
- `exportQueryToCsv` uses the same read-only SQL rules and writes only inside the app `data` folder.
- `webSearch` performs lightweight web search.
- `fetchWebPage` fetches and summarizes a specific web page over HTTP.
- Queries must be SQL Server compatible.
- Prefer square-bracket quoting for columns like `[Date]`.
- Prefer `TOP (1) ... ORDER BY ... DESC` over risky or slow patterns when finding the latest date.
- If a user asks for full stale symbol lists, the final result must cover every requested source, not a sample.

## UI/action rules

- Allowed browser actions are limited to safe selectors, input changes, symbol navigation, and DB helper calls.
- Write-capable DB export is limited to `exportQueryToCsv`, which saves CSV files under `data/`.
- DOM inspection is available through `fetchDomHtml` on demand.
- `jcodemunch` is for local repository/code understanding, not for live webpage DOM inspection.
- Live in-page display is available through `renderAgentHtml`, which writes into the Agent Workspace section when the host exposes one.
- Additional live blocks can be added with `appendAgentHtml` without clearing existing workspace content.
- For Agent Workspace tables, prefer paginated/sortable markup and keep row counts reasonable.
- Headless browsing is available through `webSearch` and `fetchWebPage` and should be used only when the task actually requires external research.
- UI access can be blocked from the Codex drawer; when blocked, no UI actions should run.
- Auto Run means actions execute immediately without pending approval cards.

## Practical completion checks

Before concluding, verify:

- Did the answer cover all requested tables or sources?
- Did it answer the user question directly instead of describing process state?
- Did it mention when results are partial or truncated?
- Did it avoid claiming a file export if no file-writing action exists?
- If ambiguity remained, did it ask the user instead of guessing?
