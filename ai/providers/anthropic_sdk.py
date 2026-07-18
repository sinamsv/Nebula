"""Anthropic SDK provider.

Verified against the installed anthropic==0.117.0 package (not written
from memory -- see the investigation this handoff continued):
- AsyncAnthropic().messages.create() takes system as a top-level string
  param (not a messages[0] entry the way OpenAI does it), plus
  messages, model, max_tokens (required, unlike OpenAI where it's
  optional), temperature, tools, tool_choice, thinking.
- thinking's type, ThinkingConfigParam, is a Union of THREE TypedDicts,
  not two: ThinkingConfigEnabledParam ({"type": "enabled",
  "budget_tokens": int, "display": optional}), ThinkingConfigDisabledParam
  ({"type": "disabled"}), and ThinkingConfigAdaptiveParam ({"type":
  "adaptive", "display": optional}). This third "adaptive" variant
  wasn't in the original plan (which only anticipated
  enabled/disabled) -- it's surfaced here as a known option but
  deliberately NOT wired into thinking_level's mapping below, since the
  confirmed design maps exactly the three project-defined levels (low/
  medium/high) plus null; adding a fourth, unrequested behavior variant
  is a decision for Sina to make explicitly, not something to infer
  silently. thinking_level=None simply omits the `thinking` kwarg
  entirely (verified as valid -- the param's type allows Omit).

Multimodal image support (verified via live inspection of
anthropic.types.ImageBlockParam / Base64ImageSourceParam in the
installed package): Anthropic wants image content as
{"type": "image", "source": {"type": "base64", "media_type": <mime>,
"data": <b64 str>}} -- separate media_type/data fields, NOT a combined
data: URL the way OpenAI does it. media_type is a closed enum of
exactly image/jpeg, image/png, image/gif, image/webp in this SDK
version -- ai/providers/base.py's ImageAttachment.mime_type is
documented to match this same set, with web_backend/ responsible for
rejecting anything else before it reaches this provider.
"""
import base64
import json
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from ai.providers.base import BaseProvider, ImageAttachment, NormalizedResponse, NormalizedToolCall

# Confirmed mapping (Sina: "منطقی و خوب هست" -- these three numbers are
# approved, not placeholders). null is handled separately in __init__
# by simply never setting self.budget_tokens, so no "null" key belongs
# in this dict.
_THINKING_LEVEL_TO_BUDGET_TOKENS = {
    "low": 4000,
    "medium": 10000,
    "high": 24000,
}


class AnthropicSDKProvider(BaseProvider):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None,
                 temperature: float = 0.7, thinking_level: Optional[str] = None):
        if base_url:
            self.client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature

        self.budget_tokens: Optional[int] = None
        if thinking_level:
            if thinking_level not in _THINKING_LEVEL_TO_BUDGET_TOKENS:
                raise ValueError(
                    f"Unknown thinking_level '{thinking_level}' for Anthropic "
                    f"provider. Valid values: "
                    f"{list(_THINKING_LEVEL_TO_BUDGET_TOKENS)} or null."
                )
            self.budget_tokens = _THINKING_LEVEL_TO_BUDGET_TOKENS[thinking_level]

    async def call(self, messages: List[Dict], tools: List[Dict],
                    system_prompt: str,
                    images: Optional[List[ImageAttachment]] = None) -> NormalizedResponse:
        anthropic_tools = [self._to_anthropic_tool(t) for t in tools] if tools else None

        call_messages = list(messages)
        if images:
            call_messages[-1] = self._attach_images_to_message(call_messages[-1], images)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "messages": call_messages,
            "max_tokens": 2000,
            "temperature": self.temperature,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            kwargs["tool_choice"] = {"type": "auto"}
        if self.budget_tokens is not None:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.budget_tokens}
            # Anthropic requires max_tokens > budget_tokens; bump max_tokens
            # up front rather than surfacing an opaque 400 from the API.
            # 2000 (this project's existing fixed max_tokens everywhere
            # else) is below even the "low" budget of 4000, so this
            # branch is not just a defensive edge case -- it's the
            # common case whenever thinking is enabled at all.
            kwargs["max_tokens"] = max(2000, self.budget_tokens + 1024)

        response = await self.client.messages.create(**kwargs)

        text_parts = []
        normalized_tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                normalized_tool_calls.append(NormalizedToolCall(
                    id=block.id,
                    name=block.name,
                    # Anthropic hands back tool_use.input already
                    # parsed as a dict -- never a JSON string -- so no
                    # json.loads() needed here (see base.py's
                    # NormalizedToolCall.arguments docstring).
                    arguments=block.input,
                ))
            # "thinking" content blocks (when budget_tokens is set) are
            # deliberately not collected into text_parts -- they're
            # internal reasoning, not the user-facing reply, mirroring
            # how OpenAI's reasoning_effort output never surfaces
            # reasoning tokens as message content either. They DO
            # remain present on response.content itself, so
            # append_tool_round() below still round-trips them
            # correctly for multi-turn continuity (required for
            # extended thinking across tool-calling rounds).

        return NormalizedResponse(
            content="".join(text_parts) if text_parts else None,
            tool_calls=normalized_tool_calls,
            raw=response,
        )

    @staticmethod
    def _attach_images_to_message(message: Dict, images: List[ImageAttachment]) -> Dict:
        """Rewrite a plain {"role": ..., "content": "<str>"} message
        into Anthropic's multimodal list-content shape: a text block
        (the original string content) plus one image block per
        attachment, base64-encoded with separate media_type/data
        fields -- the exact shape verified against ImageBlockParam /
        Base64ImageSourceParam in the installed SDK (see module
        docstring). Only ever called on the LAST message of a turn."""
        original_text = message.get("content", "")
        content_blocks: List[Dict] = []
        if original_text:
            content_blocks.append({"type": "text", "text": original_text})
        for img in images:
            b64_data = base64.b64encode(img.data).decode("utf-8")
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": img.mime_type, "data": b64_data},
            })
        return {**message, "content": content_blocks}

    def append_tool_round(self, messages: List[Dict], response: NormalizedResponse,
                           tool_results: List[str]) -> List[Dict]:
        """Anthropic's shape: the assistant's full content block list
        (text + thinking + tool_use blocks, in the order the model
        produced them) becomes one role="assistant" message, unchanged
        from response.raw.content -- appending this AS THE SDK RETURNED
        IT (not reconstructed) is what preserves thinking-block
        signatures for multi-turn continuity. Then ONE role="user"
        message carries all of this round's tool_result blocks
        together (not one user message per tool call -- Anthropic's API
        expects them batched together when multiple tools were called
        in parallel)."""
        new_messages = list(messages)
        new_messages.append({"role": "assistant", "content": response.raw.content})

        tool_result_blocks = []
        for tool_call, result in zip(response.tool_calls, tool_results):
            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result or "(tool returned no output)",
            })
        new_messages.append({"role": "user", "content": tool_result_blocks})

        return new_messages

    @staticmethod
    def _to_anthropic_tool(openai_style_tool: Dict) -> Dict:
        """Translate one entry of ai/handler.py's existing OpenAI
        function-calling format into Anthropic's flat tool block shape.
        ai/handler.py's get_available_tools() output is unchanged by
        this refactor, so this translation step lives here rather than
        upstream."""
        fn = openai_style_tool["function"]
        return {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        }
