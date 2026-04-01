# Northstar Commerce Demo Host

This is a static commerce demo page used to test the WebAgent widget against a realistic storefront host.

## What the page supports

- A visible product-card catalog that can be filtered through `#inventory-search` and `#location-filter`
- Buttons the agent can safely click:
  - `#apply-filters-btn`
  - `#refresh-inventory-btn`
  - `#open-maintenance-btn`
- Structured read tools exposed by the host bridge:
  - `getPageState()` for current filters, counts, and visible categories
  - `getVisibleProducts()` for the currently rendered storefront cards
  - `getDomTree(selector)` for a compact live semantic tree of the page or a scoped container
- An Agent Workspace target at `#agent-workspace`
- A buying-guide modal that can be opened and closed

## What to prefer

- Use website actions for host-specific UI work
- Prefer `getVisibleProducts()` and `getPageState()` over raw `fetchDomHtml` when you need to verify what is currently on the storefront
- Use `getDomTree("#inventory-body")` or `getDomTree("#agent-workspace")` when you need a compact structural view of the page
- Use `renderAgentHtml` when you want to present product comparisons inside the workspace
- Read the attached `capabilities.json` and `api-client.js` files before making assumptions about supported selectors or demo APIs

## Notes

- The product cards are static demo data spanning audio gear, laptops, monitors, tablets, keyboards, and accessories
- The "API" is illustrative and documented through the attached class file
- This host is meant for safe local testing and comparison flows, not real transactions
