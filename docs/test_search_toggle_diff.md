# tests/test_web_backend_integration.py -- required change

Only ONE spot needs updating: `test_search_toggle_removes_search_tool()`
sends `{"tools": {"search": False}}` (a bool). With the new 3-state
schema, `False` is no longer a valid value for `ToolToggles.search` and
Pydantic will now reject it with a 422 instead of the intended 200.

## Before:
```python
    r = client.post(
        f"/api/v1/chat/{chat_id}/messages",
        json={"input": "hi", "tools": {"search": False}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert captured_tools['tools'] == [], "search tool should be excluded when tools.search=false"
```

## After:
```python
    r = client.post(
        f"/api/v1/chat/{chat_id}/messages",
        json={"input": "hi", "tools": {"search": "off"}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert captured_tools['tools'] == [], "search tool should be excluded when tools.search='off'"
```

## New test to add alongside it (recommended, not required)

Confirms "on" mode actually injects the extra system-prompt instruction,
and "smart" does NOT:

```python
def test_search_on_injects_extra_instruction():
    """Confirms search_mode='on' appends the extra system-prompt nudge
    for that turn, and that 'smart' (the default) does NOT -- keeping
    smart's behavior byte-for-byte identical to the old
    enable_search=True default."""
    captured_system_prompts = []

    class PromptCapturingProvider(FakeProvider):
        async def call(self, messages, tools, system_prompt, images=None):
            captured_system_prompts.append(system_prompt)
            return await super().call(messages, tools, system_prompt, images=images)

    tmpdir = tempfile.mkdtemp()
    db = DatabaseManager(db_path=os.path.join(tmpdir, 'test.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search = SearchTool()
    handler = AIHandler(db, auth, memory, coins, search)
    handler.provider = PromptCapturingProvider([
        NormalizedResponse(content="ok smart", tool_calls=[]),
        NormalizedResponse(content="ok on", tool_calls=[]),
    ])

    app = create_app(db, auth, memory, coins, handler)
    client = TestClient(app)

    r = client.post("/api/v1/auth/signup", json={
        "username": "searchmodeuser", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = client.post("/api/v1/chat", json={}, headers=headers).json()["chat_id"]

    # smart (default) -- no extra instruction
    r = client.post(
        f"/api/v1/chat/{chat_id}/messages",
        json={"input": "hi", "tools": {"search": "smart"}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert "Search Mode: ON" not in captured_system_prompts[0]

    # on -- extra instruction appended
    r = client.post(
        f"/api/v1/chat/{chat_id}/messages",
        json={"input": "what's the weather", "tools": {"search": "on"}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert "Search Mode: ON" in captured_system_prompts[1]

    print("PASS: test_search_on_injects_extra_instruction")
```

Also add `test_search_on_injects_extra_instruction` to the `ALL_TESTS`
list at the bottom of the file.
