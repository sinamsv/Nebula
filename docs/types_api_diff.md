# web_frontend/types/api.ts -- changes

## 1. Add a new exported type (put it right above `ToolToggles`)

```ts
/** Mirrors the backend's ToolToggles.search Literal type
 * (web_backend/schemas/chat.py) -- "off" never offers the search
 * tool, "smart" (default) lets the model decide for itself, "on"
 * biases the model toward actually searching when the message
 * plausibly needs it (see ai/handler.py's _SEARCH_ON_INSTRUCTION). */
export type SearchMode = "on" | "off" | "smart";
```

## 2. Replace the existing `ToolToggles` interface

Before:
```ts
export interface ToolToggles {
  search: boolean;
}
```

After:
```ts
export interface ToolToggles {
  search: SearchMode;
}
```

Nothing else in this file needs to change -- `SendMessageRequest`,
`SendMessageResponse`, etc. all reference `ToolToggles` structurally
and pick up the new type automatically.
