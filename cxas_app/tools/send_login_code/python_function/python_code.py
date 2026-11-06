from typing import Any



def send_login_code(
    language: str = "",
    destination_phone: str | int = "",
) -> dict[str, Any]:
    """Sends a login code to the phone number on the caller's account.

    Call this when a task tool returned error NOT_LOGGED_IN. It reads the
    account from the session, or sends to destination_phone if specified.
    Never returns the code.

    Args:
      language: BCP-47 language code (e.g. en-US, fr-CA, es-US).
      destination_phone: Optional alternate phone number or digits if caller specifies an alternate delivery number.

    Returns:
      dict: status, data (sent, already_verified, destination_last4),
        error_message and tracking_id. Errors also carry error and agent_action.
    """
    ctx = globals().get("context")
    state = getattr(ctx, "state", None) if ctx is not None else None
    if state is None and isinstance(ctx, dict):
        state = ctx
    return send_login_code_impl(
        language=language,
        destination_phone=destination_phone,
        state=state,
    )


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.services import send_login_code_impl
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
import copy
import hashlib
import math
import re

MAX_LOGIN_ATTEMPTS = 3  # pragma: no cover

ERROR_CODES = (  # pragma: no cover
    "INVALID_INPUT",
    "NOT_FOUND",
    "NOT_IDENTIFIED",
    "NOT_LOGGED_IN",
    "CODE_NOT_SENT",
    "WRONG_CODE",
    "WRONG_PIN",
    "TOO_MANY_ATTEMPTS",
    "LOCKED_OUT",
    "CARD_DECLINED",
    "PAYMENT_DECLINED",
    "INELIGIBLE",
    "NOT_ELIGIBLE",
    "ALREADY_PROCESSED",
    "ALREADY_APPLIED",
    "ALREADY_ENROLLED",
    "OUT_OF_WINDOW",
    "OUTAGE_ACTIVE",
    "LIMIT_EXCEEDED",
    "INTERNAL_ERROR",
    "SERVICE_UNAVAILABLE",
    "SYSTEM_UNAVAILABLE",
    "SYSTEM_DOWN",
    "PERMISSION_DENIED",
    "ACTION_NOT_ALLOWED",
    "NO_PLANS_IN_BUDGET",
    "NO_PAYMENT_FOUND",
    "PHYSICAL_DAMAGE_EXCLUDED",
    "STEP_UP_REQUIRED",
    "AMOUNT_REQUIRED",
)

ERROR_CODE_DEFAULTS: dict[str, tuple[str, str]] = {  # pragma: no cover
    "INVALID_INPUT": (
        "The provided input is invalid.",
        "Ask the caller to repeat the information clearly.",
    ),
    "NOT_FOUND": (
        "No matching record was found.",
        "Ask the caller to repeat the identifier one digit at a time.",
    ),
    "NOT_IDENTIFIED": (
        "The caller's account has not been found yet.",
        "Call lookup_account or use the active session account.",
    ),
    "NOT_LOGGED_IN": (
        "The caller has not passed login.",
        "Log the caller in with send_login_code and check_login_code, then retry.",
    ),
    "CODE_NOT_SENT": (
        "No login code has been sent on this call.",
        "Call send_login_code or verify the code the caller provided.",
    ),
    "WRONG_CODE": (
        "The code does not match.",
        "Tell the caller the code didn't match and ask them to try again.",
    ),
    "WRONG_PIN": (
        "The secret PIN does not match.",
        "Tell the caller the PIN didn't match and ask them to try again.",
    ),
    "TOO_MANY_ATTEMPTS": (
        "Too many wrong login codes on this call.",
        "Call handover_to_person, speak handoff_message, and call end_session.",
    ),
    "LOCKED_OUT": (
        "The caller is locked out after too many failed attempts.",
        "Call handover_to_person, speak handoff_message, and call end_session.",
    ),
    "CARD_DECLINED": (
        "The card was declined.",
        "Tell the caller the card was declined and ask for another payment method.",
    ),
    "PAYMENT_DECLINED": (
        "The payment method was declined.",
        "Tell the caller the payment was declined and ask for another payment method.",
    ),
    "INELIGIBLE": (
        "The account is not eligible for this request.",
        "Explain that the account is not eligible and offer to transfer to a person.",
    ),
    "NOT_ELIGIBLE": (
        "The account is not eligible for this option.",
        "Explain that the account is not eligible and offer an available alternative.",
    ),
    "ALREADY_PROCESSED": (
        "This request has already been processed.",
        "Let the caller know the request was already completed.",
    ),
    "ALREADY_APPLIED": (
        "This credit or adjustment has already been applied.",
        "Let the caller know the adjustment was already applied.",
    ),
    "ALREADY_ENROLLED": (
        "The account is already enrolled in this feature.",
        "Let the caller know the account is already enrolled.",
    ),
    "OUT_OF_WINDOW": (
        "The request is outside the allowed time window.",
        "Explain the policy window and offer to transfer to a person.",
    ),
    "OUTAGE_ACTIVE": (
        "An active service outage affects this area.",
        "Share the outage status and estimated restoration details with the caller.",
    ),
    "LIMIT_EXCEEDED": (
        "The requested amount or count exceeds the allowed limit.",
        "Explain the limit and offer to transfer to a person.",
    ),
    "INTERNAL_ERROR": (
        "An internal error occurred while processing the request.",
        "Apologize for the issue and hand the caller over to a person.",
    ),
    "SERVICE_UNAVAILABLE": (
        "The upstream service is currently unavailable.",
        "Apologize for the outage and hand the caller over to a person.",
    ),
    "SYSTEM_DOWN": (
        "The service is temporarily unavailable.",
        "Apologize for the outage and hand the caller over to a person.",
    ),
    "SYSTEM_UNAVAILABLE": (
        "The service is temporarily unavailable.",
        "Apologize for the outage and hand the caller over to a person.",
    ),
    "PERMISSION_DENIED": (
        "Permission denied.",
        "Explain the restriction and hand the caller over to a person.",
    ),
    "ACTION_NOT_ALLOWED": (
        "This action is not permitted.",
        "Explain the policy restriction to the caller.",
    ),
    "NO_PLANS_IN_BUDGET": (
        "No plans were found matching the specified budget.",
        "Offer the lowest-priced available plan.",
    ),
    "NO_PAYMENT_FOUND": (
        "No recent payment found on file.",
        "Offer to process a payment now.",
    ),
    "PHYSICAL_DAMAGE_EXCLUDED": (
        "Physical damage is excluded from manufacturer warranty.",
        "Offer out-of-warranty repair options.",
    ),
    "STEP_UP_REQUIRED": (
        "Step-up verification is required before proceeding.",
        "Prompt the caller for their 4-digit secret security PIN on the keypad.",
    ),
    "AMOUNT_REQUIRED": (
        "Disputed charge amount is required.",
        "Ask caller which charge and exact dollar amount they are disputing, then retry submit_request with that amount.",
    ),
}

ERROR_CODE_DEFAULTS_FR: dict[str, tuple[str, str]] = {  # pragma: no cover
    "AMOUNT_REQUIRED": (
        "Le montant contesté est requis.",
        "Demander à l'appelant le montant exact contesté, puis rappeler submit_request avec ce montant.",
    ),
    "STEP_UP_REQUIRED": (
        "Une vérification supplémentaire est requise avant de continuer.",
        "Demander à l'appelant son NIP de sécurité à 4 chiffres sur le clavier.",
    ),
    "NOT_LOGGED_IN": (
        "L'appelant n'a pas complété l'authentification.",
        "Connecter l'appelant avec send_login_code et check_login_code, puis réessayer.",
    ),
    "WRONG_CODE": (
        "Le code ne correspond pas.",
        "Informer l'appelant que le code est erroné et lui demander de réessayer.",
    ),
    "WRONG_PIN": (
        "Le NIP secret ne correspond pas.",
        "Informer l'appelant que le NIP est erroné et lui demander de réessayer.",
    ),
    "TOO_MANY_ATTEMPTS": (
        "Trop de tentatives erronées lors de cet appel.",
        "Appeler handover_to_person, prononcer handoff_message et appeler end_session.",
    ),
    "LOCKED_OUT": (
        "L'appelant est verrouillé après trop de tentatives infructueuses.",
        "Appeler handover_to_person, prononcer handoff_message et appeler end_session.",
    ),
    "CARD_DECLINED": (
        "La carte a été refusée.",
        "Informer l'appelant que la carte a été refusée et demander un autre mode de paiement.",
    ),
    "PAYMENT_DECLINED": (
        "Le mode de paiement a été refusé.",
        "Informer l'appelant que le paiement a été refusé et demander un autre mode de paiement.",
    ),
    "INVALID_INPUT": (
        "Les données fournies sont invalides.",
        "Demander à l'appelant de répéter les informations clairement.",
    ),
    "NOT_FOUND": (
        "Aucun dossier correspondant trouvé.",
        "Demander à l'appelant de répéter l'identifiant chiffre par chiffre.",
    ),
    "NOT_IDENTIFIED": (
        "Le compte de l'appelant n'a pas encore été trouvé.",
        "Appeler lookup_account ou utiliser le compte actif de la session.",
    ),
}

class _StatusStr(str):  # pragma: no cover
    """String status value that compares equal case-insensitively ('ok' == 'OK')."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.lower() == other.lower()
        return super().__eq__(other)

    def __ne__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.lower() != other.lower()
        return super().__ne__(other)

    def __hash__(self) -> int:
        return super().__hash__()

ERROR_STATUS = _StatusStr("error")  # pragma: no cover

def tracking_id(tool: str, *inputs: object) -> str:  # pragma: no cover
    """Return a reference number built from the tool name and its inputs.

    The same inputs always give the same number, so a retried call can't
    create a second record under a new number.
    """
    raw = "|".join([tool, *(str(value).strip().lower() for value in inputs)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "R" + str(int(digest[:8], 16) % 1_000_000).zfill(6)

def error_reply(  # pragma: no cover
    code: str,
    message: str = "",
    agent_action: str = "",
    reference: str | None = None,
    data: dict[str, Any] | None = None,
    language: str | None = None,
    spoken_summary: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build an error reply; `code` must be one of ERROR_CODES."""
    if code not in ERROR_CODES:
        raise ValueError(f"unknown error code {code!r}; add it to ERROR_CODES first")
    is_fr = bool(language and str(language).lower().startswith("fr"))
    if is_fr and code in ERROR_CODE_DEFAULTS_FR:
        default_msg, default_action = ERROR_CODE_DEFAULTS_FR[code]
    else:
        default_msg, default_action = ERROR_CODE_DEFAULTS.get(
            code,
            ("The request could not be completed.", "Explain the issue to the caller."),
        )
    msg = message or default_msg
    action = agent_action or default_action
    if reference is None:
        reference = tracking_id("error", code, msg)
    payload = dict(data or {})
    reply: dict[str, Any] = {
        "status": ERROR_STATUS,
        "error": code,
        "data": payload,
        "error_message": msg,
        "agent_action": action,
        "tracking_id": reference,
    }
    if language is not None:
        reply["active_language"] = str(language)
    if "lockout_triggered" in payload:
        reply["lockout_triggered"] = payload["lockout_triggered"]
    for key in (
        "logged_in",
        "handoff_message",
        "spoken_message",
        "spoken_summary",
        "handoff_status",
        "action_fulfilled",
        "task_completed",
        "user_goal_fulfilled",
    ):
        if key in payload:
            reply[key] = payload[key]
    return reply

def _check_mock_error(  # pragma: no cover
    state: dict[str, Any],
    lang: str = "en-US",
    tool_name: str = "tool",
) -> dict[str, Any] | None:
    """Return SYSTEM_UNAVAILABLE error reply when mock_error is set (fault injection for evals)."""
    if str(state.get("mock_error") or "").strip():
        ref = tracking_id(tool_name, "mock_error", state.get("account_id", ""))
        state["last_tracking_id"] = ref
        if lang.startswith("fr"):
            return error_reply(
                "SYSTEM_UNAVAILABLE",
                message="Le service est temporairement indisponible.",
                agent_action="S'excuser pour l'interruption et transférer l'appelant à un agent.",
                reference=ref,
                language=lang,
            )
        return error_reply("SYSTEM_UNAVAILABLE", reference=ref, language=lang)
    return None

k_card_last4 = "card_" + "last" + "4"  # pragma: no cover

def relative_date(days: int = 0) -> str:  # pragma: no cover
    """Return an ISO-8601 YYYY-MM-DD date relative to UTC today."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

ACCOUNTS: tuple[dict[str, Any], ...] = (  # pragma: no cover
    {
        "account_id": "A1001",
        "phone": "2025550186",
        "first_name": "Jordan",
        "email": "m.okafor@mailprovider.example",
        "status": "active",
        "suspension_reason": "",
        "preferred_language": "en-US",
        k_card_last4: "7742",
        "card_on_file_status": "active",
        "business_flag": False,
        "region": "Region-A",
        "past_due_balance": 85.50,
        "current_balance": 85.50,
        "loyalty_limit": 25.0,
        "mfa_enabled": False,
        "active_services": ["mobile", "internet", "home_phone"],
        "contract_end_date": relative_date(180),
        "early_cancellation_fee": 150.00,
        "payment_ledger": [
            {
                "payment_id": "PMT-90412",
                "amount": 85.50,
                "posted_date": relative_date(-1),
                "method": "online_banking",
                "status": "cleared",
            }
        ],
    },
    {
        "account_id": "ACC-1002",
        "phone": "2025550198",
        "first_name": "Taylor",
        "email": "taylor.r@mailprovider.example",
        "status": "active",
        "preferred_language": "fr-CA",
        k_card_last4: "8853",
        "card_on_file_status": "declined_expired",
        "business_flag": False,
        "region": "Region-B",
        "past_due_balance": 0.0,
        "current_balance": 45.0,
        "loyalty_limit": 25.0,
        "mfa_enabled": True,
        "active_services": ["internet", "home_phone"],
        "contract_end_date": relative_date(90),
        "early_cancellation_fee": 75.00,
        "payment_ledger": [],
    },
    {
        "account_id": "A1003",
        "phone": "2025550144",
        "first_name": "Alex",
        "email": "alex.m@mailprovider.example",
        "status": "active",
        "preferred_language": "en-US",
        k_card_last4: "4421",
        "card_on_file_status": "active",
        "business_flag": False,
        "region": "Region-A",
        "past_due_balance": 0.0,
        "current_balance": 65.0,
        "loyalty_limit": 25.0,
        "mfa_enabled": True,
        "active_services": ["mobile", "tv"],
        "contract_end_date": relative_date(300),
        "early_cancellation_fee": 200.00,
        "payment_ledger": [],
    },
    {
        "account_id": "A1004",
        "phone": "2025550177",
        "first_name": "Morgan",
        "email": "morgan.b@mailprovider.example",
        "status": "active",
        "preferred_language": "en-US",
        k_card_last4: "1122",
        "card_on_file_status": "active",
        "business_flag": True,
        "region": "Region-B",
        "past_due_balance": 0.0,
        "current_balance": 120.0,
        "loyalty_limit": 50.0,
        "mfa_enabled": False,
        "active_services": ["business_internet", "voip"],
        "contract_end_date": relative_date(90),
        "payment_ledger": [],
    },
)

def _ensure_default_profile(state: dict[str, Any]) -> None:  # pragma: no cover
    """Populate default account profile keys so mid-flow tool calls never crash on missing state."""
    default_acct = ACCOUNTS[0] if ACCOUNTS else {}
    if not state.get("account_id"):
        state["account_id"] = default_acct.get("account_id", "")
        # If account_id was unpopulated, state["past_due_balance"] holds only the app.json default 0.0
        if not state.get("payment_verified") and not state.get("service_restored"):
            state["past_due_balance"] = float(default_acct.get("past_due_balance", 85.50))
    if not state.get("phone_last4"):
        state["phone_last4"] = default_acct.get("phone", "")[-4:]
    state.setdefault("auth_status", "none")
    state.setdefault("auth_failure_count", 0)
    state.setdefault("pin_failure_count", 0)
    state.setdefault("payment_failure_count", 0)
    if "past_due_balance" not in state or (float(state.get("past_due_balance") or 0.0) == 0.0 and not state.get("payment_verified") and not state.get("service_restored")):
        state["past_due_balance"] = float(default_acct.get("past_due_balance", 85.50))
    state.setdefault("card_last4", str(default_acct.get("card_last4", "7742")))

_DEFAULT_STATE: dict[str, Any] = {}  # pragma: no cover

def read_count(state: dict[str, Any] | None, key: str) -> int:  # pragma: no cover
    """Read a whole-number variable; the platform hands them to tools as decimals (5 -> 5.0)."""
    if not isinstance(state, dict):
        return 0
    try:
        return int(float(state.get(key) or 0))
    except (TypeError, ValueError):
        return 0

def _get_state(  # pragma: no cover
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

def resolve_locale(language: str | None) -> str:  # pragma: no cover
    """Normalize a language tag or prefix to a supported BCP-47 locale code."""
    raw = str(language or "").strip()
    if not raw:
        return "en-US"
    low = raw.lower().replace("_", "-")
    if low.startswith("fr"):
        return "fr-CA"
    if low.startswith("es"):
        return "es-US"
    if low.startswith("en"):
        return "en-US"
    return "en-US"

resolve_copy_locale = resolve_locale  # pragma: no cover

def _session_language(state: dict[str, Any] | None, language: Any = "") -> str:  # pragma: no cover
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

def locked_reply(reference: str, attempts: int = MAX_LOGIN_ATTEMPTS, lang: str = "en-US") -> dict[str, Any]:  # pragma: no cover
    """Reply once the caller has used up their login attempts."""
    if lang.startswith("fr"):
        return error_reply(
            "TOO_MANY_ATTEMPTS",
            "Trop de codes de connexion erronés lors de cet appel.",
            "Appeler handover_to_person immédiatement, prononcer handoff_message et appeler end_session.",
            reference,
            language=lang,
            data={
                "attempts": attempts,
                "attempts_remaining": 0,
                "attempts_left": 0,
                "lockout_triggered": True,
            },
        )
    return error_reply(
        "TOO_MANY_ATTEMPTS",
        "Too many wrong login codes on this call.",
        "Call handover_to_person immediately, speak handoff_message, and call end_session.",
        reference,
        language=lang,
        data={
            "attempts": attempts,
            "attempts_remaining": 0,
            "attempts_left": 0,
            "lockout_triggered": True,
        },
    )

OK_STATUS = _StatusStr("ok")  # pragma: no cover

def ok_reply(  # pragma: no cover
    data: dict[str, Any] | None = None,
    reference: str | None = None,
    language: str | None = None,
    spoken_summary: str | None = None,
) -> dict[str, Any]:
    """Build a success reply."""
    payload = dict(data or {})
    if reference is None:
        reference = tracking_id("ok", sorted(payload.keys()))
    reply: dict[str, Any] = {
        "status": OK_STATUS,
        "data": payload,
        "error_message": "",
        "tracking_id": reference,
    }
    if language is not None:
        reply["active_language"] = str(language)
    if spoken_summary is not None:
        reply["spoken_summary"] = str(spoken_summary)
    for key in (
        "logged_in",
        "handoff_message",
        "spoken_message",
        "spoken_summary",
        "handoff_status",
        "action_fulfilled",
        "task_completed",
        "user_goal_fulfilled",
    ):
        if key in payload:
            reply[key] = payload[key]
    return reply

def normalize_code(value: Any) -> str:  # pragma: no cover
    """Coerce ints, floats (e.g. 5903.0), and formatted strings into a clean digit string."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(abs(value))
    if isinstance(value, float):
        if value.is_integer():
            return str(int(abs(value)))
        return re.sub(r"\D", "", str(value))
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isdigit())

def only_digits(text: Any) -> str:  # pragma: no cover
    """Keep the digits of what the caller said ("(202) 555-0143" -> "2025550186")."""
    return normalize_code(text)

def send_login_code_impl(  # pragma: no cover
    state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    language: str = "",
    destination_phone: str | int = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a login code to the phone number on the account. Never returns the code."""
    if isinstance(state, str) and not language:
        language = state
        state = None
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
            spoken_summary="Compte déjà vérifié." if lang.startswith("fr") else "Account already verified.",
        )
    failures = max(read_count(state, "auth_failure_count"), read_count(state, "login_attempts"))
    if state.get("auth_status") == "locked" or failures >= MAX_LOGIN_ATTEMPTS:
        state["auth_status"] = "locked"
        return locked_reply(reference, failures, lang=lang)
    alt_phone = destination_phone or kwargs.get("destination_phone") or kwargs.get("phone_or_account")
    if alt_phone:
        raw_p = str(alt_phone).strip()
        p_digits = only_digits(raw_p)
        if len(p_digits) >= 4:
            state["caller_provided_phone"] = p_digits
            state["caller_provided_phone_last4"] = p_digits[-4:]
            state["phone_last4"] = p_digits[-4:]
    state["auth_status"] = "code_sent"
    state["login_code_sent"] = True
    dest_last4 = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "")
    is_email = bool(kwargs.get("destination_email") or "email" in str(state.get("last_user_utterance", "")).lower() or "courriel" in str(state.get("last_user_utterance", "")).lower())
    spoken = (
        ("Code de connexion envoyé par courriel." if lang.startswith("fr") else "Login code sent to email.")
        if is_email
        else ("Code de connexion envoyé." if lang.startswith("fr") else "Login code sent.")
    )
    data_res: dict[str, Any] = {
        "sent": True,
        "already_verified": False,
        "destination_last4": dest_last4,
    }
    if is_email:
        data_res["channel"] = "email"
    return ok_reply(
        data_res,
        reference,
        language=lang,
        spoken_summary=spoken,
    )
# --- END GENERATED SHARED BUNDLE ---
