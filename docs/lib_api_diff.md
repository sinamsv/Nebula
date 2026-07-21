# web_frontend/lib/api.ts -- one required change

`sendMessage()`'s default parameter still uses the old boolean shape
(`{ search: true }`), which no longer type-checks once
`ToolToggles.search` becomes `SearchMode` (see types_api_diff.md).
Everything else in this file is unaffected -- `tools` is just passed
straight through in the request body either way.

## Before:
```ts
export function sendMessage(
  token: string,
  chatId: number,
  input: string,
  tools: ToolToggles = { search: true }
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(`/chat/${chatId}/messages`, {
    method: "POST",
    token,
    json: { input, tools },
  });
}
```

## After:
```ts
export function sendMessage(
  token: string,
  chatId: number,
  input: string,
  tools: ToolToggles = { search: "smart" }
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(`/chat/${chatId}/messages`, {
    method: "POST",
    token,
    json: { input, tools },
  });
}
```

Nothing else in api.ts needs to change -- this function already just
forwards `tools` as-is in the JSON body, and the backend's Pydantic
schema (ToolToggles) is what actually validates the "on"/"off"/"smart"
values.
