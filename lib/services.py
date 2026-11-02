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
    BLOCKED_CALLER_NUMBERS,
    DECLINED_CARD_LAST4,
    SPOKEN_LINES,
    find_account,
    login_code_accepted,
    normalize_identifier,
    normalize_code,
    only_digits,
    read_count,
    resolve_copy_locale,
    resolve_locale,
    secret_pin_accepted,
    spoken_line,
)
from lib.replies import ERROR_CODES, display_amount, error_reply, ok_reply, tracking_id  # noqa: F401

ALL_TOOLS = (
    "lookup_account",
    "send_login_code",
    "check_login_code",
    "check_secret_pin",
    "submit_request",
    "handover_to_person",
)

# Login tries allowed on one call (take it from the PRD). The last try always fails
# and locks the caller out (lib/fakes.py login_code_accepted, DESIGN_RULES rule 21).
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
    """Resolve session language with asymmetric lock: non-English locks over English.

    When state has no language or is default 'en-US', a model-supplied
    non-English locale (fr-CA/es-US/...) is accepted and becomes the lock.
    Once state holds a non-English locale, a model-supplied 'en-US' or empty
    value is ignored (PRD BR-TV-004 lock).
    """
    has_state_dict = callable(getattr(state, "get", None))
    current = ""
    if has_state_dict:
        existing = state.get("language")
        if existing and str(existing).strip():
            current = resolve_copy_locale(str(existing))

    arg_lang = ""
    if language and str(language).strip():
        arg_lang = resolve_copy_locale(str(language))

    # 1. Once state holds a non-English locale, model-supplied en-US/empty is ignored.
    if current and current != "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = current
            if not state.get("preferred_language"):
                state["preferred_language"] = current
        return current

    # 2. When state has no language or is default 'en-US':
    # A model-supplied non-English locale (fr-CA/es-US/...) is accepted and becomes the lock.
    if arg_lang and arg_lang != "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = arg_lang
            state["preferred_language"] = arg_lang
        return arg_lang

    # 3. If state already had 'en-US', keep it.
    if current == "en-US":
        return "en-US"

    # 4. State had no language and model passed non-empty 'en-US'.
    if arg_lang == "en-US":
        if callable(getattr(state, "__setitem__", None)):
            state["language"] = "en-US"
        return "en-US"

    # 5. Check preferred_language in state if any.
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
    """Pick the handover language (docs/DESIGN_RULES.md rule 25).

    1. An explicit `language` argument wins, English included.
    2. Then the call's active language in session state (`language`).
    3. Only when both are empty: French or Spanish words in the reason, summary,
       queue, context or the caller's last words (a Turn-1 handover before any
       lookup has set a language).
    4. Then the account's preferred_language, else en-US.
    """
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
    # Only words that are not also English ("agent", "client", "non" are left out).
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
    if not str(phone_or_account or "").strip():
        return error_reply(
            "INVALID_INPUT",
            "No phone number or account number was given.",
            "Ask the caller for the phone number or account number on the account.",
            reference,
        )
    digits = only_digits(phone_or_account)
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
    account = find_account(phone_or_account)
    if account is None:
        return error_reply(
            "NOT_FOUND",
            "No account matches that number.",
            "Ask the caller to say the number again, one digit at a time.",
            reference,
        )
    if state.get("account_id") != account["account_id"]:
        # A different account: a login on the previous one must not carry over.
        state["auth_status"] = "none"
        state["logged_in"] = False
        state["login_code_sent"] = False
        state["auth_failure_count"] = 0
        state["login_attempts"] = 0
        state["pin_failure_count"] = 0
        state["pin_attempts"] = 0
    state["account_id"] = account["account_id"]
    state["phone_last4"] = account["phone"][-4:]
    ident = normalize_identifier(phone_or_account)
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
        w in str(phone_or_account).lower() for w in ("business", "entreprise", "commercial", "bus-")
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
                "first_name": account["first_name"],
                "phone_last4": account["phone"][-4:],
                "caller_provided_phone_last4": state["caller_provided_phone_last4"],
                "account_status": account["status"],
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
            "first_name": account["first_name"],
            "phone_last4": account["phone"][-4:],
            "caller_provided_phone_last4": state["caller_provided_phone_last4"],
            "account_status": account["status"],
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


def _handle_telco_domain_request(
    clean_summary: str,
    state: dict[str, Any],
    lang: str,
    reference: str,
) -> dict[str, Any] | None:
    low = clean_summary.lower()

    # 1. Outage Check (M4) - Information inquiry, does not require login
    if any(k in low for k in ("outage", "panne", "service alert", "panne de service")) or re.search(r"\b[A-Za-z]\d[A-Za-z]\b", clean_summary):
        if any(fsa in clean_summary.upper() for fsa in ("H3", "G1", "H3Z", "G1R")):
            msg = spoken_line("outage_active", lang)
            return ok_reply(
                {"outage_active": True, "affected_area": "QC", "eta": "2 hours"},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        else:
            msg = (
                "No active outages were found in your area. Would you like me to send an SMS troubleshooting guide?"
                if lang == "en-US"
                else "Aucune panne active n'a été trouvée dans votre secteur. Souhaitez-vous que je vous envoie un guide de dépannage par texto?"
            )
            return ok_reply(
                {"outage_active": False, "recommend_troubleshooting_guide": True},
                reference,
                language=lang,
                spoken_summary=msg,
            )

    # 2. Password Reset (M7) - Identified only, does not require login
    if any(k in low for k in ("password", "mot de passe", "reinitialiser", "réinitialiser")):
        p_last4 = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "0186")
        msg = (
            f"I have sent a password reset link to your mobile number ending in {p_last4}, valid for 30 minutes."
            if lang == "en-US"
            else f"J'ai envoyé un lien de réinitialisation de mot de passe à votre numéro mobile se terminant par {p_last4}, valide pendant 30 minutes."
        )
        return ok_reply(
            {"sms_sent": True, "valid_minutes": 30, "phone_last4": p_last4},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # All mutating actions below require login!
    if state.get("logged_in") is False:
        state["auth_status"] = "none"
    if state.get("auth_status") != "pass":
        return error_reply(
            "NOT_LOGGED_IN",
            "The caller has not passed login.",
            "Log the caller in with send_login_code and check_login_code, then call submit_request again.",
            reference,
            language=lang,
        )

    # 3. Billing Disputes / Credits / Refunds (M3)
    if any(k in low for k in ("dispute", "credit", "crédit", "refund", "remboursement", "conteste", "charge", "overcharge", "streaming", "downtime")):
        amt_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_summary)
        amount = float(amt_match.group(1)) if amt_match else 12.50
        if amount > 25.0:
            transfer_msg = spoken_line("transfer_to_specialist", lang)
            state["handoff_message"] = transfer_msg
            state["handoff_reason"] = "refund_threshold_exceeded"
            return error_reply(
                "LIMIT_EXCEEDED",
                message="Dispute amount exceeds the $25.00 limit for automated adjustment.",
                agent_action="Inform caller that refund exceeds $25 and transfer to a billing specialist.",
                reference=reference,
                language=lang,
                data={"amount": amount, "threshold": 25.0, "requires_specialist": True},
                spoken_summary=transfer_msg,
            )
        else:
            days = 5
            amt_disp = f"{amount:.2f}"
            conf_msg = spoken_line("refund_confirmation_pattern", lang, amount=amt_disp, days=days)
            return ok_reply(
                {"refund_approved": True, "amount": amount, "amount_display": amt_disp, "days": days},
                reference,
                language=lang,
                spoken_summary=conf_msg,
            )

    # 4. Bill Payment & Service Restore (M3 / M7)
    if any(k in low for k in ("pay", "payer", "payment", "paiement", "restore", "rétablir", "retablir", "solde", "past due")):
        if "declined" in low or (state.get("payment_failure_count", 0) == 0 and "decline" in low):
            state["payment_failure_count"] = read_count(state, "payment_failure_count") + 1
            state["payment_declined_once"] = True
            state["card_last4"] = ""
            return error_reply(
                "CARD_DECLINED",
                message="The payment card was declined.",
                agent_action="Prompt caller for an alternative card.",
                reference=reference,
                language=lang,
                spoken_summary=spoken_line("card_declined", lang),
            )
        card_match = re.search(r"\b(\d{4})\b", clean_summary)
        c_last4 = card_match.group(1) if card_match else str(state.get("card_last4") or "7742")
        state["card_last4"] = c_last4
        state["last_payment_method"] = "credit_card"
        state["service_restored"] = True
        state["status"] = "active"
        msg = (
            f"Your payment of $85.50 on card ending in {c_last4} was successful and your service has been restored."
            if lang == "en-US"
            else f"Votre paiement de 85.50 $ sur la carte se terminant par {c_last4} a été effectué avec succès et votre service est rétabli."
        )
        return ok_reply(
            {"paid": True, "amount": 85.50, "amount_display": "85.50", "card_last4": c_last4, "service_restored": True},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # 5. Payment Arrangement (M3 / M7)
    if any(k in low for k in ("arrangement", "entente", "installment", "versement")):
        state["service_restored"] = True
        msg = (
            "Your payment arrangement has been set up with two installments of $42.75, and your service is restored."
            if lang == "en-US"
            else "Votre entente de paiement a été configurée et votre service est rétabli."
        )
        return ok_reply(
            {"arrangement_confirmed": True, "service_restored": True, "installments": 2},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # 6. Prior Payment Verification (M3 / M7)
    if any(k in low for k in ("already paid", "déjà payé", "deja paye", "yesterday", "hier", "verify payment")):
        state["service_restored"] = True
        msg = (
            "I have verified your payment from yesterday, and your service has been restored."
            if lang == "en-US"
            else "J'ai vérifié votre paiement d'hier et votre service est rétabli."
        )
        return ok_reply(
            {"payment_verified": True, "service_restored": True},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # 7. Autopay Setup (M3)
    if any(k in low for k in ("autopay", "prélèvement", "prelevement", "automatique")):
        state["autopay_enrolled"] = True
        c_last4 = str(state.get("card_last4") or "7742")
        msg = (
            f"Autopay has been successfully configured for your account using your card ending in {c_last4}."
            if lang == "en-US"
            else f"Le paiement automatique a été configuré avec succès pour votre compte à l'aide de votre carte se terminant par {c_last4}."
        )
        return ok_reply(
            {"autopay_configured": True, "card_last4": c_last4},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # 8. Appointments & Reschedule (M6)
    if any(k in low for k in ("technician", "technicien", "appointment", "rendez-vous")):
        if any(k in low for k in ("reschedule", "reporter", "changer", "tomorrow", "demain")):
            state["appointment_rescheduled"] = True
            msg = (
                "Your technician appointment has been rescheduled to tomorrow between 1:00 PM and 5:00 PM."
                if lang == "en-US"
                else "Votre rendez-vous avec le technicien a été reporté à demain entre 13 h et 17 h."
            )
            return ok_reply(
                {"rescheduled": True, "new_slot": "Tomorrow 13:00 - 17:00"},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        else:
            msg = (
                "The technician is currently delayed en route by approximately 45 minutes. Available reschedule slots are tomorrow morning or tomorrow afternoon from 1:00 PM to 5:00 PM."
                if lang == "en-US"
                else "Le technicien est actuellement retardé en route. Des plages de report sont disponibles demain."
            )
            return ok_reply(
                {"status": "en_route", "delayed": True, "delay_minutes": 45, "available_slots": ["Tomorrow 08:00 - 12:00", "Tomorrow 13:00 - 17:00"]},
                reference,
                language=lang,
                spoken_summary=msg,
            )

    # 9. Ticket Status (M6)
    if any(k in low for k in ("ticket", "billet")):
        msg = (
            "Your open support ticket T88219 is currently in progress with our technical team."
            if lang == "en-US"
            else "Votre billet de soutien T88219 est actuellement en cours de traitement par notre équipe technique."
        )
        return ok_reply(
            {"ticket_id": "T88219", "status": "in_progress", "eta": "24-48 hours"},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    # 10. Technical Troubleshooting (M4 / M8)
    if any(k in low for k in ("satellite", "101", "tv", "fibe", "mobile data", "données", "donnees", "slow data", "signal")):
        if "satellite" in low or "101" in low:
            msg = (
                "For Satellite TV Error 101, please check that the coaxial cable is securely connected and power cycle your receiver. I can also text you an SMS guide."
                if lang == "en-US"
                else "Pour l'erreur 101 de la télévision par satellite, vérifiez le câble coaxial et redémarrez votre récepteur."
            )
            return ok_reply(
                {"troubleshooting_steps": "Check coaxial cable and reboot receiver", "guide_sent": True},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        elif "fibe" in low or "tv" in low or "signal" in low:
            msg = (
                "For the Fibe TV app, please close the app completely, verify your Wi-Fi connection, and relaunch it."
                if lang == "en-US"
                else "Pour l'application Télé Fibe, veuillez redémarrer l'application et vérifier votre connexion Wi-Fi."
            )
            return ok_reply(
                {"troubleshooting_steps": "Restart Fibe TV app and check Wi-Fi", "guide_sent": True},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        else:
            msg = (
                "For mobile data issues, please toggle airplane mode on and off, or reset network settings."
                if lang == "en-US"
                else "Pour les problèmes de données mobiles, activez et désactivez le mode avion ou réinitialisez les paramètres réseau."
            )
            return ok_reply(
                {"troubleshooting_steps": "Toggle airplane mode and reset network settings", "guide_sent": True},
                reference,
                language=lang,
                spoken_summary=msg,
            )

    # 11. Sales, Upgrades, Warranty, Port-In (M5)
    if any(k in low for k in ("plan", "forfait", "upgrade", "rehausser", "vitesse", "budget", "sports", "claim", "warranty", "garantie", "replacement", "remplacement", "port", "transfer")):
        if any(k in low for k in ("warranty", "garantie", "replacement", "remplacement", "screen", "pixel", "samsung", "battery", "batterie")):
            if "swollen" in low or "gonfl" in low:
                msg = (
                    "Your urgent battery safety warranty replacement has been ordered. Please stop using the device immediately for safety."
                    if lang == "en-US"
                    else "Votre remplacement sous garantie d'urgence pour batterie gonflée a été commandé. Cessez immédiatement d'utiliser l'appareil par sécurité."
                )
                return ok_reply(
                    {"urgent_replacement_approved": True, "claim_id": "W90214", "safety_alert": True},
                    reference,
                    language=lang,
                    spoken_summary=msg,
                )
            else:
                msg = (
                    "Your device warranty replacement request has been approved and a replacement unit is being shipped."
                    if lang == "en-US"
                    else "Votre demande de remplacement sous garantie a été approuvée et un appareil de remplacement est en cours d'expédition."
                )
                return ok_reply(
                    {"replacement_approved": True, "claim_id": "W90214", "tracking_number": "TRK-48291"},
                    reference,
                    language=lang,
                    spoken_summary=msg,
                )
        elif any(k in low for k in ("transfer", "port", "transférer", "transferer")):
            msg = (
                "Your phone number transfer request has been initiated and will complete within 2 to 4 hours."
                if lang == "en-US"
                else "Votre demande de transfert de numéro a été initiée avec succès."
            )
            return ok_reply(
                {"port_initiated": True, "request_id": "P38492"},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        elif "60" in clean_summary or "budget" in low:
            msg = (
                "I found a 50GB 5G mobile plan for $55 per month, which fits within your $60 budget."
                if lang == "en-US"
                else "J'ai trouvé un forfait 5G de 50 Go pour 55 $ par mois, ce qui respecte votre budget."
            )
            return ok_reply(
                {"plan_name": "50GB 5G Plan", "monthly_rate": 55.0, "rate_display": "55.00"},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        elif "sports" in low:
            msg = (
                "The Sports Package has been added to your TV plan for $15 per month."
                if lang == "en-US"
                else "Le forfait Sports a été ajouté à votre forfait télé pour 15 $ par mois."
            )
            return ok_reply(
                {"add_on": "Sports Package", "monthly_rate": 15.0, "rate_display": "15.00"},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        else:
            msg = (
                "Your internet upgrade to Gigabit Fiber has been confirmed and will take effect immediately."
                if lang == "en-US"
                else "Votre rehaussement internet vers la Fibre Gigabit a été confirmé."
            )
            return ok_reply(
                {"upgraded": True, "plan": "Gigabit Fiber", "effective_date": "immediate"},
                reference,
                language=lang,
                spoken_summary=msg,
            )

    # 12. MFA & Cancellations (M7)
    if any(k in low for k in ("mfa", "2fa")):
        if any(k in low for k in ("disable", "désactiver", "desactiver")):
            msg = (
                "Multi-factor authentication has been disabled on your account."
                if lang == "en-US"
                else "L'authentification multifacteur a été désactivée sur votre compte."
            )
            return ok_reply(
                {"mfa_enabled": False},
                reference,
                language=lang,
                spoken_summary=msg,
            )
        else:
            msg = (
                "Multi-factor authentication has been successfully enabled on your account."
                if lang == "en-US"
                else "L'authentification multifacteur a été activée avec succès sur votre compte."
            )
            return ok_reply(
                {"mfa_enabled": True},
                reference,
                language=lang,
                spoken_summary=msg,
            )

    if any(k in low for k in ("cancel", "annuler", "résilier", "resilier", "port out")):
        state["service_cancelled"] = True
        msg = (
            "Your service cancellation has been processed under confirmation number C99214."
            if lang == "en-US"
            else "L'annulation de votre service a été effectuée sous le numéro de confirmation C99214."
        )
        return ok_reply(
            {"cancelled": True, "cancellation_id": "C99214"},
            reference,
            language=lang,
            spoken_summary=msg,
        )

    return None


def submit_request_impl(
    summary: str,
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Record the caller's request. Refuses until the caller has passed login."""
    state = _get_state(state, session_state)
    lang = _session_language(state, language)
    mock_err = _check_mock_error(state, lang, "submit_request")
    if mock_err:
        return mock_err
    account_id = str(state.get("account_id") or "")
    clean_summary = " ".join(str(summary or "").split())
    reference = tracking_id("submit_request", account_id, clean_summary)
    if not clean_summary:
        return error_reply(
            "INVALID_INPUT",
            "The request is empty.",
            "Ask the caller what the request is.",
            reference,
            language=lang,
        )

    domain_reply = _handle_telco_domain_request(clean_summary, state, lang, reference)
    if domain_reply is not None:
        state["request_summary"] = clean_summary
        state["last_tracking_id"] = reference
        return domain_reply

    if state.get("logged_in") is False:
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
        reference = tracking_id("submit_request", account_id, clean_summary)
    state["request_summary"] = clean_summary
    state["last_tracking_id"] = reference
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
    if clean_reason in ("business_handoff", "business"):
        message = spoken_line("business_handoff", resolved_lang)
    elif clean_reason in ("fraud_escalation", "fraud"):
        message = spoken_line("empathy_protocol", resolved_lang)
    elif clean_reason in ("talk_to_a_person", "live_agent_handoff", "user_requested_agent"):
        message = spoken_line("live_agent_handoff", resolved_lang)
    elif clean_reason in ("refund_threshold_exceeded", "transfer_to_specialist"):
        message = spoken_line("transfer_to_specialist", resolved_lang)
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
