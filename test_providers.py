"""Smoke tests for ai/providers/*.py, using mocked SDK clients.

Per the handoff's explicit requirement: verify call() and
append_tool_round() both work correctly for (a) a final-answer response
with no tool calls, and (b) a response requesting one or more tool
calls, for each of the three provider implementations.

These tests mock at the SDK-client boundary (the object each provider
constructs internally: AsyncOpenAI, AsyncAnthropic, genai.Client) rather
than mocking BaseProvider itself, since the actual thing under test is
each provider's translation logic -- SDK response shape in,
NormalizedResponse out, and back again through append_tool_round().

Run with: python3 -m pytest tests/test_providers.py -v
(or: python3 tests/test_providers.py, since each test function is also
directly callable and this file's __main__ block runs them all without
requiring pytest to be installed).
"""
import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, '.')

from ai.providers.base import NormalizedResponse, NormalizedToolCall

SAMPLE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search the web",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}]

SAMPLE_MESSAGES = [{"role": "user", "content": "[Sina]: what's the weather in Tehran?"}]
SAMPLE_SYSTEM_PROMPT = "You are Nebula, a helpful assistant."


def run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------------
# OpenAISDKProvider
# ----------------------------------------------------------------------

def test_openai_final_answer_no_tools():
    from ai.providers.openai_sdk import OpenAISDKProvider

    provider = OpenAISDKProvider(api_key="fake", model="gpt-test")

    mock_message = SimpleNamespace(content="The weather in Tehran is sunny.", tool_calls=None)
    mock_message.model_dump = MagicMock(return_value={"role": "assistant", "content": "The weather in Tehran is sunny."})
    mock_response = SimpleNamespace(choices=[SimpleNamespace(message=mock_message)])
    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content == "The weather in Tehran is sunny."
    assert result.tool_calls == []
    assert not result.has_tool_calls
    print("PASS: test_openai_final_answer_no_tools")


def test_openai_tool_call_requested_and_round_trip():
    from ai.providers.openai_sdk import OpenAISDKProvider

    provider = OpenAISDKProvider(api_key="fake", model="gpt-test")

    mock_tool_call = SimpleNamespace(
        id="call_abc123",
        function=SimpleNamespace(name="search", arguments='{"query": "weather in Tehran"}'),
    )
    mock_message = SimpleNamespace(content=None, tool_calls=[mock_tool_call])
    mock_message.model_dump = MagicMock(return_value={
        "role": "assistant", "content": None,
        "tool_calls": [{"id": "call_abc123", "type": "function",
                         "function": {"name": "search", "arguments": '{"query": "weather in Tehran"}'}}],
    })
    mock_response = SimpleNamespace(choices=[SimpleNamespace(message=mock_message)])
    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content is None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_abc123"
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == {"query": "weather in Tehran"}
    assert result.has_tool_calls

    new_messages = provider.append_tool_round(
        SAMPLE_MESSAGES, result, ["Sunny, 28C in Tehran today."]
    )
    # Original message + assistant tool_calls message + one tool result message
    assert len(new_messages) == len(SAMPLE_MESSAGES) + 2
    assert new_messages[-2]["tool_calls"][0]["id"] == "call_abc123"
    assert new_messages[-1] == {
        "role": "tool", "tool_call_id": "call_abc123",
        "content": "Sunny, 28C in Tehran today.",
    }
    print("PASS: test_openai_tool_call_requested_and_round_trip")


# ----------------------------------------------------------------------
# AnthropicSDKProvider
# ----------------------------------------------------------------------

def test_anthropic_final_answer_no_tools():
    from ai.providers.anthropic_sdk import AnthropicSDKProvider

    provider = AnthropicSDKProvider(api_key="fake", model="claude-test")

    text_block = SimpleNamespace(type="text", text="The weather in Tehran is sunny.")
    mock_response = SimpleNamespace(content=[text_block])
    provider.client.messages.create = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content == "The weather in Tehran is sunny."
    assert result.tool_calls == []
    assert not result.has_tool_calls
    print("PASS: test_anthropic_final_answer_no_tools")


def test_anthropic_tool_call_requested_and_round_trip():
    from ai.providers.anthropic_sdk import AnthropicSDKProvider

    provider = AnthropicSDKProvider(api_key="fake", model="claude-test")

    tool_use_block = SimpleNamespace(
        type="tool_use", id="toolu_xyz789", name="search",
        input={"query": "weather in Tehran"},
    )
    mock_response = SimpleNamespace(content=[tool_use_block])
    provider.client.messages.create = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content is None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "toolu_xyz789"
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == {"query": "weather in Tehran"}
    assert result.has_tool_calls

    new_messages = provider.append_tool_round(
        SAMPLE_MESSAGES, result, ["Sunny, 28C in Tehran today."]
    )
    # Original message + one assistant message (full content block list)
    # + one user message (batched tool_result blocks)
    assert len(new_messages) == len(SAMPLE_MESSAGES) + 2
    assert new_messages[-2] == {"role": "assistant", "content": [tool_use_block]}
    assert new_messages[-1] == {
        "role": "user",
        "content": [{
            "type": "tool_result", "tool_use_id": "toolu_xyz789",
            "content": "Sunny, 28C in Tehran today.",
        }],
    }
    print("PASS: test_anthropic_tool_call_requested_and_round_trip")


def test_anthropic_thinking_level_maps_to_budget_tokens():
    from ai.providers.anthropic_sdk import AnthropicSDKProvider

    provider = AnthropicSDKProvider(api_key="fake", model="claude-test", thinking_level="medium")
    assert provider.budget_tokens == 10000

    provider_none = AnthropicSDKProvider(api_key="fake", model="claude-test", thinking_level=None)
    assert provider_none.budget_tokens is None
    print("PASS: test_anthropic_thinking_level_maps_to_budget_tokens")


# ----------------------------------------------------------------------
# GoogleSDKProvider
# ----------------------------------------------------------------------

def test_google_final_answer_no_tools():
    from ai.providers.google_sdk import GoogleSDKProvider

    provider = GoogleSDKProvider(api_key="fake", model="gemini-test")

    mock_response = SimpleNamespace(
        text="The weather in Tehran is sunny.",
        function_calls=None,
        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
    )
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content == "The weather in Tehran is sunny."
    assert result.tool_calls == []
    assert not result.has_tool_calls
    print("PASS: test_google_final_answer_no_tools")


def test_google_tool_call_requested_and_round_trip():
    from ai.providers.google_sdk import GoogleSDKProvider

    provider = GoogleSDKProvider(api_key="fake", model="gemini-test")

    # Real Google FunctionCall.id is documented optional -- test the
    # common case where the SDK does NOT supply one, exercising this
    # provider's id-synthesis path.
    mock_function_call = SimpleNamespace(id=None, name="search", args={"query": "weather in Tehran"})
    mock_model_content = SimpleNamespace(role="model", parts=["<native function_call part>"])
    mock_response = SimpleNamespace(
        text=None,
        function_calls=[mock_function_call],
        candidates=[SimpleNamespace(content=mock_model_content)],
    )
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = run(provider.call(SAMPLE_MESSAGES, SAMPLE_TOOLS, SAMPLE_SYSTEM_PROMPT))

    assert result.content is None
    assert len(result.tool_calls) == 1
    # Synthesized id, since the mocked FunctionCall.id was None
    assert result.tool_calls[0].id.startswith("google_call_")
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == {"query": "weather in Tehran"}
    assert result.has_tool_calls

    new_messages = provider.append_tool_round(
        SAMPLE_MESSAGES, result, ["Sunny, 28C in Tehran today."]
    )
    assert len(new_messages) == len(SAMPLE_MESSAGES) + 2
    # The model's own native Content object is appended AS-IS (identity
    # check, not just equality) -- this is required to preserve thought
    # signatures for multi-turn continuity.
    assert new_messages[-2] is mock_model_content
    # The trailing user-role Content carries the function_response part;
    # inspect it via the real genai types since this provider constructs
    # real Content/Part/FunctionResponse objects, not dicts.
    from google.genai import types as genai_types
    assert isinstance(new_messages[-1], genai_types.Content)
    assert new_messages[-1].role == "user"
    assert len(new_messages[-1].parts) == 1
    fr = new_messages[-1].parts[0].function_response
    assert fr.name == "search"
    assert fr.response == {"output": "Sunny, 28C in Tehran today."}
    # Synthesized id must NOT be echoed back to the SDK.
    assert fr.id is None
    print("PASS: test_google_tool_call_requested_and_round_trip")


def test_google_thinking_level_uppercased():
    from ai.providers.google_sdk import GoogleSDKProvider

    provider = GoogleSDKProvider(api_key="fake", model="gemini-test", thinking_level="high")
    assert provider.thinking_level == "HIGH"
    print("PASS: test_google_thinking_level_uppercased")


ALL_TESTS = [
    test_openai_final_answer_no_tools,
    test_openai_tool_call_requested_and_round_trip,
    test_anthropic_final_answer_no_tools,
    test_anthropic_tool_call_requested_and_round_trip,
    test_anthropic_thinking_level_maps_to_budget_tokens,
    test_google_final_answer_no_tools,
    test_google_tool_call_requested_and_round_trip,
    test_google_thinking_level_uppercased,
]

if __name__ == "__main__":
    failures = []
    for test_fn in ALL_TESTS:
        try:
            test_fn()
        except Exception as e:
            failures.append((test_fn.__name__, e))
            print(f"FAIL: {test_fn.__name__} — {e}")

    print()
    print(f"{len(ALL_TESTS) - len(failures)}/{len(ALL_TESTS)} passed")
    if failures:
        sys.exit(1)
