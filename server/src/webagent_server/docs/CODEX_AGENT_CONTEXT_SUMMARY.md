# Codex Agent Context Summary

- Backend entry point for the in-app Codex agent is `web_ui.py`.
- Main Codex route is `/api/codex/chat`; status route is `/api/codex/status`.
- Frontend Codex drawer lives in `static/codex_extension.js`.
- Browser-side safe action bridge lives in `static/yahoo_app_agent.js`.

## DB conventions

- Primary price source of truth is typically `dbo.AlphaEOD`.
- `dbo.AlphaEOD` uses `Symbol` and `[Date]`.
- `dbo.MACD` uses `Symbol` and `[TradeDate]`.
- `dbo.RSI` uses `Symbol` and `[TradeDate]`.
- `dbo.ATR` and `dbo.EMA` are indicator tables and commonly use `Symbol` plus a trade-date column.
- Do not assume `YahooEOD` is authoritative if `AlphaEOD` is present.

## Agent behavior

- Allowed in-app action types are `clickSelector`, `setInputValue`, `navigateStock`, `queryDb`, `fetchDbTables`, `fetchDbStatus`.
- `exportQueryToCsv` is available for read-only SQL exports into the app `data` folder.
- `fetchDomHtml` is available when visible UI context is insufficient; do not request DOM/HTML by default.
- `fetchDomHtml` supports paged reads with `offset` and `limit`; use another `fetchDomHtml` action if a prior chunk is truncated.
- `renderAgentHtml` is available to write live HTML into the page's Agent Workspace section when the host exposes one.
- `appendAgentHtml` is available to add another HTML block below existing workspace content without a page refresh.
- `webSearch` and `fetchWebPage` are available for lightweight headless browsing when the task genuinely needs web research.
- If `jcodemunch` MCP is configured in the Codex CLI runtime, use it for repo/code exploration before brute-force file scanning.
- Do not use `jcodemunch` for live webpage DOM inspection; use `fetchDomHtml` for the current page.
- `queryDb` is read-only only. It must be a single read-only statement that starts with `SELECT` or `WITH`; CTEs such as `WITH x AS (...) SELECT ...` are allowed.
- `exportQueryToCsv` must also use a single read-only `SELECT`/`WITH` query and can only save under `data/`.
- Agent Workspace tables should stay paginated/sortable and avoid excessive row counts.
- SQL must be SQL Server compatible.
- If evidence is insufficient but a safe query can resolve it, continue with actions instead of stopping.
- If a material ambiguity cannot be resolved safely, ask a direct clarifying question instead of guessing.

## Completion rules

- Do not conclude a task until every requested source or deliverable has been covered.
- Do not infer `0` stale rows from a result set that omitted a requested source.
- Do not claim a file was saved unless the workflow actually saved it.
- If the user asked for a CSV export, prefer `exportQueryToCsv` with a path under `data/`.
- If visible UI summaries are insufficient, prefer `fetchDomHtml` before asking the user for selectors.
- When using `fetchDomHtml`, request only the chunk needed for the current task and continue paging only if necessary.
- If web research is needed, use `webSearch` first, then `fetchWebPage` for the most relevant result.
