# Bridge Contract

The widget is generic. The host website makes it useful by providing a bridge object.

The bridge is where the host defines:

- what page context is visible to the model
- what actions are safe to expose
- any site-specific helpers that are more stable than raw DOM automation

## Required Method

### `getContext(allowUiAccess)`

Returns a plain JSON object describing the current page.

Minimum useful shape:

```js
{
  title: document.title,
  path: location.pathname,
  url: location.href
}
```

The `allowUiAccess` argument tells the host whether the widget is currently allowed to gather UI-derived details.

## Recommended Method

### `getVisibleTextSample()`

Returns a compact text sample of visible page content.

Example:

```js
getVisibleTextSample() {
  return document.body.innerText.slice(0, 4000);
}
```

## Optional Safe Actions

The host may expose any subset of these:

- `clickSelector(selector)`
- `setInputValue(selector, value)`
- `navigateStock(symbol)`
- `queryDb(sql, limit)`
- `exportQueryToCsv(sql, path)`
- `fetchDomHtml(offset, limit)`
- `renderAgentHtml(html)`
- `appendAgentHtml(html)`
- `webSearch(query, limit)`
- `fetchWebPage(url)`
- `fetchDbTables()`
- `fetchDbStatus()`

If a method is missing, the widget treats that action as unsupported.

## Example Bridge

```html
<script>
  window.MySiteAgentBridge = {
    getContext(allowUiAccess) {
      return {
        title: document.title,
        path: location.pathname,
        url: location.href,
        uiAccessAllowed: !!allowUiAccess
      };
    },
    getVisibleTextSample() {
      return document.body.innerText.slice(0, 4000);
    },
    clickSelector(selector) {
      const el = document.querySelector(selector);
      if (!el) throw new Error("selector not found");
      el.click();
      return { ok: true, selector };
    },
    setInputValue(selector, value) {
      const el = document.querySelector(selector);
      if (!el) throw new Error("selector not found");
      el.value = value == null ? "" : String(value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: true, selector, value: el.value };
    }
  };
</script>
```

## Design Guidance

The bridge should expose only actions the host considers safe.

Good bridge design usually means:

- keep actions narrow and explicit
- prefer stable helpers over brittle DOM assumptions
- avoid exposing write or navigation actions the host would not let a human user do casually
- expose business-specific helpers when they are safer than generic selectors

The bridge is the host-controlled capability boundary. That is what makes the widget portable across sites without making every site share the same unsafe automation surface.
