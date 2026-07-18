"""Integration test for web_backend/, using FastAPI's TestClient, a
fake BaseProvider (same FakeProvider pattern as the project's own
test_handler_integration.py), and a fake tiktoken encoding to avoid
network access. Exercises: signup -> JWT -> create chat -> send
message -> get history -> per-chat token isolation from a simulated
legacy Discord message -> admin review flow -> sync code generation.

Run with: python3 tests/test_web_backend_integration.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, '.')

# --- Fake discord module (moderation.py imports discord.py) ---
import types
fake_discord = types.ModuleType('discord')
class _FakeGuild: pass
class _FakeForbidden(Exception): pass
fake_discord.Guild = _FakeGuild
fake_discord.Forbidden = _FakeForbidden
sys.modules['discord'] = fake_discord

# --- Fake tiktoken encoding (avoid network fetch in sandboxed envs) ---
import tiktoken
class _FakeEncoding:
    def encode(self, text):
        return list(range(len(text)))
tiktoken.encoding_for_model = lambda model: _FakeEncoding()

os.environ['JWT_SECRET'] = 'test-jwt-secret-not-for-production'
os.environ['OAUTH_TOKEN_ENCRYPTION_KEY'] = 'iY129m5jLWjbNe1pSN2uO18rCVShyuF3M7pN5P4b6PQ='
os.environ['ADMIN_BOOTSTRAP_KEY'] = 'test-bootstrap-key'

for var in ['AI_PROVIDER', 'AI_API_KEY', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'AI_MODEL']:
    os.environ.pop(var, None)

from fastapi.testclient import TestClient

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler
from ai.providers.base import BaseProvider, NormalizedResponse, NormalizedToolCall
from web_backend.app import create_app


class FakeProvider(BaseProvider):
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0
        self.last_images = None

    async def call(self, messages, tools, system_prompt, images=None):
        self.last_images = images
        response = self._responses[self.call_count]
        self.call_count += 1
        return response

    def append_tool_round(self, messages, response, tool_results):
        new_messages = list(messages)
        new_messages.append({"role": "assistant", "content": "[fake tool round]"})
        for tc, result in zip(response.tool_calls, tool_results):
            new_messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return new_messages


def make_test_client(fake_responses):
    tmpdir = tempfile.mkdtemp()
    db = DatabaseManager(db_path=os.path.join(tmpdir, 'test.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search = SearchTool()

    handler = AIHandler(db, auth, memory, coins, search)
    assert handler.provider is None, "expected no real provider configured in test env"
    handler.provider = FakeProvider(fake_responses)

    app = create_app(db, auth, memory, coins, handler)
    client = TestClient(app)
    return client, db, handler


def test_full_signup_chat_flow():
    client, db, handler = make_test_client([
        NormalizedResponse(content="Hi Sina! How can I help?", tool_calls=[]),
    ])

    # bootstrap status should show available before anyone signs up
    r = client.get("/api/v1/auth/bootstrap-status")
    assert r.status_code == 200
    assert r.json()["bootstrap_available"] is True

    # signup as the first (bootstrap) admin
    r = client.post("/api/v1/auth/signup", json={
        "username": "sina", "password": "supersecret123",
        "display_name": "Sina", "bootstrap_key": "test-bootstrap-key",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["became_admin"] is True
    assert body["is_approved"] is True
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # bootstrap should now show unavailable
    r = client.get("/api/v1/auth/bootstrap-status")
    assert r.json()["bootstrap_available"] is False

    # create a chat
    r = client.post("/api/v1/chat", json={"title": "My Chat"}, headers=headers)
    assert r.status_code == 201, r.text
    chat_id = r.json()["chat_id"]
    assert r.json()["title"] == "My Chat"

    # send a message
    r = client.post(f"/api/v1/chat/{chat_id}/messages", json={"input": "hello nebula"}, headers=headers)
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["reply_text"] == "Hi Sina! How can I help?"

    # get history
    r = client.get(f"/api/v1/chat/{chat_id}", headers=headers)
    assert r.status_code == 200
    messages = r.json()["messages"]
    assert len(messages) == 2  # user + assistant
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi Sina! How can I help?"

    # list chats
    r = client.get("/api/v1/chat", headers=headers)
    assert len(r.json()["chats"]) == 1

    print("PASS: test_full_signup_chat_flow")


def test_chat_memory_isolated_from_discord_legacy_history():
    """Confirms the core promise of the schema migration: a Discord
    message (chat_id=None) and a web chat message (chat_id=<int>) for
    the SAME account never appear in each other's history."""
    client, db, handler = make_test_client([
        NormalizedResponse(content="Web reply", tool_calls=[]),
    ])

    r = client.post("/api/v1/auth/signup", json={
        "username": "sina2", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    nebula_user_id = r.json()["nebula_user_id"]
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # simulate an existing Discord message for this account (chat_id=None)
    db.add_message(nebula_user_id, "user", "hello from discord", "discord", token_count=5)

    r = client.post("/api/v1/chat", json={}, headers=headers)
    chat_id = r.json()["chat_id"]

    r = client.post(f"/api/v1/chat/{chat_id}/messages", json={"input": "hello from web"}, headers=headers)
    assert r.status_code == 200

    # web chat history should NOT contain the discord message
    r = client.get(f"/api/v1/chat/{chat_id}", headers=headers)
    contents = [m["content"] for m in r.json()["messages"]]
    assert "hello from discord" not in contents
    assert any("hello from web" in c for c in contents)

    # legacy (Discord) history should be untouched by the web message
    legacy_history = db.get_conversation_history(nebula_user_id, chat_id=None)
    legacy_contents = [m["content"] for m in legacy_history]
    assert "hello from discord" in legacy_contents
    assert not any("hello from web" in c for c in legacy_contents)

    print("PASS: test_chat_memory_isolated_from_discord_legacy_history")


def test_admin_review_flow():
    client, db, handler = make_test_client([])

    # bootstrap admin
    r = client.post("/api/v1/auth/signup", json={
        "username": "admin1", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    admin_token = r.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # regular pending user
    r = client.post("/api/v1/auth/signup", json={"username": "pendinguser", "password": "supersecret123"})
    assert r.json()["is_approved"] is False
    pending_user_id = r.json()["nebula_user_id"]
    pending_token = r.json()["access_token"]
    pending_headers = {"Authorization": f"Bearer {pending_token}"}

    # pending user should be blocked from chat (not approved)
    r = client.post("/api/v1/chat", json={}, headers=pending_headers)
    assert r.status_code == 403

    # pending user cannot see admin routes
    r = client.get("/api/v1/admin/users/pending", headers=pending_headers)
    assert r.status_code == 403

    # admin lists pending users
    r = client.get("/api/v1/admin/users/pending", headers=admin_headers)
    assert r.status_code == 200
    usernames = [p["username"] for p in r.json()["pending"]]
    assert "pendinguser" in usernames

    # admin approves
    r = client.post(f"/api/v1/admin/users/{pending_user_id}/review", json={"status": "approved"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is True

    # now pending user (now approved) can create a chat
    r = client.post("/api/v1/chat", json={}, headers=pending_headers)
    assert r.status_code == 201

    print("PASS: test_admin_review_flow")


def test_coins_self_only():
    client, db, handler = make_test_client([])

    r = client.post("/api/v1/auth/signup", json={
        "username": "coinuser", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/users/me/coins", headers=headers)
    assert r.status_code == 200
    assert r.json()["balance"] == 10

    # admin can modify another user's coins via the id-based endpoint
    user_id = r.json.__self__ if False else None  # noop, keep structure simple
    nebula_user_id = client.post("/api/v1/auth/signup", json={
        "username": "target_user", "password": "supersecret123",
    }).json()["nebula_user_id"]

    r = client.post(f"/api/v1/users/{nebula_user_id}/coins", json={"amount": 5, "mode": "add"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["new_balance"] == 15

    print("PASS: test_coins_self_only")


def test_sync_code_generation():
    client, db, handler = make_test_client([])

    r = client.post("/api/v1/auth/signup", json={
        "username": "syncuser", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/platforms")
    assert r.status_code == 200
    platform_ids = [p["id"] for p in r.json()["platforms"]]
    assert "discord" in platform_ids
    assert "telegram" in platform_ids

    r = client.post("/api/v1/sync/telegram", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["code"]) == 6
    assert "verify username:syncuser" in body["verify_command_hint"]

    # invalid platform rejected
    r = client.post("/api/v1/sync/notaplatform", headers=headers)
    assert r.status_code == 400

    print("PASS: test_sync_code_generation")


def test_image_message_reaches_provider():
    """Confirms the multipart image endpoint actually threads an
    ImageAttachment through to provider.call() -- the core "real
    multimodal forwarding" promise for web."""
    client, db, handler = make_test_client([
        NormalizedResponse(content="I see a red square.", tool_calls=[]),
    ])

    r = client.post("/api/v1/auth/signup", json={
        "username": "imguser", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/chat", json={}, headers=headers)
    chat_id = r.json()["chat_id"]

    fake_image_bytes = b"\xff\xd8\xff\xe0" + b"0" * 100  # fake jpeg-ish bytes
    r = client.post(
        f"/api/v1/chat/{chat_id}/messages/image",
        params={"text": "what is this?"},
        files={"image": ("test.jpg", fake_image_bytes, "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply_text"] == "I see a red square."

    assert handler.provider.last_images is not None
    assert len(handler.provider.last_images) == 1
    assert handler.provider.last_images[0].mime_type == "image/jpeg"
    assert handler.provider.last_images[0].data == fake_image_bytes

    print("PASS: test_image_message_reaches_provider")


def test_search_toggle_removes_search_tool():
    """Confirms {"tools": {"search": false}} actually removes the
    search tool from what's offered to the model."""
    captured_tools = {}

    class ToolCapturingProvider(FakeProvider):
        async def call(self, messages, tools, system_prompt, images=None):
            captured_tools['tools'] = tools
            return await super().call(messages, tools, system_prompt, images=images)

    tmpdir = tempfile.mkdtemp()
    db = DatabaseManager(db_path=os.path.join(tmpdir, 'test.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search = SearchTool()
    handler = AIHandler(db, auth, memory, coins, search)
    handler.provider = ToolCapturingProvider([NormalizedResponse(content="ok", tool_calls=[])])

    app = create_app(db, auth, memory, coins, handler)
    client = TestClient(app)

    r = client.post("/api/v1/auth/signup", json={
        "username": "tooluser", "password": "supersecret123", "bootstrap_key": "test-bootstrap-key",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = client.post("/api/v1/chat", json={}, headers=headers).json()["chat_id"]

    r = client.post(
        f"/api/v1/chat/{chat_id}/messages",
        json={"input": "hi", "tools": {"search": False}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert captured_tools['tools'] == [], "search tool should be excluded when tools.search=false"

    print("PASS: test_search_toggle_removes_search_tool")


ALL_TESTS = [
    test_full_signup_chat_flow,
    test_chat_memory_isolated_from_discord_legacy_history,
    test_admin_review_flow,
    test_coins_self_only,
    test_sync_code_generation,
    test_image_message_reaches_provider,
    test_search_toggle_removes_search_tool,
]

if __name__ == "__main__":
    failures = []
    for test_fn in ALL_TESTS:
        try:
            test_fn()
        except Exception as e:
            import traceback
            failures.append((test_fn.__name__, e))
            print(f"FAIL: {test_fn.__name__} — {type(e).__name__}: {e}")
            traceback.print_exc()

    print()
    print(f"{len(ALL_TESTS) - len(failures)}/{len(ALL_TESTS)} passed")
    if failures:
        sys.exit(1)
