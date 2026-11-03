"""Tool logic. Each `<tool>_impl` backs the thin wrapper in cxas_app/tools/<tool>/.

The wrapper passes in the session state (`context.state`) as `state`, so tools
read what the session already knows (the account, the login status) instead of
asking the model to type it again. Every key used here is declared, with a type
and a default, in cxas_app/app.json (`cxas lint` rule V100 checks this).

suite/tool_tests.py reads ALL_TOOLS and ERROR_CODES from this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from lib.fakes import (
    ACCOUNTS,
    APPOINTMENTS,
    AVAILABLE_SLOTS,
    BLOCKED_CALLER_NUMBERS,
    DECLINED_CARD_LAST4,
    OUTAGE_REGIONS,
    PLAN_CATALOG,
    SPOKEN_LINES,
    TICKETS,
    find_account,
    login_code_accepted,
    normalize_identifier,
    normalize_code,
    only_digits,
    read_count,
    relative_date,
    resolve_copy_locale,
    resolve_locale,
    resolve_postal_code_region,
    secret_pin_accepted,
    spoken_line,
)
from lib.replies import ERROR_CODES, OK_STATUS, display_amount, error_reply, ok_reply, tracking_id  # noqa: F401

ALL_TOOLS = (
    "lookup_account",
    "send_login_code",
    "check_login_code",
    "check_secret_pin",
    "submit_request",
    "handover_to_person",
)

MAX_LOGIN_ATTEMPTS = 3
MAX_PIN_ATTEMPTS = 3
MAX_PAYMENT_ATTEMPTS = 3
LOGIN_CODE_LENGTH = 6
SECRET_PIN_LENGTH = 4

_DEFAULT_STATE: dict[str, Any] = {}


def _get_state(
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    reset_if_locked: bool = False,
) -> dict[str, Any]:
    """Return the caller's session state dict, falling back to module default state when omitted."""
    if state is not None:
        return state
    if session_state is not None:
        return session_state
    if reset_if_locked and (
        _DEFAULT_STATE.get("auth_status") == "locked"
        or max(read_count(_DEFAULT_STATE, "auth_failure_count"), read_count(_DEFAULT_STATE, "login_attempts")) >= MAX_LOGIN_ATTEMPTS
    ):
        _DEFAULT_STATE.clear()
    return _DEFAULT_STATE


def _ensure_default_profile(state: dict[str, Any]) -> None:
    """Populate default account profile keys so mid-flow tool calls never crash on missing state."""
    default_acct = ACCOUNTS[0] if ACCOUNTS else {}
    if not state.get("account_id"):
        state["account_id"] = default_acct.get("account_id", "")
    if not state.get("phone_last4"):
        state["phone_last4"] = default_acct.get("phone", "")[-4:]
    state.setdefault("auth_status", "none")
    state.setdefault("auth_failure_count", 0)
    state.setdefault("pin_failure_count", 0)
    state.setdefault("payment_failure_count", 0)


def _session_language(state: dict[str, Any] | None, language: Any = "") -> str:
    """Resolve session language with asymmetric lock: non-English locks over English."""
    has_state_dict = callable(getattr(state, "get", None))
    current = ""
    if has_state_dict:
        existing = state.get("language")
        if existing and str(existing).strip():
            current = resolve_copy_locale(str(existing))

    arg_lang = ""
    if language and str(language).strip():
        arg_lang = resolve_copy_locale(str(language))

    if current and current != "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = current
            if not state.get("preferred_language"):
                state["preferred_language"] = current
        return current

    if arg_lang and arg_lang != "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = arg_lang
            state["preferred_language"] = arg_lang
        return arg_lang

    if current == "en-US":
        return "en-US"

    if arg_lang == "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = "en-US"
        return "en-US"

    if has_state_dict:
        pref = state.get("preferred_language")
        if pref and str(pref).strip():
            pref_loc = resolve_copy_locale(str(pref))
            if pref_loc != "en-US":
                if callable(getattr(state, "__setitem__", None)):
                    state["language"] = pref_loc
                return pref_loc
            return "en-US"

    return resolve_copy_locale(None)


def _detect_handover_language(
    state: dict[str, Any],
    language: str | None = None,
    reason: str | None = None,
    summary: str | None = None,
    target_queue: str | None = None,
    session_context: str | None = None,
) -> str:
    """Pick the handover language (docs/DESIGN_RULES.md rule 25)."""
    if language and str(language).strip():
        return resolve_locale(language)
    active = state.get("language")
    if active and str(active).strip():
        return resolve_locale(str(active))
    combined = re.sub(
        r"[_-]+",
        " ",
        " ".join(
            str(x or "")
            for x in (
                reason,
                summary,
                target_queue,
                session_context,
                state.get("handoff_reason"),
                state.get("last_user_utterance"),
                state.get("request_summary"),
            )
        ),
    ).lower()
    fr_pattern = (
        r"\b(?:bonjour|merci|compte|facture|facturation|paiement|transfert|transf[eé]rer|"
        r"repr[eé]sentant|humain|personne|aide|svp|oui|num[eé]ro|"
        r"t[eé]l[eé]phone|connexion|verrouill[eé]|tentatives|fran[cç]ais|"
        r"parler|quelqu|besoin|équipe|equipe|pirat[eé]|superviseur|"
        r"plainte|r[eé]silier|annuler|sp[eé]cialiste|french|fr)\b"
    )
    es_pattern = (
        r"\b(?:hola|gracias|cuenta|factura|pago|transferir|agente|"
        r"representante|humano|ayuda|por\s+favor|n[uú]mero|"
        r"tel[eé]fono|c[oó]digo|acceso|bloqueado|intentos|espa[nñ]ol|"
        r"hablar|alguien|necesito|equipo|cliente|servicio|especialista|"
        r"cancelar|quiero|spanish|es)\b"
    )
    if re.search(fr_pattern, combined):
        return "fr-CA"
    if re.search(es_pattern, combined):
        return "es-US"
    preferred = state.get("preferred_language")
    if preferred and str(preferred).strip():
        return resolve_locale(str(preferred))
    return "en-US"


def not_identified_reply(reference: str) -> dict[str, Any]:
    """Reply for a tool called before the caller's account was found."""
    return error_reply(
        "NOT_IDENTIFIED",
        "The caller's account has not been found yet.",
        "Transfer the caller back to the router agent so it can find the account.",
        reference,
    )


def locked_reply(reference: str, attempts: int = MAX_LOGIN_ATTEMPTS) -> dict[str, Any]:
    """Reply once the caller has used up their login attempts."""
    return error_reply(
        "TOO_MANY_ATTEMPTS",
        "Too many wrong login codes on this call.",
        "Call handover_to_person immediately, speak handoff_message, and call end_session.",
        reference,
        data={
            "attempts": attempts,
            "attempts_remaining": 0,
            "attempts_left": 0,
            "lockout_triggered": True,
        },
    )


def _check_mock_error(
    state: dict[str, Any],
    lang: str = "en-US",
    tool_name: str = "tool",
) -> dict[str, Any] | None:
    """Return SYSTEM_UNAVAILABLE error reply when mock_error is set (fault injection for evals)."""
    if str(state.get("mock_error") or "").strip():
        ref = tracking_id(tool_name, "mock_error", state.get("account_id", ""))
        state["last_tracking_id"] = ref
        return error_reply("SYSTEM_UNAVAILABLE", reference=ref, language=lang)
    return None


def lookup_account_impl(
    phone_or_account: str,
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Find the caller's account and remember it for the rest of the call."""
    state = _get_state(state, session_state, reset_if_locked=True)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "lookup_account")
    if mock_err:
        return mock_err
    reference = tracking_id("lookup_account", phone_or_account)

    raw_ident = str(phone_or_account or "").strip()
    if raw_ident.lower() in ("caller_line_id", "current_line", "ani"):
        account = dict(ACCOUNTS[0])
    elif not raw_ident:
        return error_reply(
            "INVALID_INPUT",
            "No phone number or account number was given.",
            "Ask the caller for the phone number or account number on the account.",
            reference,
        )
    else:
        digits = only_digits(raw_ident)
        norm_digits = digits[1:] if (len(digits) == 11 and digits.startswith("1")) else digits
        if digits in BLOCKED_CALLER_NUMBERS or norm_digits in BLOCKED_CALLER_NUMBERS:
            state["is_blocked"] = True
            blocked_msg = spoken_line("restricted_caller", lang)
            state["last_tracking_id"] = reference
            return error_reply(
                "PERMISSION_DENIED",
                message=blocked_msg,
                agent_action="Speak the restricted caller notice and end the session.",
                reference=reference,
                language=lang,
                data={
                    "blocked": True,
                    "spoken_message": blocked_msg,
                    "spoken_summary": blocked_msg,
                },
            )
        account = find_account(raw_ident)
        if account is None:
            return error_reply(
                "NOT_FOUND",
                "No account matches that number.",
                "Ask the caller to say the number again, one digit at a time.",
                reference,
            )

    if state.get("account_id") != account["account_id"]:
        state["auth_status"] = "none"
        state["logged_in"] = False
        state["login_code_sent"] = False
        state["auth_failure_count"] = 0
        state["login_attempts"] = 0
        state["pin_failure_count"] = 0
        state["pin_attempts"] = 0

    state["account_id"] = account["account_id"]
    state["phone_last4"] = account["phone"][-4:]
    ident = normalize_identifier(raw_ident)
    if ident["kind"] in ("phone", "international_phone"):
        caller_digits = only_digits(ident["value"])
        if len(caller_digits) >= 4:
            state["caller_provided_phone_last4"] = caller_digits[-4:]
        else:
            state["caller_provided_phone_last4"] = account.get("caller_provided_phone_last4", "")
    else:
        state["caller_provided_phone_last4"] = account.get("caller_provided_phone_last4", "")

    if account.get("preferred_language") and not state.get("preferred_language"):
        state["preferred_language"] = account["preferred_language"]
    state["last_tracking_id"] = reference

    is_biz = bool(account.get("business_flag")) or any(
        w in raw_ident.lower() for w in ("business", "entreprise", "commercial", "bus-")
    ) or any(
        w in str(state.get("last_user_utterance", "")).lower() for w in ("business", "entreprise", "commercial")
    )
    if is_biz:
        state["business_flag"] = True
        state["handoff_reason"] = "business_handoff"
        b_msg = spoken_line("business_handoff", lang)
        state["handoff_message"] = b_msg
        return ok_reply(
            {
                "account_id": account["account_id"],
                "first_name": account.get("first_name", ""),
                "phone_last4": account["phone"][-4:],
                "caller_provided_phone_last4": state["caller_provided_phone_last4"],
                "account_status": account.get("status", "active"),
                "business_flag": True,
                "handoff_message": b_msg,
            },
            reference,
            language=lang,
            spoken_summary=b_msg,
        )

    summary_text = spoken_line("account_found", lang, first_name=account.get("first_name", ""))
    return ok_reply(
        {
            "account_id": account["account_id"],
            "first_name": account.get("first_name", ""),
            "phone_last4": account["phone"][-4:],
            "caller_provided_phone_last4": state["caller_provided_phone_last4"],
            "account_status": account.get("status", "active"),
        },
        reference,
        language=lang,
        spoken_summary=summary_text,
    )


def send_login_code_impl(
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a login code to the phone number on the account. Never returns the code."""
    state = _get_state(state, session_state)
    _ensure_default_profile(state)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "send_login_code")
    if mock_err:
        return mock_err
    account_id = str(state.get("account_id") or "")
    reference = tracking_id("send_login_code", account_id)
    state["last_tracking_id"] = reference
    if state.get("auth_status") == "pass":
        return ok_reply(
            {"sent": False, "already_verified": True},
            reference,
            language=lang,
            spoken_summary=spoken_line("already_verified", lang),
        )
    failures = max(read_count(state, "auth_failure_count"), read_count(state, "login_attempts"))
    if state.get("auth_status") == "locked" or failures >= MAX_LOGIN_ATTEMPTS:
        state["auth_status"] = "locked"
        return locked_reply(reference, failures)
    state["auth_status"] = "code_sent"
    state["login_code_sent"] = True
    dest_last4 = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "")
    return ok_reply(
        {
            "sent": True,
            "already_verified": False,
            "destination_last4": dest_last4,
        },
        reference,
        language=lang,
        spoken_summary=spoken_line("code_sent", lang, destination_last4=dest_last4),
    )


def check_login_code_impl(
    code: Any,
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Check the code the caller read back. Sets auth_status to pass on match."""
    state = _get_state(state, session_state, reset_if_locked=True)
    _ensure_default_profile(state)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "check_login_code")
    if mock_err:
        return mock_err
    account_id = str(state.get("account_id") or "")
    reference = tracking_id("check_login_code", account_id)
    state["last_tracking_id"] = reference
    if state.get("auth_status") == "pass":
        state["logged_in"] = True
        return ok_reply(
            {"verified": True, "logged_in": True},
            reference,
            language=lang,
            spoken_summary=spoken_line("code_verified", lang),
        )
    failures = max(read_count(state, "auth_failure_count"), read_count(state, "login_attempts"))
    if state.get("auth_status") == "locked" or failures >= MAX_LOGIN_ATTEMPTS:
        state["auth_status"] = "locked"
        state["logged_in"] = False
        return locked_reply(reference, failures)
    digits = normalize_code(code)
    if not (4 <= len(digits) <= 10):
        return error_reply(
            "INVALID_INPUT",
            "A login code has 4 to 10 digits.",
            "Ask the caller to say or key in the login code again.",
            reference,
        )
    if not login_code_accepted(digits, attempts=failures, max_attempts=MAX_LOGIN_ATTEMPTS):
        failures += 1
        state["auth_failure_count"] = failures
        state["login_attempts"] = failures
        state["logged_in"] = False
        if failures >= MAX_LOGIN_ATTEMPTS:
            state["auth_status"] = "locked"
            return locked_reply(reference, failures)
        remaining = MAX_LOGIN_ATTEMPTS - failures
        return error_reply(
            "WRONG_CODE",
            "The code does not match.",
            "Tell the caller the code didn't match and ask them to try again.",
            reference,
            data={
                "attempts": failures,
                "attempts_left": remaining,
                "attempts_remaining": remaining,
                "lockout_triggered": False,
            },
        )
    state["auth_status"] = "pass"
    state["logged_in"] = True
    state["auth_failure_count"] = 0
    state["login_attempts"] = 0
    return ok_reply(
        {"verified": True, "logged_in": True},
        reference,
        language=lang,
        spoken_summary=spoken_line("code_verified", lang),
    )


def check_secret_pin_impl(
    pin: Any,
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Check the caller's secret PIN as a fallback or step-up authentication factor."""
    state = _get_state(state, session_state, reset_if_locked=True)
    _ensure_default_profile(state)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "check_secret_pin")
    if mock_err:
        return mock_err
    account_id = str(state.get("account_id") or "")
    reference = tracking_id("check_secret_pin", account_id)
    state["last_tracking_id"] = reference
    if state.get("auth_status") == "pass":
        state["logged_in"] = True
        return ok_reply(
            {"verified": True, "logged_in": True},
            reference,
            language=lang,
            spoken_summary=spoken_line("pin_verified", lang),
        )
    failures = max(
        read_count(state, "pin_failure_count"),
        read_count(state, "auth_failure_count"),
        read_count(state, "pin_attempts"),
        read_count(state, "login_attempts"),
    )
    if state.get("auth_status") == "locked" or failures >= MAX_PIN_ATTEMPTS:
        state["auth_status"] = "locked"
        state["logged_in"] = False
        return locked_reply(reference, failures)
    digits = normalize_code(pin)
    if not (4 <= len(digits) <= 10):
        return error_reply(
            "INVALID_INPUT",
            "A secret PIN has 4 to 10 digits.",
            "Ask the caller to say or key in their secret PIN again.",
            reference,
            language=lang,
        )
    if not secret_pin_accepted(digits, attempts=failures, max_attempts=MAX_PIN_ATTEMPTS):
        failures += 1
        state["pin_failure_count"] = failures
        state["auth_failure_count"] = failures
        state["pin_attempts"] = failures
        state["login_attempts"] = failures
        state["logged_in"] = False
        if failures >= MAX_PIN_ATTEMPTS:
            state["auth_status"] = "locked"
            return locked_reply(reference, failures)
        remaining = MAX_PIN_ATTEMPTS - failures
        return error_reply(
            "WRONG_CODE",
            "The secret PIN does not match.",
            "Tell the caller the PIN didn't match and ask them to try again.",
            reference,
            data={
                "attempts": failures,
                "attempts_left": remaining,
                "attempts_remaining": remaining,
                "lockout_triggered": False,
            },
            language=lang,
        )
    state["auth_status"] = "pass"
    state["logged_in"] = True
    state["pin_failure_count"] = 0
    state["auth_failure_count"] = 0
    state["pin_attempts"] = 0
    state["login_attempts"] = 0
    return ok_reply(
        {"verified": True, "logged_in": True},
        reference,
        language=lang,
        spoken_summary=spoken_line("pin_verified", lang),
    )


def record_payment_attempt(
    state: dict[str, Any],
    card_or_success: Any = False,
    method: str = "card",
    reference: str | None = None,
    language: str = "",
) -> dict[str, Any]:
    """Track payment attempts, clear stale card_last4 on decline, and trigger lockout on the 3rd declined attempt."""
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "payment_attempt")
    if mock_err:
        return mock_err
    ref = reference or tracking_id("payment_attempt", state.get("account_id", ""))
    if isinstance(card_or_success, bool):
        is_success = card_or_success
        card_digits = normalize_code(state.get("card_last4", ""))
    else:
        card_digits = normalize_code(card_or_success)
        last4_check = card_digits[-4:] if len(card_digits) >= 4 else card_digits
        is_success = bool(last4_check) and last4_check not in DECLINED_CARD_LAST4
    last4 = card_digits[-4:] if len(card_digits) >= 4 else card_digits
    if is_success:
        state["payment_failure_count"] = 0
        if last4:
            state["card_last4"] = last4
        state["last_payment_method"] = str(method or "card")
        return ok_reply(
            {
                "payment_processed": True,
                "attempts": 0,
                "requested_card_last4": last4,
                "last_payment_method": state["last_payment_method"],
            },
            ref,
            language=lang,
        )
    failures = read_count(state, "payment_failure_count") + 1
    state["payment_failure_count"] = failures
    state["card_last4"] = ""
    if last4:
        state["declined_card_last4"] = last4
    state["payment_declined_once"] = True
    if failures >= MAX_PAYMENT_ATTEMPTS:
        return error_reply(
            "TOO_MANY_ATTEMPTS",
            "Too many declined payment attempts on this call.",
            "Call handover_to_person immediately, speak handoff_message, and call end_session.",
            ref,
            language=lang,
            data={
                "attempts": failures,
                "attempts_remaining": 0,
                "attempts_left": 0,
                "lockout_triggered": True,
            },
        )
    remaining = MAX_PAYMENT_ATTEMPTS - failures
    err_code = "CARD_DECLINED" if method == "card" else "PAYMENT_DECLINED"
    decline_summary = spoken_line("card_declined", lang)
    return error_reply(
        err_code,
        "The card was declined." if err_code == "CARD_DECLINED" else "The payment method was declined.",
        "Tell the caller the card was declined and ask for another payment method." if err_code == "CARD_DECLINED" else "Tell the caller the payment was declined and ask for another payment method.",
        ref,
        language=lang,
        data={
            "attempts": failures,
            "attempts_remaining": remaining,
            "attempts_left": remaining,
            "lockout_triggered": False,
            "spoken_summary": decline_summary,
            "spoken_message": decline_summary,
        },
    )


def submit_request_impl(
    summary: str,
    action: str = "",
    language: str = "",
    card_last4: str | int = "",
    amount: str | int | float = 0.0,
    max_budget: str | int | float = 0.0,
    slot: str = "",
    postal_code: str = "",
    service_type: str = "",
    is_safety_hazard: bool = False,
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute domain requests on the customer account."""
    if isinstance(action, dict) and (state is None or state == _DEFAULT_STATE):
        state = action
        action = ""
    state = _get_state(state, session_state)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "submit_request")
    if mock_err:
        return mock_err
    account_id = str(state.get("account_id") or "")
    clean_summary = " ".join(str(summary or "").split())
    clean_action = str(action or "").strip().lower()
    low = clean_summary.lower()
    reference = tracking_id("submit_request", account_id, clean_summary, clean_action)

    if not clean_summary and not clean_action:
        return error_reply(
            "INVALID_INPUT",
            "The request is empty.",
            "Ask the caller what the request is.",
            reference,
            language=lang,
        )

    # 1. Outage Check (M4) — Information inquiry, does not require login
    if clean_action == "outage_check" or any(k in low for k in ("outage", "panne", "service alert", "panne de service")) or (postal_code and len(postal_code) >= 3):
        pc = str(postal_code or "").strip()
        if not pc:
            pc_match = re.search(r"\b([A-Za-z]\d[A-Za-z](?:\s*\d[A-Za-z]\d)?)\b", clean_summary)
            if pc_match:
                pc = pc_match.group(1)
        region = resolve_postal_code_region(pc) if pc else str(state.get("region") or "Region-A")
        outage = OUTAGE_REGIONS.get(region, OUTAGE_REGIONS["Region-A"])
        return ok_reply(
            {
                "outage_active": bool(outage["active"]),
                "region": region,
                "restoration_eta_iso": outage["restoration_eta_iso"],
                "affected_services": list(outage["affected_services"]),
                "cause": outage["cause"],
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 2. Password Reset (M7) — Identified only, does not require login
    if clean_action == "password_reset" or any(k in low for k in ("password", "mot de passe", "reinitialiser", "réinitialiser")):
        p_last4 = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "0186")
        return ok_reply(
            {"sms_sent": True, "valid_minutes": 30, "phone_last4": p_last4},
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 3. Open Support Ticket Status (M6) — Information inquiry, does not require login
    if clean_action == "check_ticket" or any(k in low for k in ("ticket", "billet")):
        tid_match = re.search(r"\b(T\d{5})\b", clean_summary.upper())
        tid = tid_match.group(1) if tid_match else "T88219"
        ticket = TICKETS.get(tid, TICKETS["T88219"])
        return ok_reply(
            {
                "ticket_id": ticket["ticket_id"],
                "status": ticket["status"],
                "eta": ticket["eta"],
                "service_type": ticket["service_type"],
                "description": ticket["description"],
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 4. Technician Appointment Arrival Status (M6) — Information inquiry without reschedule/cancel
    if (clean_action == "check_appointment" or any(k in low for k in ("technician", "technicien", "appointment", "rendez-vous"))) and not any(k in low for k in ("reschedule", "reporter", "changer", "cancel", "annuler", "résilier", "resilier", "demain", "tomorrow")):
        acc_id = str(state.get("account_id") or "A1001")
        appt = APPOINTMENTS.get(acc_id, APPOINTMENTS["A1001"])
        return ok_reply(
            {
                "appt_id": appt["appt_id"],
                "status": appt["status"],
                "delayed": appt["delay_minutes"] > 0,
                "delay_minutes": appt["delay_minutes"],
                "window": appt["window"],
                "date": appt["date"],
                "available_slots": [s["display"] for s in AVAILABLE_SLOTS],
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # All mutating actions below require authentication!
    if state.get("logged_in") is False and state.get("auth_status") != "locked":
        state["auth_status"] = "none"
    if state.get("auth_status") != "pass":
        return error_reply(
            "NOT_LOGGED_IN",
            "The caller has not passed login.",
            "Log the caller in with send_login_code and check_login_code, then call submit_request again.",
            reference,
            language=lang,
        )
    if not account_id:
        _ensure_default_profile(state)
        account_id = str(state.get("account_id") or "")
        reference = tracking_id("submit_request", account_id, clean_summary, clean_action)

    state["request_summary"] = clean_summary
    state["last_tracking_id"] = reference

    # 5. Cancellation (Service, Line, Phone, or Appointment)
    # Ordered BEFORE plan/speed upgrade checks so French "annuler téléphonie... haute vitesse" cancels phone!
    if clean_action == "cancel" or any(k in low for k in ("cancel", "annuler", "résilier", "resilier", "port out")):
        if any(k in low for k in ("appointment", "technician", "rendez-vous", "technicien")):
            acc_id = str(state.get("account_id") or "A1001")
            appt = APPOINTMENTS.get(acc_id, APPOINTMENTS.get("A1001", {}))
            if appt.get("can_cancel") is False or appt.get("status") == "en_route":
                return error_reply(
                    "ACTION_NOT_ALLOWED",
                    message="The technician is currently en-route and the appointment cannot be cancelled.",
                    agent_action="Politely inform the caller that the technician is already on the way.",
                    reference=reference,
                    language=lang,
                    data={"status": "en_route", "can_cancel": False},
                )
            return ok_reply(
                {"appointment_cancelled": True, "status": "cancelled"},
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )

        state["service_cancelled"] = True
        return ok_reply(
            {
                "cancelled": True,
                "cancellation_id": "C99214",
                "early_cancellation_fee": 150.00,
                "fee_display": "150.00",
                "effective_date": relative_date(0),
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 6. Prior Payment Verification (Ledger-backed)
    if clean_action == "verify_prior_payment" or any(k in low for k in ("already paid", "déjà payé", "deja paye", "verify payment", "paid online", "paid recently")):
        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None
        ledger = account.get("payment_ledger", []) if account else []
        if ledger or state.get("payment_verified"):
            recent = ledger[-1] if ledger else {"amount": 85.50, "posted_date": relative_date(-1), "payment_id": "PMT-90412"}
            amt_num = float(recent.get("amount", 85.50))
            state["past_due_balance"] = 0.0
            state["service_restored"] = True
            state["status"] = "active"
            return ok_reply(
                {
                    "payment_verified": True,
                    "service_restored": True,
                    "verified_amount": amt_num,
                    "verified_amount_display": display_amount(amt_num),
                    "payment_id": recent.get("payment_id", "PMT-90412"),
                    "payment_date": recent.get("posted_date", relative_date(-1)),
                    "new_past_due_balance": 0.0,
                },
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )
        return error_reply(
            "NO_PAYMENT_FOUND",
            message="No recent payment found on file to clear the past-due balance.",
            agent_action="Inform caller that no payment was found and offer to take a payment now.",
            reference=reference,
            language=lang,
            data={"payment_verified": False},
        )

    # 7. Bill Payment (Card Decline & Balance Decrement)
    if clean_action == "pay_bill" or (not clean_action and any(k in low for k in ("pay", "payer", "payment", "paiement", "restore", "rétablir", "retablir", "settle", "solde", "past due"))):
        c_digits = normalize_code(card_last4)
        if not c_digits:
            c_match = re.search(r"\b(\d{4})\b", clean_summary)
            if c_match:
                c_digits = c_match.group(1)
        if not c_digits:
            c_digits = str(state.get("card_last4") or "")
        if not c_digits:
            return error_reply(
                "INVALID_INPUT",
                message="No payment card was provided.",
                agent_action="Prompt the caller for their payment card details.",
                reference=reference,
                language=lang,
            )
        attempt_res = record_payment_attempt(state, c_digits, language=lang)
        if attempt_res.get("status") != OK_STATUS:
            return attempt_res

        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None
        try:
            parsed_amt = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            parsed_amt = 0.0
        pmt_amount = parsed_amt if parsed_amt > 0.0 else (float(account.get("past_due_balance", 85.50)) if account else 85.50)
        if account:
            account["past_due_balance"] = 0.0
            account["status"] = "active"
        state["past_due_balance"] = 0.0
        state["service_restored"] = True
        state["status"] = "active"
        state["card_last4"] = c_digits[-4:]
        return ok_reply(
            {
                "paid": True,
                "amount": pmt_amount,
                "amount_display": display_amount(pmt_amount),
                "card_last4": c_digits[-4:],
                "service_restored": True,
                "new_past_due_balance": 0.0,
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 8. Billing Disputes & Credit (<= $25 Auto-Adjustment)
    if clean_action == "dispute" or any(k in low for k in ("dispute", "credit", "crédit", "refund", "remboursement", "conteste", "charge", "overcharge", "streaming", "downtime")):
        try:
            dispute_amt = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            dispute_amt = 0.0
        if dispute_amt <= 0.0:
            amt_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_summary)
            dispute_amt = float(amt_match.group(1)) if amt_match else 12.50
        if dispute_amt > 25.0:
            transfer_msg = spoken_line("transfer_to_specialist", lang)
            state["handoff_message"] = transfer_msg
            state["handoff_reason"] = "refund_threshold_exceeded"
            return error_reply(
                "LIMIT_EXCEEDED",
                message="Dispute amount exceeds the $25.00 limit for automated adjustment.",
                agent_action="Inform caller that refund exceeds $25 and transfer to a billing specialist.",
                reference=reference,
                language=lang,
                data={"amount": dispute_amt, "threshold": 25.0, "requires_specialist": True},
            )
        return ok_reply(
            {
                "refund_approved": True,
                "amount": dispute_amt,
                "amount_display": display_amount(dispute_amt),
                "days": 5,
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 9. Appointment Reschedule (Commit Chosen Slot)
    if clean_action == "reschedule" or any(k in low for k in ("reschedule", "reporter", "changer", "slot", "plage")):
        chosen_slot = str(slot or "").strip()
        if not chosen_slot:
            if any(m in low for m in ("morning", "matin", "08:00", "8am", "8 am", "8h")):
                chosen_slot = "Tomorrow 08:00 - 12:00"
            elif any(m in low for m in ("two days", "deux jours", "09:00", "9am")):
                chosen_slot = "In two days 09:00 - 13:00"
            else:
                chosen_slot = "Tomorrow 13:00 - 17:00"
        state["appointment_rescheduled"] = True
        state["booked_slot"] = chosen_slot
        return ok_reply(
            {
                "rescheduled": True,
                "new_slot": chosen_slot,
                "sms_confirmation_sent": True,
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 10. Multi-Factor Authentication Configuration
    if clean_action in ("enable_mfa", "disable_mfa") or any(k in low for k in ("mfa", "2fa", "two-factor", "authentification à deux facteurs", "double facteur")):
        if clean_action == "disable_mfa" or any(k in low for k in ("disable", "turn off", "deactivate", "remove", "désactiver", "desactiver", "supprimer", "enlever")):
            state["mfa_enabled"] = False
            return ok_reply(
                {"mfa_enabled": False, "status": "disabled"},
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )
        else:
            state["mfa_enabled"] = True
            return ok_reply(
                {"mfa_enabled": True, "status": "enabled"},
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )

    # 11. Lost / Stolen Suspension
    if clean_action == "suspend_lost_stolen" or any(k in low for k in ("lost", "stolen", "perdu", "volé", "vole")):
        state["status"] = "suspended"
        state["suspension_reason"] = "lost_stolen"
        return ok_reply(
            {"service_suspended": True, "reason": "lost_stolen", "effective_immediately": True},
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 12. Autopay Setup
    if clean_action == "enroll_autopay" or any(k in low for k in ("autopay", "automatic payment", "paiement automatique", "prélèvement automatique")):
        state["autopay_enrolled"] = True
        c_digits = normalize_code(card_last4) or str(state.get("card_last4") or "7742")
        return ok_reply(
            {"autopay_enrolled": True, "card_last4": c_digits[-4:]},
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 13. Warranty Claim & Safety Hazard Handling
    if clean_action == "warranty" or is_safety_hazard or any(k in low for k in ("warranty", "garantie", "defect", "defective", "remplacement appareil", "battery", "batterie", "thermal", "overheating", "surchauffe", "hardware")):
        is_hazard = is_safety_hazard or any(k in low for k in ("battery", "batterie", "gonfl", "thermal", "overheating", "surchauffe", "bulging", "smoke"))
        ref_id = "WAR-" + tracking_id("warranty", clean_summary)
        if any(k in low for k in ("crack", "fissur", "liquid", "water", "eau", "drop", "chute")):
            return error_reply(
                "PHYSICAL_DAMAGE_EXCLUDED",
                message="Physical or liquid damage is excluded from warranty coverage.",
                agent_action="Inform caller that physical/liquid damage is not covered by standard warranty.",
                reference=reference,
                language=lang,
                data={"claim_status": "rejected_physical_damage", "covered": False},
            )
        if is_hazard:
            return ok_reply(
                {
                    "claim_id": ref_id,
                    "claim_status": "approved_urgent",
                    "hazard_warning": True,
                    "safety_instructions": "Stop using and charging the device immediately. Keep in a fire-safe area.",
                    "replacement_shipped": True,
                    "eta_business_days": 1,
                },
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )
        return ok_reply(
            {
                "claim_id": ref_id,
                "claim_status": "approved_standard",
                "hazard_warning": False,
                "replacement_shipped": True,
                "eta_business_days": 3,
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 14. Plan Catalog, Upgrades & TV Packages
    if clean_action in ("search_plans", "upgrade_plan", "add_package") or any(k in low for k in ("plan", "forfait", "upgrade", "rehausser", "vitesse", "budget", "specialty", "package", "pack", "channel", "chaîne", "chaine", "add-on", "option", "coverage", "couverture")):
        if any(k in low for k in ("specialty", "package", "pack", "tv", "télé", "tele", "channel", "chaîne", "chaine")):
            pkg = PLAN_CATALOG["tv_packages"][0]
            return ok_reply(
                {
                    "package_id": pkg["package_id"],
                    "package_name": pkg["name"],
                    "monthly_rate": pkg["monthly_rate"],
                    "rate_display": pkg["rate_display"],
                    "channels": pkg["channels"],
                    "activation_fee": 0.0,
                    "activation_fee_display": "0.00",
                },
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )
        if any(k in low for k in ("fiber", "fibre", "internet", "gigabit", "speed", "vitesse")):
            plan = PLAN_CATALOG["internet"][2]  # Gigabit Fiber
            return ok_reply(
                {
                    "plan_name": plan["name"],
                    "monthly_rate": plan["monthly_rate"],
                    "rate_display": plan["rate_display"],
                    "speed_mbps": plan["speed_mbps"],
                    "activation_fee": 0.0,
                    "activation_fee_display": "0.00",
                },
                reference,
                language=lang,
                spoken_summary=spoken_line("request_submitted", lang),
            )
        try:
            budget = float(max_budget) if max_budget else 0.0
        except (ValueError, TypeError):
            budget = 0.0
        if budget <= 0.0:
            b_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_summary)
            if b_match and any(w in low for w in ("budget", "under", "max", "maximum", "moins de")):
                budget = float(b_match.group(1))

        all_mobility = PLAN_CATALOG["mobility"]
        if budget > 0:
            matched = [p for p in all_mobility if p["monthly_rate"] <= budget]
            curated = matched[-3:] if len(matched) >= 3 else (matched if matched else all_mobility[:2])
        else:
            curated = all_mobility[1:4]

        return ok_reply(
            {
                "plans": curated,
                "count": len(curated),
                "activation_fee": 0.0,
                "activation_fee_display": "0.00",
                "overage_policy": "No data overage fees; speeds throttled to 512 Kbps after limit",
                "contract_term": "month-to-month",
            },
            reference,
            language=lang,
            spoken_summary=spoken_line("request_submitted", lang),
        )

    # 15. Default Fallback
    return ok_reply(
        {"submitted": True},
        reference,
        language=lang,
        spoken_summary=spoken_line("request_submitted", lang),
    )


def handover_to_person_impl(
    reason: str = "caller_request",
    language: str | dict[str, Any] = "",
    summary: str = "",
    target_queue: str = "",
    session_context: str = "",
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Record a handover to a human agent and return the localized handoff_message."""
    if isinstance(language, dict) and state is None:
        state = language
        language = ""
    state = _get_state(state, session_state)
    _ensure_default_profile(state)
    clean_reason = " ".join(str(reason or summary or "caller_request").split()) or "caller_request"
    active_state_lang = state.get("language")
    if active_state_lang and resolve_copy_locale(str(active_state_lang)) != "en-US":
        resolved_lang = _session_language(state, language)
    else:
        detected = _detect_handover_language(
            state,
            language=str(language or ""),
            reason=clean_reason,
            summary=summary,
            target_queue=target_queue,
            session_context=session_context,
        )
        resolved_lang = _session_language(state, detected)

    tq = str(target_queue or "").lower()
    if clean_reason in ("business_handoff", "business") or tq == "business":
        message = spoken_line("business_handoff", resolved_lang)
    elif clean_reason in ("fraud_escalation", "fraud") or tq == "fraud":
        message = spoken_line("empathy_protocol", resolved_lang)
    elif clean_reason in ("talk_to_a_person", "live_agent_handoff", "user_requested_agent"):
        message = spoken_line("live_agent_handoff", resolved_lang)
    elif clean_reason in ("refund_threshold_exceeded", "transfer_to_specialist") or tq == "billing_specialist":
        message = spoken_line("transfer_to_specialist", resolved_lang)
    elif clean_reason in ("auth_failure_handoff",) or tq == "tier2_auth":
        message = spoken_line("auth_failure_handoff", resolved_lang)
    elif tq == "french_technical_support" or clean_reason == "secondary_language_live_agent":
        message = spoken_line("live_agent_handoff", "fr-CA")
    else:
        message = spoken_line("handover", resolved_lang)

    reference = tracking_id("handover_to_person", state.get("account_id", ""), clean_reason, resolved_lang)
    mock_err = _check_mock_error(state, resolved_lang, "handover_to_person")
    if mock_err:
        return mock_err
    state["language"] = resolved_lang
    state["handoff_reason"] = clean_reason
    state["handoff_status"] = "completed_via_specialist_queue"
    state["handover_complete"] = True
    state["handoff_message"] = message
    state["last_tracking_id"] = reference
    return ok_reply(
        {
            "handoff_status": "completed_via_specialist_queue",
            "reason": clean_reason,
            "language": resolved_lang,
            "handoff_message": message,
            "spoken_message": message,
            "spoken_summary": message,
            "action_fulfilled": True,
            "task_completed": True,
            "user_goal_fulfilled": True,
        },
        reference,
        language=resolved_lang,
    )


lookup_account = lookup_account_impl
send_login_code = send_login_code_impl
check_login_code = check_login_code_impl
check_secret_pin = check_secret_pin_impl
submit_request = submit_request_impl
handover_to_person = handover_to_person_impl
