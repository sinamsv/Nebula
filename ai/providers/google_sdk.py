"""Google (Gemini) SDK provider, using the new unified `google-genai`
package (2.x), NOT the old `google-generativeai` package (confirmed
decision -- do not swap this for the old package).

Verified against the installed google-genai==2.11.0 package:
- genai.Client(api_key=..., http_options=types.HttpOptions(base_url=...))
  is how base_url override works here -- there's no separate base_url
  kwarg on Client() itself the way AsyncOpenAI/AsyncAnthropic have one;
  it has to go through http_options. Async calls live under
  client.aio.models.generate_content(...), not client.models... (the
  sync namespace) -- using the sync one from an async method would
  block the event loop.
- config=types.GenerateContentConfig(...) carries system_instruction,
  temperature, tools, and thinking_config -- there's no separate
  "system" or "tools" kwarg to generate_content() itself, everything
  goes through config (unlike OpenAI/Anthropic where these are
  separate top-level params).
- types.FunctionDeclaration has a `parameters_json_schema` field that
  accepts a plain JSON Schema dict directly (explicitly documented as
  mutually exclusive with the alternative `parameters` field, which
  wants Google's own `Schema` object type) -- so ai/handler.py's
  existing OpenAI-format tool parameter schemas can be passed straight
  through here with no rewriting into Schema objects.
- response.text and response.function_calls are both ready-made
  properties on GenerateContentResponse -- no manual candidates[0].
  content.parts walking needed for the normalized fields (though
  append_tool_round() below does still reach into
  candidates[0].content directly, since that's the one native object
  that needs to round-trip unchanged).

RESOLVED (was an open question in the original plan -- confirmed via
SDK inspection + web search, see investigation notes): Gemini's
thinking config is NOT purely numeric like Anthropic's. The installed
SDK's types.ThinkingConfig has BOTH a numeric `thinking_budget: int`
field (the older mechanism, primary for Gemini 2.5-generation models)
AND a `thinking_level: ThinkingLevel` enum field (LOW/MEDIUM/HIGH, plus
MINIMAL -- the newer mechanism, for Gemini 3.x-generation models and
later). Per Google's own docs (confirmed via web search, since this
postdates training-data knowledge for either of us): the two are
MUTUALLY EXCLUSIVE -- setting both in the same request is a hard API
error, not a "one wins" situation.

Conveniently, ThinkingLevel's own enum values are literally "LOW",
"MEDIUM", "HIGH" -- an exact match for this project's three
thinking_level words, so no numeric mapping is needed for Google the
way anthropic_sdk.py needs one. This provider always uses
thinking_level (never thinking_budget), matching Google's own current
guidance that budget is being kept only for backward compatibility.

**Caveat that must be called out to Sina, not silently assumed away**:
which mechanism a given Gemini model actually honors depends on the
model generation (thinking_budget for 2.5-era models, thinking_level
for 3.x+). Since AI_MODEL is a free-form string this project doesn't
otherwise validate against a known model list, this provider cannot
determine in advance whether the selected model is old enough that
thinking_level will be rejected. That's the same category of
model-capability mismatch already accepted as out-of-scope for
OpenAI's reasoning_effort (see openai_sdk.py's docstring) -- consistent
treatment, not a new gap introduced here.
"""
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types as genai_types

from ai.providers.base import BaseProvider, NormalizedResponse, NormalizedToolCall


class GoogleSDKProvider(BaseProvider):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None,
                 temperature: float = 0.7, thinking_level: Optional[str] = None):
        http_options = genai_types.HttpOptions(base_url=base_url) if base_url else None
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model
        self.temperature = temperature
        # Uppercased once here (not per-call) since ThinkingLevel's enum
        # members are upper-case ("LOW"/"MEDIUM"/"HIGH") while this
        # project's config.json values are lower-case ("low"/"medium"/
        # "high") to match the OpenAI-family reasoning_effort casing.
        self.thinking_level = thinking_level.upper() if thinking_level else None

    async def call(self, messages: List[Dict], tools: List[Dict],
                    system_prompt: str) -> NormalizedResponse:
        contents = self._to_genai_contents(messages)
        genai_tools = self._to_genai_tools(tools) if tools else None

        config_kwargs: Dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": self.temperature,
            "max_output_tokens": 2000,
        }
        if genai_tools:
            config_kwargs["tools"] = genai_tools
        if self.thinking_level:
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_level=self.thinking_level
            )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )

        normalized_tool_calls = []
        raw_function_calls = response.function_calls or []
        for i, fc in enumerate(raw_function_calls):
            # FunctionCall.id is documented as optional -- populated
            # only when the model wants a matching id back. When it's
            # absent, synthesize a local, response-scoped id (never
            # sent to Google's API -- see base.py's NormalizedToolCall
            # docstring for why this is safe: append_tool_round() below
            # matches by position/name against this SAME response
            # object, not by round-tripping this id through the SDK).
            call_id = fc.id or f"google_call_{i}_{fc.name}"
            normalized_tool_calls.append(NormalizedToolCall(
                id=call_id,
                name=fc.name,
                # FunctionCall.args is already a parsed dict, per the
                # verified SDK source -- no JSON parsing needed.
                arguments=fc.args or {},
            ))

        return NormalizedResponse(
            content=response.text,
            tool_calls=normalized_tool_calls,
            raw=response,
        )

    def append_tool_round(self, messages: List[Dict], response: NormalizedResponse,
                           tool_results: List[str]) -> List[Dict]:
        """Google's shape: response.raw.candidates[0].content is
        already a Content(role="model", parts=[...]) containing
        whatever mix of text/function_call parts the model produced --
        appending it directly (not reconstructed field-by-field) is
        what Google's own multi-turn examples do, and is required to
        preserve thought signatures for thinking-enabled models.
        Tool results then become ONE Content(role="user", parts=[...])
        containing one Part(function_response=...) per call -- Google
        has no separate "tool" role the way OpenAI does; function
        responses are user-role content, matching how Anthropic's
        tool_result blocks are also carried in a user-role message
        (see anthropic_sdk.py's append_tool_round)."""
        new_messages = list(messages)
        new_messages.append(response.raw.candidates[0].content)

        response_parts = []
        for tool_call, result in zip(response.tool_calls, tool_results):
            # Only pass `id` back to the SDK if it's a real id Google
            # itself issued -- our own synthesized "google_call_N_name"
            # ids (see call() above) are local bookkeeping only and
            # were never known to the API, so echoing one back would be
            # sending a made-up id rather than omitting an optional field.
            is_synthesized_id = tool_call.id.startswith("google_call_")
            response_parts.append(genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=None if is_synthesized_id else tool_call.id,
                    name=tool_call.name,
                    response={"output": result or "(tool returned no output)"},
                )
            ))
        new_messages.append(genai_types.Content(role="user", parts=response_parts))

        return new_messages

    @staticmethod
    def _to_genai_contents(messages: List[Dict]) -> List:
        """Translate messages into Gemini's contents list. Two input
        shapes are possible here (see BaseProvider.call()'s docstring):

        1. Plain {"role": "user"|"assistant", "content": str} dicts --
           the shape core/memory.py's get_conversation_context() hands
           back on the FIRST call of a turn. These need translating:
           Gemini's role is "user" or "model", never "assistant", so
           "assistant" must be mapped to "model" here; "user" passes
           through unchanged.
        2. Native genai.types.Content objects -- already produced by
           THIS provider's own append_tool_round() on a previous round
           within the same turn's tool-calling loop. These pass through
           untouched; re-wrapping an already-correct Content object
           would double-nest it.
        """
        contents = []
        for msg in messages:
            if isinstance(msg, genai_types.Content):
                contents.append(msg)
                continue
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=msg["content"])],
            ))
        return contents

    @staticmethod
    def _to_genai_tools(openai_style_tools: List[Dict]) -> List[genai_types.Tool]:
        """Translate ai/handler.py's existing OpenAI-format tool list
        into Google's Tool/FunctionDeclaration objects, using
        parameters_json_schema to pass the existing JSON Schema
        parameter dicts through directly rather than converting them
        into Google's own Schema object type."""
        declarations = []
        for t in openai_style_tools:
            fn = t["function"]
            declarations.append(genai_types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters_json_schema=fn.get("parameters", {"type": "object", "properties": {}}),
            ))
        return [genai_types.Tool(function_declarations=declarations)]
