"""Provider abstraction: the interface every AI backend (OpenAI, Anthropic,
Google, and OpenAI-compatible endpoints like xAI/OpenRouter/Groq) is
normalized behind, so ai/handler.py never imports or branches on a
specific SDK.

Design principle (confirmed): normalization happens NOW, not as a later
phase. Every provider converts its own SDK's response shape into
NormalizedResponse immediately in call(), and every provider owns its
own conversation-history formatting in append_tool_round(). handle_turn()
in ai/handler.py only ever sees these two methods and the two
dataclasses below -- it has no branch that says "if provider is X, do Y".

Why append_tool_round() lives on the provider (not in handler.py):
each SDK has an incompatible shape for "here's what the assistant
said, and here's what the tools it called returned":
  - OpenAI: a role="assistant" message carrying tool_calls, followed by
    one role="tool" message per call (see the existing, working
    implementation this replaces in ai/handler.py's tool-calling loop
    for the concrete shape).
  - Anthropic: a role="assistant" message whose content is a list
    including tool_use blocks, followed by a role="user" message whose
    content is a list of tool_result blocks.
  - Google (google-genai): a Content(role="model", parts=[...]) --
    conveniently just response.candidates[0].content, appendable as-is
    -- followed by a Content(role="user", parts=[Part(function_response=...)])
    per call.
None of these three shapes are interchangeable, and none of them are
OpenAI's shape with different field names -- forcing them through one
shared function in handler.py would mean that function still needs a
per-provider branch internally, which is exactly the coupling this
abstraction exists to avoid. Keeping the formatting logic in the
provider file that already knows the SDK's types is what keeps
handler.py itself provider-agnostic.

--- Web panel addition: multimodal image input (confirmed with Sina) ---

call() gains a new `images` parameter, a list of ImageAttachment (below).
Default is None/empty, which is a no-op for Discord/Telegram -- neither
adapter passes images, so their behavior (and every existing test) is
completely unchanged. Only the web adapter, from its new
multipart-image endpoint, ever populates this.

Each provider's call() is responsible for translating the *last* user
message plus any images into its OWN multimodal content-block shape --
this is deliberately handled inside call() (not upstream in
ai/handler.py) for the same reason tool-schema translation already
lives per-provider: OpenAI/Anthropic/Google each have a genuinely
different, incompatible shape for "text plus an inline image" content
blocks, verified via live SDK inspection (not from memory) for all
three:
  - OpenAI: a list content value on the message, mixing
    {"type": "text", ...} and {"type": "image_url", "image_url":
    {"url": "data:<mime>;base64,<data>"}} parts.
  - Anthropic: a list content value on the message, mixing
    {"type": "text", ...} and {"type": "image", "source": {"type":
    "base64", "media_type": <mime>, "data": <b64 str>}} parts.
  - Google: genai.types.Part.from_bytes(data=<raw bytes>,
    mime_type=<mime>) alongside a Part(text=...), inside one Content.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImageAttachment:
    """One image to attach to the CURRENT user turn, provider-agnostic.

    data: raw image bytes (not base64-encoded, not a data URL -- each
    provider's call() does whatever encoding its own SDK needs; keeping
    this field as raw bytes means the web_backend layer that reads an
    uploaded file doesn't need to know anything about any provider's
    preferred encoding).

    mime_type: e.g. "image/jpeg", "image/png", "image/webp", "image/gif"
    -- the same four types Anthropic's SDK enumerates as valid
    (verified via live inspection), which in practice is also what
    OpenAI and Google both accept, so no per-provider allow-list
    divergence to track here. web_backend/ is responsible for
    rejecting anything outside this set before it ever reaches a
    provider (see web_backend's upload validation).
    """
    data: bytes
    mime_type: str


@dataclass
class NormalizedToolCall:
    """One tool/function call requested by the model, in a shape that's
    identical regardless of which provider produced it.

    id: a string that append_tool_round() can use to match this call to
    its result. For OpenAI and Anthropic, this is always the SDK's own
    real tool_call_id / tool_use id. For Google, FunctionCall.id is
    documented as optional -- populated only "if the client should
    execute the function_call and return the response with the
    matching id". When the SDK omits it, ai/providers/google_sdk.py
    synthesizes a local, per-response-unique id (see that file) purely
    so this field is never empty; that synthesized id is never sent
    back to Google's API, since google_sdk.py's own append_tool_round()
    is the only code that ever reads it, and it uses position/name
    matching, not the id, when building the FunctionResponse parts.

    arguments: already JSON-parsed into a dict. OpenAI and Google both
    hand back parsed args natively; Anthropic's tool_use.input is
    already a dict too (never a JSON string needing parsing on any of
    the three SDKs) -- so no provider's call() needs to do its own
    json.loads() here, and ai/handler.py never needs to know that was
    ever a concern.
    """
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class NormalizedResponse:
    """What a single provider.call() returns, regardless of provider.

    content: the final text reply, if the model produced one instead of
    (or in addition to any trailing text alongside) requesting tools.
    None when the model's turn consists ONLY of tool call(s) -- mirrors
    the existing, working assumption in ai/handler.py's tool-calling
    loop, where `if not response_message.tool_calls: final_content =
    response_message.content; break` is the only place content is read
    for the final reply, and content is otherwise ignored on rounds
    that have tool_calls.

    tool_calls: empty list (not None) when the model produced a final
    answer with no tool use. ai/handler.py's loop condition becomes
    `if not response.tool_calls:` unchanged from today's
    `if not response_message.tool_calls:`.

    raw: the provider's own native response/message object, untouched.
    ai/handler.py never reads this field -- it exists solely so each
    provider's OWN append_tool_round() can pull whatever it needs
    (e.g. Anthropic's content blocks, or Google's candidates[0].content)
    without re-deriving it from the normalized fields above, which
    would lose information (e.g. Anthropic thinking blocks, Google
    thought signatures) that must round-trip back to the SDK unchanged
    for multi-turn tool use to work correctly.
    """
    content: Optional[str]
    tool_calls: List[NormalizedToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseProvider(ABC):
    """One instance per configured AI backend. Constructed once by
    ai/handler.py's provider-resolution logic (see ai/handler.py) and
    reused for the lifetime of the process, the same way the single
    AsyncOpenAI client used to be constructed once in the old
    _setup_openai().
    """

    @abstractmethod
    async def call(
        self,
        messages: List[Dict],
        tools: List[Dict],
        system_prompt: str,
        images: Optional[List[ImageAttachment]] = None,
    ) -> NormalizedResponse:
        """Make one request to this provider's API and return a
        NormalizedResponse.

        messages: the CURRENT accumulated conversation for this turn,
        in the provider's OWN native format -- NOT a shared universal
        format. On the very first call of a turn, this is built from
        core/memory.py's get_conversation_context() output, which is
        already `{"role": ..., "content": ...}` dicts; every provider
        accepts that shape as plain user/assistant turns (OpenAI and
        Anthropic both use "role"/"content" directly; Google's
        translation from this simple shape into Content/Part objects
        happens inside google_sdk.py's call(), not in handler.py). On
        subsequent calls within the same tool-calling loop (see
        MAX_TOOL_ROUNDS in ai/handler.py), messages has already been
        extended by THIS provider's own append_tool_round() from the
        previous round, so it's in this provider's native shape by
        then, not the simple universal one -- each provider's call()
        must accept both its own extended shape AND the plain
        {"role", "content"} shape memory hands it on round one.

        tools: OpenAI function-calling format (the shape already
        produced by ai/handler.py's existing get_available_tools() --
        unchanged by this refactor). Each provider's call() is
        responsible for translating this into its own tool schema
        (Anthropic's flat name/description/input_schema tool blocks,
        Google's FunctionDeclaration objects) before calling its SDK.

        system_prompt: plain string, loaded once from system.txt by
        ai/handler.py, unchanged from today.

        images: optional list of ImageAttachment to attach to the LAST
        message in `messages` (i.e. the current user turn). None or
        empty (the default) is a complete no-op -- every provider's
        call() must produce byte-for-byte the same request it would
        have without this parameter when images is falsy, which is
        what keeps Discord/Telegram (which never pass images)
        unaffected by this addition. Only meaningful on the FIRST
        call() of a turn (round one) -- images are never attached to
        synthetic tool-round messages.
        """
        raise NotImplementedError

    @abstractmethod
    def append_tool_round(
        self,
        messages: List[Dict],
        response: NormalizedResponse,
        tool_results: List[str],
    ) -> List[Dict]:
        """Given the messages sent to produce `response`, the
        NormalizedResponse itself (whose .raw holds this provider's
        native message/candidate object), and the plain string result
        of executing each of response.tool_calls (same order), return
        the new `messages` list to send on the NEXT call() -- i.e. the
        original messages plus whatever this provider's SDK needs
        appended to represent "the assistant asked for these tools" and
        "here's what they returned".

        tool_results[i] corresponds to response.tool_calls[i] -- same
        indexing ai/handler.py's tool-execution loop already uses today
        when it iterates response_message.tool_calls in order.

        Returns a NEW list (or the same list mutated and returned,
        implementation's choice) rather than mutating in place silently
        -- ai/handler.py always reassigns `messages = provider.
        append_tool_round(...)`, so either approach behaves correctly,
        but returning explicitly keeps the call site readable.
        """
        raise NotImplementedError
