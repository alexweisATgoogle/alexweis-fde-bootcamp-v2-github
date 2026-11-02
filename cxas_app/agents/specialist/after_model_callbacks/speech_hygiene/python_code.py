from __future__ import annotations

from types import SimpleNamespace
from typing import Optional



def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Cleans every text part of the reply before the caller hears it.

    Strips markdown symbols, masks long numbers to their last 4 digits and
    prefers caller_provided_phone_last4. After a handover it adds
    handoff_message only when the reply has no spoken text at all; it never
    replaces words the model said, so a step-specific or PRD-exact transfer
    line survives. Returns None when nothing changed, so the reply goes out
    untouched.
    """
    state = getattr(callback_context, "state", None)
    state_dict = state if isinstance(state, dict) else {}
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if content is None or parts is None:
        return None
    changed = False
    has_spoken_text = False

    for part in parts:
        text = getattr(part, "text", None)
        if not isinstance(text, str) or not text.strip():
            continue
        has_spoken_text = True
        cleaned = clean_agent_speech(clean_speech(text), state_dict)
        if cleaned != text:
            part.text = cleaned
            changed = True

    if not has_spoken_text:
        handoff_msg = enforce_handover_utterance("", state_dict).strip()
        if handoff_msg and isinstance(parts, list):
            cleaned_msg = clean_agent_speech(clean_speech(handoff_msg), state_dict)
            if parts and getattr(parts[0], "text", None) in (None, "") and not getattr(parts[0], "function_call", None):
                parts[0].text = cleaned_msg
            else:
                parts.insert(0, SimpleNamespace(text=cleaned_msg))
            changed = True

    return llm_response if changed else None


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.speech import clean_agent_speech, clean_speech, enforce_handover_utterance
from datetime import datetime, timedelta, timezone
from typing import Any
import re

_LAST4_CONTEXT_RE = re.compile(  # pragma: no cover
    r"((?:ending\s+in|terminant\s+par|termina\s+en|number\s+is|num[eé]ro\s+est|n[uú]mero\s+es)\s+)(\d{4})\b",
    re.IGNORECASE,
)

NUMBER_RUN_RE = re.compile(r"\(?\d+\)?(?:[-.]\(?\d+\)?|\s\(?\d{3,}\)?)*")  # pragma: no cover

SPEAKABLE_NUMBERS: frozenset[str] = frozenset()  # pragma: no cover

def mask_long_numbers(text: str, min_digits: int = 9) -> str:  # pragma: no cover
    """Replace every number of `min_digits` or more digits by its last 4 digits."""

    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < min_digits or digits in SPEAKABLE_NUMBERS:
            return match.group(0)
        return digits[-4:]

    return NUMBER_RUN_RE.sub(_mask, text)

MARKDOWN_RE = re.compile(r"\*+|`+|^#+[ \t]*", re.MULTILINE)  # pragma: no cover

def strip_markdown(text: str) -> str:  # pragma: no cover
    """Drop the markdown symbols a voice would read out: asterisks, backticks, headings."""
    return MARKDOWN_RE.sub("", text)

def clean_speech(text: str) -> str:  # pragma: no cover
    """Everything the speech_hygiene callback does to one piece of reply text."""
    return mask_long_numbers(strip_markdown(text))

def clean_agent_speech(  # pragma: no cover
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Clean markdown and long numbers, and prefer caller_provided_phone_last4 when present."""
    cleaned = clean_speech(text)
    if not isinstance(session_params, dict):
        return cleaned
    caller_last4 = str(session_params.get("caller_provided_phone_last4") or "").strip()
    profile_last4 = str(session_params.get("phone_last4") or "").strip()
    card_last4 = str(session_params.get("card_last4") or "").strip()
    if len(caller_last4) == 4 and caller_last4.isdigit():
        if (
            len(profile_last4) == 4
            and profile_last4 != caller_last4
            and profile_last4 != card_last4
            and profile_last4 in cleaned
        ):
            cleaned = re.sub(rf"\b{re.escape(profile_last4)}\b", caller_last4, cleaned)

        def _replace_non_card_last4(m: re.Match[str]) -> str:
            prefix = cleaned[max(0, m.start() - 35) : m.start()].lower()
            if any(
                w in prefix
                for w in ("card", "carte", "tarjeta", "visa", "mastercard", "amex", "crédit", "credit", "débit", "debit")
            ):
                return f"{m.group(1)}{card_last4}" if (len(card_last4) == 4 and card_last4.isdigit()) else m.group(0)
            if len(card_last4) == 4 and m.group(2) == card_last4:
                return m.group(0)
            return f"{m.group(1)}{caller_last4}"

        cleaned = _LAST4_CONTEXT_RE.sub(_replace_non_card_last4, cleaned)
    return cleaned

def enforce_handover_utterance(  # pragma: no cover
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Fill an empty handover turn with handoff_message; leave spoken text alone.

    After handover_to_person ran (handover_complete is True), a reply with no
    spoken text gets the localized handoff_message. Text the model did speak is
    returned unchanged, so a step-specific or PRD-exact transfer line survives.
    """
    if (text or "").strip():
        return text
    if not isinstance(session_params, dict) or not session_params.get("handover_complete"):
        return text
    handoff_msg = str(session_params.get("handoff_message") or "").strip()
    return handoff_msg or text
# --- END GENERATED SHARED BUNDLE ---
