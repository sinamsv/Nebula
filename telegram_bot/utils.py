"""Small shared helpers for telegram_bot/ handler modules."""
import re
from typing import Dict, List


def parse_labeled_args(text: str, keys: List[str]) -> Dict[str, str]:
    """Parse 'key:value key2:value2' style arguments out of a Telegram
    command message's raw text.

    Telegram has no native named-parameter mechanism the way Discord's
    slash commands do (no autocomplete UI, no per-parameter schema) --
    everything after a command is just free text. This project's
    Discord commands use named parameters (username, password, code,
    ...), and /sync's own output literally tells the user to type
    `/verify username:X code:Y` on Telegram, so handlers here parse
    that same key:value convention out of the raw text rather than
    switching to Telegram's more common space-separated positional
    style. It also means each value is self-documenting inline, which
    matters more here than on Discord since there's no builder UI
    showing parameter names as the user types.

    Returns {key: value} for every key found; a key with no match is
    simply absent from the result -- callers check for required keys
    themselves and reply with their own usage message. Values are
    whitespace-delimited (no spaces inside a value), matching how
    usernames/passwords/codes are already validated elsewhere in this
    project to be space-free tokens.
    """
    result = {}
    for key in keys:
        match = re.search(rf'{re.escape(key)}:(\S+)', text)
        if match:
            result[key] = match.group(1)
    return result
