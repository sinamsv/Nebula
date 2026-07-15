"""OpenAI-family provider: covers the official OpenAI API AND every
OpenAI-compatible endpoint that has no dedicated SDK of its own (xAI,
OpenRouter, Groq -- see ai/config.json). All four are the exact same
AsyncOpenAI client pointed at a different base_url; there is nothing
provider-specific to branch on internally, which is why this single
file covers all of them rather than one file per compatible endpoint
(confirmed architecture decision -- see the handoff prompt's file
structure section).

This is a fairly direct extraction of the tool-calling shape that
already existed, working, in ai/handler.py before this refactor -- see
that file's git history / the pre-refactor version for the original
inline version of this same logic. Verified against the installed
openai==2.45.0 package; AsyncOpenAI's constructor signature (api_key,
base_url, ...) is unchanged from what the pre-refactor code already
relied on, so no behavior changes here, only relocation +
normalization.
"""
import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ai.providers.base import BaseProvider, NormalizedResponse, NormalizedToolCall


class OpenAISDKProvider(BaseProvider):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None,
                 temperature: float = 0.7, thinking_level: Optional[str] = None):
        """base_url=None lets AsyncOpenAI fall back to its own built-in
        default (api.openai.com) -- same behavior as the pre-refactor
        `AsyncOpenAI(api_key=api_key)` no-base_url branch in the old
        _setup_openai(). For xai/openrouter/groq, ai/handler.py's
        provider-resolution logic always passes a concrete base_url
        from ai/config.json (required for those three, since none of
        them have a default to fall back to)."""
        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        # thinking_level is passed straight through as reasoning_effort
        # -- no word-to-number translation needed here, unlike
        # anthropic_sdk.py. OpenAI's o-series, and xAI's reasoning
        # models, both accept these same words directly. If the
        # selected model doesn't support reasoning_effort at all, the
        # API will reject or ignore the field -- that's a model-choice
        # concern outside this abstraction's scope (confirmed).
        self.thinking_level = thinking_level

    async def call(self, messages: List[Dict], tools: List[Dict],
                    system_prompt: str) -> NormalizedResponse:
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": full_messages,
            "tools": tools if tools else None,
            "tool_choice": "auto" if tools else None,
            "temperature": self.temperature,
            "max_tokens": 2000,
        }
        if self.thinking_level:
            kwargs["reasoning_effort"] = self.thinking_level

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        normalized_tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                normalized_tool_calls.append(NormalizedToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return NormalizedResponse(
            content=message.content,
            tool_calls=normalized_tool_calls,
            raw=message,
        )

    def append_tool_round(self, messages: List[Dict], response: NormalizedResponse,
                           tool_results: List[str]) -> List[Dict]:
        """Identical shape to the pre-refactor inline version: append
        the assistant's own tool_calls message exactly as the SDK sent
        it (model_dump(exclude_unset=True) -- this is what makes the
        follow-up tool_call_id references valid on the next call), then
        one role="tool" message per call, matched positionally to
        response.tool_calls / tool_results (same indexing contract
        documented on BaseProvider.append_tool_round)."""
        new_messages = list(messages)
        new_messages.append(response.raw.model_dump(exclude_unset=True))

        for tool_call, result in zip(response.tool_calls, tool_results):
            new_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result or "(tool returned no output)",
            })

        return new_messages
