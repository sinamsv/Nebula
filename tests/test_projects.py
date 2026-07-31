"""Unit and integration tests for Projects feature.

Exercises:
- ProjectStore filesystem helper (creation, sanitization, path traversal validation, deletion, collision overwriting).
- Projects API endpoints via TestClient (listing, creation, owner-only authorization, assets upload, chats isolation).
- AIHandler integration with project instructions and knowledge base injected into system prompt.

Run with: python3 tests/test_projects.py
"""
import os
import sys
import tempfile
import shutil
import unittest
from datetime import datetime

sys.path.insert(0, '.')

# --- Fake discord module (moderation.py imports discord.py) ---
import types
fake_discord = types.ModuleType('discord')
class _FakeGuild: pass
class _FakeForbidden(Exception): pass
fake_discord.Guild = _FakeGuild
fake_discord.Forbidden = _FakeForbidden
sys.modules['discord'] = fake_discord

# --- Fake tiktoken encoding ---
import tiktoken
class _FakeEncoding:
    def encode(self, text):
        return list(range(max(1, len(text) // 5)))
tiktoken.encoding_for_model = lambda model: _FakeEncoding()

os.environ['JWT_SECRET'] = 'test-jwt-secret-not-for-production'
os.environ['OAUTH_TOKEN_ENCRYPTION_KEY'] = 'iY129m5jLWjbNe1pSN2uO18rCVShyuF3M7pN5P4b6PQ='
os.environ['ADMIN_BOOTSTRAP_KEY'] = 'test-bootstrap-key'

from fastapi.testclient import TestClient
from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler
from ai.providers.base import BaseProvider, NormalizedResponse
from web_backend.app import create_app
from web_backend.project_store import (
    ProjectStore,
    ProjectValidationError,
    ProjectNotFoundError,
    ProjectPermissionError,
)


class SpyProvider(BaseProvider):
    def __init__(self, reply="Fake AI reply"):
        self.reply = reply
        self.last_system_prompt = None
        self.last_messages = None

    async def call(self, messages, tools, system_prompt, images=None, model_override=None):
        self.last_messages = messages
        self.last_system_prompt = system_prompt
        return NormalizedResponse(content=self.reply, tool_calls=[])

    async def call_stream(self, messages, tools, system_prompt, images=None, model_override=None):
        response = await self.call(messages, tools, system_prompt, images, model_override)
        if response.content:
            yield {"type": "content", "content": response.content}
        if response.tool_calls:
            yield {"type": "tool_calls", "tool_calls": response.tool_calls}

    def append_tool_round(self, messages, response, tool_results):
        return messages


class TestProjectStoreUnit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = ProjectStore(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_project_lifecycle_and_validation(self):
        # Create project
        owner = "alice"
        meta = self.store.create_project("Nebula CLI", "A cool AI companion CLI", owner)
        self.assertEqual(meta["name"], "Nebula CLI")
        self.assertEqual(meta["owner"], owner)
        project_id = meta["id"]

        # Retrieve metadata
        fetched = self.store.get_project_metadata(owner, project_id)
        self.assertEqual(fetched["id"], project_id)
        self.assertEqual(fetched["description"], "A cool AI companion CLI")

        # Reject empty name
        with self.assertRaises(ProjectValidationError):
            self.store.create_project("", "desc", owner)

        # Reject invalid UUID project_id
        with self.assertRaises(ProjectValidationError):
            self.store.get_project_metadata(owner, "not-a-uuid")

        # Reject path traversal project_id
        with self.assertRaises(ProjectValidationError):
            self.store.get_project_metadata(owner, "../etc")

        # Enforce owner-only (resolves to NotFound since bob's user dir doesn't contain alice's project)
        with self.assertRaises(ProjectNotFoundError):
            self.store.get_project_metadata("bob", project_id)

        # Update instruction
        self.store.update_instruction(owner, project_id, "Act as a Rust developer.")
        inst = self.store.read_instruction(owner, project_id)
        self.assertEqual(inst, "Act as a Rust developer.")

        # Save knowledge files and handle collision (overwrite)
        self.store.save_knowledge_file(owner, project_id, "readme.md", b"Hello Nebula")
        self.store.save_knowledge_file(owner, project_id, "readme.md", b"Hello Overwrite")

        files = self.store.list_knowledge_files(owner, project_id)
        self.assertIn("readme.md", files)

        contents = self.store.read_knowledge_files_contents(owner, project_id)
        self.assertEqual(contents["readme.md"], "Hello Overwrite")

        # Create, get, and list project-scoped chats
        chat = self.store.create_chat(owner, project_id, "Development Thread")
        chat_id = chat["chat_id"]
        self.assertEqual(chat["title"], "Development Thread")

        chats_list = self.store.list_chats(owner, project_id)
        self.assertEqual(len(chats_list), 1)
        self.assertEqual(chats_list[0]["chat_id"], chat_id)

        # Append messages and retrieve history
        self.store.append_chat_message(owner, project_id, chat_id, "user", "How to write a cargo command?")
        self.store.append_chat_message(owner, project_id, chat_id, "assistant", "Use cargo run.")

        chat_history = self.store.get_chat(owner, project_id, chat_id)
        messages = chat_history["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["content"], "Use cargo run.")

        # Delete project
        self.store.delete_project(owner, project_id)
        with self.assertRaises(ProjectNotFoundError):
            self.store.get_project_metadata(owner, project_id)


class TestProjectsIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_dir = tempfile.mkdtemp()
        os.environ['PROJECTS_DIR'] = self.temp_dir

        self.db = DatabaseManager(db_path=os.path.join(self.db_dir, 'test.db'))
        self.auth = AuthManager(self.db)
        self.memory = MemoryManager(self.db)
        self.coins = CoinManager(self.db)
        self.search = SearchTool()

        self.handler = AIHandler(self.db, self.auth, self.memory, self.coins, self.search)
        self.spy_provider = SpyProvider("I am a helpful assistant.")
        self.handler.provider = self.spy_provider

        # Seed default model config so AI turns are allowed
        self.db.save_model("google/gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", ["Member", "Trusted", "Researcher", "Admin"])

        self.app = create_app(self.db, self.auth, self.memory, self.coins, self.handler)
        self.client = TestClient(self.app)

        # Sign up alice
        r = self.client.post("/api/v1/auth/signup", json={
            "username": "alice", "password": "supersecret123",
            "display_name": "Alice", "bootstrap_key": "test-bootstrap-key",
        })
        self.alice_token = r.json()["access_token"]
        self.alice_headers = {"Authorization": f"Bearer {self.alice_token}"}

        # Sign up bob (approved Member via database manually)
        r = self.client.post("/api/v1/auth/signup", json={
            "username": "bob", "password": "supersecret123",
            "display_name": "Bob",
        })
        self.bob_id = r.json()["nebula_user_id"]
        self.db.set_user_approval(self.bob_id, True, approved_by=1)
        self.bob_token = r.json()["access_token"]
        self.bob_headers = {"Authorization": f"Bearer {self.bob_token}"}

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.db_dir)
        os.environ.pop('PROJECTS_DIR', None)

    def test_api_project_lifecycle_and_owner_isolation(self):
        # Create project as Alice
        r = self.client.post("/api/v1/project/create", json={
            "name": "Nebula CLI", "description": "Rust CLI companion"
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 201)
        project_id = r.json()["id"]
        self.assertEqual(r.json()["name"], "Nebula CLI")

        # List projects as Alice
        r = self.client.get("/api/v1/projects/alice", headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["projects"]), 1)
        self.assertEqual(r.json()["projects"][0]["id"], project_id)

        # POST dual-verb variant
        r = self.client.post("/api/v1/projects/alice", headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["projects"]), 1)

        # Bob listing Alice's projects is rejected by path-param username constraint
        r = self.client.get("/api/v1/projects/alice", headers=self.bob_headers)
        self.assertEqual(r.status_code, 403)

        # Bob lists his own empty list
        r = self.client.get("/api/v1/projects/bob", headers=self.bob_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["projects"]), 0)

        # Bob accessing Alice's project must return 404 (prevent information leak)
        r = self.client.get(f"/api/v1/project/{project_id}/chats", headers=self.bob_headers)
        self.assertEqual(r.status_code, 404)

        # Alice updates assets (instruction and/or knowledge file)
        r = self.client.post(
            f"/api/v1/project/{project_id}/upload",
            data={"instruction": "Always respond in UPPERCASE."},
            files={"file": ("context.txt", b"Nebula uses Rust.", "text/plain")},
            headers=self.alice_headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("updated_at", r.json())

        # Alice creates a project-scoped chat
        r = self.client.post(
            f"/api/v1/project/{project_id}/chats",
            json={"title": "CLI Chat"},
            headers=self.alice_headers,
        )
        self.assertEqual(r.status_code, 201)
        chat_id = r.json()["chat_id"]

        # Alice lists chats
        r = self.client.get(f"/api/v1/project/{project_id}/chats", headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["chats"]), 1)
        self.assertEqual(r.json()["chats"][0]["chat_id"], chat_id)

        # Alice sends a message, which integrates with the AI Provider pipeline and context injection
        r = self.client.post(
            f"/api/v1/project/{project_id}/chat/{chat_id}",
            json={"input": "What language does Nebula use?"},
            headers=self.alice_headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["reply_text"], "I am a helpful assistant.")
        self.assertIn("usage", r.json())

        # Verify that instructions and knowledge were correctly injected into system prompt
        self.assertIn("Always respond in UPPERCASE.", self.spy_provider.last_system_prompt)
        self.assertIn("context.txt", self.spy_provider.last_system_prompt)
        self.assertIn("Nebula uses Rust.", self.spy_provider.last_system_prompt)

        # Verify history is persisted in project chat JSON
        r = self.client.get(f"/api/v1/project/{project_id}/chat/{chat_id}", headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        messages = r.json()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

        # Verify project chat messages are completely isolated from SQLite history
        sqlite_history = self.db.get_conversation_history(1)
        sqlite_contents = [m["content"] for m in sqlite_history]
        self.assertNotIn("What language does Nebula use?", sqlite_contents)

        # Delete project
        r = self.client.delete(f"/api/v1/project/delete/{project_id}", headers=self.alice_headers)
        self.assertEqual(r.status_code, 204)

        # Re-verify project folder is gone
        r = self.client.get(f"/api/v1/project/{project_id}/chats", headers=self.alice_headers)
        self.assertEqual(r.status_code, 404)

    def test_backend_additions_stage_1(self):
        # Create a new project as Alice
        r = self.client.post("/api/v1/project/create", json={
            "name": "Additions Project", "description": "Backend stage 1 test"
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 201)
        project_id = r.json()["id"]
        self.assertEqual(r.json()["pinned"], False) # defaults to False

        # Pin project using PATCH
        r = self.client.patch(f"/api/v1/project/{project_id}", json={
            "pinned": True
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["pinned"], True)

        # Unpin project using PATCH
        r = self.client.patch(f"/api/v1/project/{project_id}", json={
            "pinned": False
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["pinned"], False)

        # Rename and update description using PATCH
        r = self.client.patch(f"/api/v1/project/{project_id}", json={
            "name": "New Name", "description": "New Desc", "pinned": True
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "New Name")
        self.assertEqual(r.json()["description"], "New Desc")
        self.assertEqual(r.json()["pinned"], True)

        # Empty name validation check
        r = self.client.patch(f"/api/v1/project/{project_id}", json={
            "name": "   "
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 400) # Empty/whitespace rejected

        # Empty PATCH body check (all fields None)
        r = self.client.patch(f"/api/v1/project/{project_id}", json={}, headers=self.alice_headers)
        self.assertEqual(r.status_code, 400)

        # Bob accessing Alice's project PATCH is rejected/404
        r = self.client.patch(f"/api/v1/project/{project_id}", json={"name": "Bob Rename"}, headers=self.bob_headers)
        self.assertEqual(r.status_code, 404)

        # File size limit checks
        r = self.client.post("/api/v1/project/create", json={
            "name": "Bob Project", "description": "Bob Stage 1 tests"
        }, headers=self.bob_headers)
        bob_project_id = r.json()["id"]

        # Let's temporarily lower Bob's role's max_upload_mb to 0 for a test case so a tiny file is rejected!
        r = self.client.put("/api/v1/admin/roles/settings", json={
            "role": "Member",
            "allowed_models": [],
            "allowed_tools": ["search"],
            "daily_limit": 50.0,
            "weekly_limit": 200.0,
            "max_upload_mb": 0 # Set to 0MB upload limit to test rejection!
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["max_upload_mb"], 0)

        # Bob tries to upload a small file, which should fail because 22 bytes > 0 bytes limit!
        r = self.client.post(
            f"/api/v1/project/{bob_project_id}/upload",
            files={"file": ("readme.txt", b"Hello, this is a test.")},
            headers=self.bob_headers,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("File size exceeds", r.json()["detail"])

        # Change Bob's (Member) limit to 1MB and retry
        r = self.client.put("/api/v1/admin/roles/settings", json={
            "role": "Member",
            "allowed_models": [],
            "allowed_tools": ["search"],
            "daily_limit": 50.0,
            "weekly_limit": 200.0,
            "max_upload_mb": 1
        }, headers=self.alice_headers)
        self.assertEqual(r.status_code, 200)

        # Bob uploads the small file, should succeed
        r = self.client.post(
            f"/api/v1/project/{bob_project_id}/upload",
            files={"file": ("readme.txt", b"Hello, this is a test.")},
            headers=self.bob_headers,
        )
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
