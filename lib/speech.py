"""Speech hygiene for every spoken reply: no markdown symbols, no full long numbers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from lib.fakes import spoken_line

# Numbers the PRD wants said in full, such as a support line. Every other
# number with 9 or more digits is cut to its last 4 digits.
SPEAKABLE_NUMBERS: frozenset[str] = frozenset()

# Digit groups joined by "-" or ".", or by a space when the next group has 3+
# digits. Phone, card and account numbers match in full; a date and time such
# as "2026-10-08 14:30" stops at 8 digits.
NUMBER_RUN_RE = re.compile(r"\(?\d+\)?(?:[-.]\(?\d+\)?|\s\(?\d{3,}\)?)*")
MARKDOWN_RE = re.compile(r"\*+|`+|^#+[ \t]*", re.MULTILINE)
_LAST4_CONTEXT_RE = re.compile(
    r"((?:ending\s+in|terminant\s+par|termina\s+en|number\s+is|num[eé]ro\s+est|n[uú]mero\s+es)\s+)(\d{4})\b",
    re.IGNORECASE,
)


def mask_long_numbers(text: str, min_digits: int = 9) -> str:
    """Replace every number of `min_digits` or more digits by its last 4 digits."""

    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < min_digits or digits in SPEAKABLE_NUMBERS:
            return match.group(0)
        return digits[-4:]

    return NUMBER_RUN_RE.sub(_mask, text)


def strip_markdown(text: str) -> str:
    """Drop the markdown symbols a voice would read out: asterisks, backticks, headings."""
    return MARKDOWN_RE.sub("", text)


def clean_speech(text: str) -> str:
    """Everything the speech_hygiene callback does to one piece of reply text."""
    return mask_long_numbers(strip_markdown(text))


def enforce_outage_utterance(
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Ensure active outage announcements speak all three sentences verbatim."""
    clean_text = (text or "").strip()
    state_dict = session_params if isinstance(session_params, dict) else {}
    pending_announce = bool(state_dict.get("outage_announce_pending"))
    if pending_announce:
        state_dict["outage_announce_pending"] = False

    if not clean_text:
        if pending_announce:
            lang = str(state_dict.get("language") or "")
            return spoken_line("outage_active", "fr-CA" if lang.startswith("fr") else "en-US")
        return text

    low = clean_text.lower()
    # If the text explicitly says there is no outage, NEVER overwrite
    if any(neg in low for neg in (
        "no active outage", "no outage", "not seeing", "there is no outage",
        "isn't an outage", "is not an outage", "pas de panne", "aucune panne",
        "aucun incident", "n'y a pas de panne", "pas d'interruption", "fonctionne normalement"
    )):
        return text

    # adv_iter12_1: Do not overwrite if utterance contains credit amounts or adjustments
    if any(k in low for k in ("$", "credit", "crédit", "adjustment", "ajustement", "sub-", "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9")):
        return text

    # Do not overwrite a dedicated SMS registration confirmation turn
    if any(k in low for k in ("i've registered", "j'ai inscrit", "j'ai bien noté", "registered text", "registered your number")):
        return text

    is_en_outage = (
        pending_announce
        or "active outage in your area" in low
        or "there's an active outage" in low
        or "there is an active outage" in low
        or ("active outage" in low and "area" in low)
    )
    is_fr_outage = (
        (pending_announce and str(state_dict.get("language", "")).startswith("fr"))
        or "panne active dans votre secteur" in low
        or ("panne active" in low and "secteur" in low)
    )
    if not (is_en_outage or is_fr_outage):
        return text

    lang = str(state_dict.get("language") or "")
    if is_fr_outage or lang.startswith("fr"):
        full_line = spoken_line("outage_active", "fr-CA")
        has_s1 = "panne active" in low or "panne" in low
        has_s2 = "travaillons" in low
        has_s3 = "texto lorsque" in low or "sera rétabli" in low or "sera retabli" in low
        if not (has_s1 and has_s2 and has_s3):
            return full_line
    else:
        full_line = spoken_line("outage_active", "en-US")
        has_s1 = "active outage" in low or "outage in your area" in low
        has_s2 = "working on it" in low
        has_s3 = "text you when" in low or "when it's restored" in low or "when it is restored" in low
        if not (has_s1 and has_s2 and has_s3):
            return full_line

    return text


def clean_agent_speech(
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Clean markdown and long numbers, and prefer caller_provided_phone_last4 when present."""
    cleaned = clean_speech(text)
    cleaned = enforce_outage_utterance(cleaned, session_params)
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


def enforce_handover_utterance(
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Ensure handover turns contain required disclosures; fill empty replies.

    After handover_to_person ran (or during an over-threshold dispute escalation),
    an empty reply receives the localized handoff_message. If the model spoke a
    partial reply missing the required explanation sentence on an over-threshold
    dispute, prepend the explanation sentence to ensure both sentences are spoken.
    """
    clean_text = (text or "").strip()
    if not isinstance(session_params, dict):
        return text

    is_threshold = bool(session_params.get("dispute_limit_exceeded")) or (
        str(session_params.get("handoff_reason") or "") in ("refund_threshold_exceeded", "dispute_limit_exceeded")
    )
    is_handover = bool(
        session_params.get("handover_complete")
        or is_threshold
    )
    if not is_handover:
        return text

    lang = str(session_params.get("language") or "")
    explanation_sent = (
        "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste."
        if lang.startswith("fr")
        else "Disputes exceeding the automated limit require review by a specialist."
    )
    transfer_sent = spoken_line("transfer_to_specialist", lang)

    if is_threshold:
        if not clean_text:
            return f"{explanation_sent} {transfer_sent}"

        low = clean_text.lower()
        has_explanation = (
            "exceeding the automated limit" in low
            or "dépassant la limite automatisée" in low
            or "depassant la limite automatisee" in low
            or any(w in low for w in ("exceed", "limit", "dépasse", "depasse", "maximum", "review", "specialized team", "équipe spécialisée", "equipe specialisee"))
        )
        has_spec = any(w in low for w in ("billing specialist", "specialist now", "spécialiste de la facturation", "specialiste de la facturation", "spécialiste maintenant", "specialiste maintenant"))
        has_generic = any(w in low for w in ("representative", "représentant", "representant", "customer service", "service à la clientèle", "service a la clientele"))
        has_transfer_verb = any(w in low for w in ("transfer", "transfèr", "transfér", "connect"))
        has_transfer = (has_spec or has_transfer_verb) and not (has_generic and not has_spec)

        if not has_explanation and not has_transfer:
            return f"{explanation_sent} {transfer_sent}"
        if not has_explanation and has_transfer:
            return f"{explanation_sent} {clean_text}"
        if has_explanation and not has_transfer:
            clean_text = re.sub(
                r"(?:(?:i (?:will|shall|can|must|'m|am)?\s*(?:transferring|transfer|connect) you (?:to|with) (?:a |an )?(?:customer service |live )?representative(?: now| right away| immediately| shortly)?\.?)|"
                r"(?:je vous (?:transf[eéè]re|transf[eéè]rerai?|mets en contact avec)\s*(?:[àa]\s+)?un repr[eé]sentant(?: maintenant| imm[eé]diatement| tout de suite)?\.?))",
                "",
                clean_text,
                flags=re.IGNORECASE,
            ).strip()
            clean_text = f"{clean_text} {transfer_sent}".strip()
            return clean_text
        return clean_text

    handoff_msg = str(session_params.get("handoff_message") or "").strip()
    if not clean_text:
        return handoff_msg or text

    return text


def resolve_handover_fallback(
    reason: str = "",
    language: str = "",
    session_params: dict[str, Any] | None = None,
) -> str:
    """Return localized spoken transfer sentence for an empty handover turn."""
    state_dict = session_params if isinstance(session_params, dict) else {}
    lang = language or str(state_dict.get("language") or "en-US")
    clean_r = str(reason or state_dict.get("handoff_reason") or "").strip().lower()
    if clean_r in ("business_handoff", "business", "business_account"):
        return spoken_line("business_handoff", lang)
    if clean_r in ("fraud_escalation", "fraud"):
        return spoken_line("empathy_protocol", lang)
    if clean_r in ("refund_threshold_exceeded", "transfer_to_specialist"):
        return spoken_line("transfer_to_specialist", lang)
    if clean_r in ("auth_failure_handoff", "auth_failure"):
        return spoken_line("auth_failure_handoff", lang)
    return spoken_line("live_agent_handoff", lang)

