"""Integration test for ai/handler.py's handle_turn() tool-calling loop,
using a fake BaseProvider implementation (not a real SDK mock -- that's
what tests/test_providers.py already covers per-provider). This test
exercises the actual MAX_TOOL_ROUNDS loop in handle_turn() itself: does
it correctly call provider.call() -> execute tools -> provider.
append_tool_round() -> repeat, and correctly store only the final
synthesized response to memory (the exact bug this loop was originally
written to fix, per ai/handler.py's own comments)?

Run with: python3 tests/test_handler_integration.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, '.')

import types
fake_discord = types.ModuleType('discord')
class _FakeGuild: pass
class _FakeForbidden(Exception): pass
fake_discord.Guild = _FakeGuild
fake_discord.Forbidden = _FakeForbidden
sys.modules['discord'] = fake_discord

import tiktoken
class _FakeEncoding:
    def encode(self, text):
        return list(range(len(text)))
tiktoken.encoding_for_model = lambda model: _FakeEncoding()

from core.database import DatabaseManager
from core.auth import AuthManager
from core.memory import MemoryManager
from core.coins import CoinManager
from tools.search import SearchTool
from ai.handler import AIHandler
from ai.providers.base import BaseProvider, NormalizedResponse, NormalizedToolCall


class FakeProvider(BaseProvider):
    """Scripted provider: returns a pre-set sequence of NormalizedResponse
    objects, one per call() invocation, so the test controls exactly how
    many tool-calling rounds happen."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0
        self.append_tool_round_calls = []

    async def call(self, messages, tools, system_prompt, images=None):
        response = self._responses[self.call_count]
        self.call_count += 1
        return response

    def append_tool_round(self, messages, response, tool_results):
        self.append_tool_round_calls.append((list(messages), response, list(tool_results)))
        new_messages = list(messages)
        new_messages.append({"role": "assistant", "content": f"[fake tool_calls round {self.call_count}]"})
        for tc, result in zip(response.tool_calls, tool_results):
            new_messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return new_messages


def make_handler_with_fake_provider(responses):
    tmpdir = tempfile.mkdtemp()
    db = DatabaseManager(db_path=os.path.join(tmpdir, 'test.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search = SearchTool()

    for var in ['AI_PROVIDER', 'AI_API_KEY', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'AI_MODEL']:
        os.environ.pop(var, None)

    handler = AIHandler(db, auth, memory, coins, search)
    assert handler.provider is None, "expected no real provider configured in this test env"
    handler.provider = FakeProvider(responses)

    return handler, db, auth


def setup_approved_user(db, auth):
    result = auth.signup(
        username="testuser", password="testpassword123", display_name="Test User",
        platform="discord", platform_user_id="12345",
    )
    db.set_user_approval(result['nebula_user_id'], True, approved_by=result['nebula_user_id'])
    return result['nebula_user_id']


def test_handle_turn_no_tool_calls():
    """Simplest path: model answers directly, no tools. Confirms
    result.reply_text is set and the reply gets stored to memory."""
    responses = [
        NormalizedResponse(content="Hi Test User, I'm doing well!", tool_calls=[]),
    ]
    handler, db, auth = make_handler_with_fake_provider(responses)
    setup_approved_user(db, auth)

    result = asyncio.run(handler.handle_turn(
        source_platform="discord", platform_user_id="12345",
        display_name="Test User", message_text="how are you?",
    ))

    assert not result.is_blocked
    assert result.reply_text == "Hi Test User, I'm doing well!"
    assert handler.provider.call_count == 1

    history = db.get_conversation_history(1, limit=10)
    assert len(history) == 2  # user message + assistant reply
    assert history[0]['role'] == 'user'
    assert history[1]['role'] == 'assistant'
    assert history[1]['content'] == "Hi Test User, I'm doing well!"
    print("PASS: test_handle_turn_no_tool_calls")


def test_handle_turn_one_tool_call_round():
    """Model requests one tool call, then answers on the second round.
    This is exactly the bug scenario from ai/handler.py's own comments:
    confirms the SECOND call() actually happens (round-trip works) and
    that ONLY the final synthesized content gets stored to memory --
    not the tool result, not None."""
    tool_call = NormalizedToolCall(id="call_1", name="search", arguments={"query": "weather"})
    responses = [
        NormalizedResponse(content=None, tool_calls=[tool_call]),
        NormalizedResponse(content="It's sunny in Tehran today!", tool_calls=[]),
    ]
    handler, db, auth = make_handler_with_fake_provider(responses)
    setup_approved_user(db, auth)

    result = asyncio.run(handler.handle_turn(
        source_platform="discord", platform_user_id="12345",
        display_name="Test User", message_text="what's the weather in Tehran?",
    ))

    assert not result.is_blocked
    assert result.reply_text == "It's sunny in Tehran today!"
    # Confirms the round-trip: call() was invoked TWICE (once producing
    # the tool_calls response, once producing the final answer) -- this
    # is the exact fix the original MAX_TOOL_ROUNDS loop was written for.
    assert handler.provider.call_count == 2
    assert len(handler.provider.append_tool_round_calls) == 1

    history = db.get_conversation_history(1, limit=10)
    assert len(history) == 2  # user message + assistant's FINAL reply only
    assert history[1]['content'] == "It's sunny in Tehran today!"
    # Confirm the tool's own raw output never got stored as the
    # assistant's memory entry (the original bug's symptom).
    assert "search" not in history[1]['content'].lower()
    print("PASS: test_handle_turn_one_tool_call_round")


def test_handle_turn_multiple_tool_call_rounds():
    """Two full tool-calling rounds before a final answer -- confirms
    the loop handles more than one round correctly and stays within
    MAX_TOOL_ROUNDS (5)."""
    tool_call_1 = NormalizedToolCall(id="call_1", name="search", arguments={"query": "weather"})
    tool_call_2 = NormalizedToolCall(id="call_2", name="search", arguments={"query": "forecast tomorrow"})
    responses = [
        NormalizedResponse(content=None, tool_calls=[tool_call_1]),
        NormalizedResponse(content=None, tool_calls=[tool_call_2]),
        NormalizedResponse(content="Sunny today, rain expected tomorrow.", tool_calls=[]),
    ]
    handler, db, auth = make_handler_with_fake_provider(responses)
    setup_approved_user(db, auth)

    result = asyncio.run(handler.handle_turn(
        source_platform="discord", platform_user_id="12345",
        display_name="Test User", message_text="what's the weather like this week?",
    ))

    assert not result.is_blocked
    assert result.reply_text == "Sunny today, rain expected tomorrow."
    assert handler.provider.call_count == 3
    assert len(handler.provider.append_tool_round_calls) == 2
    print("PASS: test_handle_turn_multiple_tool_call_rounds")


def test_handle_turn_max_rounds_exhausted():
    """If the model keeps requesting tools past MAX_TOOL_ROUNDS, the
    loop stops without a final synthesized reply, but doesn't crash and
    doesn't store a None/garbage assistant message."""
    tool_call = NormalizedToolCall(id="call_n", name="search", arguments={"query": "x"})
    # One more tool-requesting response than MAX_TOOL_ROUNDS allows.
    responses = [NormalizedResponse(content=None, tool_calls=[tool_call])] * (AIHandler.MAX_TOOL_ROUNDS + 1)
    handler, db, auth = make_handler_with_fake_provider(responses)
    setup_approved_user(db, auth)

    result = asyncio.run(handler.handle_turn(
        source_platform="discord", platform_user_id="12345",
        display_name="Test User", message_text="keep searching forever",
    ))

    assert not result.is_blocked
    assert result.reply_text is None  # no final content was ever produced
    assert handler.provider.call_count == AIHandler.MAX_TOOL_ROUNDS  # capped, didn't run away
    assert len(result.tool_messages) == AIHandler.MAX_TOOL_ROUNDS  # but tool results were still surfaced

    history = db.get_conversation_history(1, limit=10)
    assert len(history) == 1  # only the user's message -- no assistant entry was stored
    print("PASS: test_handle_turn_max_rounds_exhausted")


def test_handle_turn_unconfigured_provider_still_blocks_gracefully():
    """Confirms the pre-existing (deliberately unchanged) behavior: an
    unconfigured provider blocks the turn with the generic user-facing
    message, AFTER a coin has already been spent -- not before."""
    tmpdir = tempfile.mkdtemp()
    db = DatabaseManager(db_path=os.path.join(tmpdir, 'test.db'))
    auth = AuthManager(db)
    memory = MemoryManager(db)
    coins = CoinManager(db)
    search = SearchTool()

    for var in ['AI_PROVIDER', 'AI_API_KEY', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'AI_MODEL']:
        os.environ.pop(var, None)

    handler = AIHandler(db, auth, memory, coins, search)
    assert handler.provider is None

    nebula_user_id = setup_approved_user(db, auth)
    balance_before = coins.get_status(nebula_user_id)['balance']

    result = asyncio.run(handler.handle_turn(
        source_platform="discord", platform_user_id="12345",
        display_name="Test User", message_text="hello?",
    ))

    assert result.is_blocked
    assert result.blocked_reason == AIHandler.user_facing_unconfigured_message()
    # No provider-specific detail leaks into the user-facing path.
    assert "AI_PROVIDER" not in result.blocked_reason
    assert "AI_API_KEY" not in result.blocked_reason

    balance_after = coins.get_status(nebula_user_id)['balance']
    assert balance_after == balance_before - CoinManager.MESSAGE_COST, (
        "pre-existing behavior (coin spent before provider-configured check) "
        "must remain unchanged by this refactor"
    )
    print("PASS: test_handle_turn_unconfigured_provider_still_blocks_gracefully")


ALL_TESTS = [
    test_handle_turn_no_tool_calls,
    test_handle_turn_one_tool_call_round,
    test_handle_turn_multiple_tool_call_rounds,
    test_handle_turn_max_rounds_exhausted,
    test_handle_turn_unconfigured_provider_still_blocks_gracefully,
]

if __name__ == "__main__":
    failures = []
    for test_fn in ALL_TESTS:
        try:
            test_fn()
        except Exception as e:
            failures.append((test_fn.__name__, e))
            print(f"FAIL: {test_fn.__name__} — {type(e).__name__}: {e}")

    print()
    print(f"{len(ALL_TESTS) - len(failures)}/{len(ALL_TESTS)} passed")
    if failures:
        sys.exit(1)
