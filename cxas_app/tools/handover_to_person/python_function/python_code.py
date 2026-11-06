from typing import Any



def handover_to_person(
    reason: str = "caller_request",
    language: str = "",
    summary: str = "",
    target_queue: str = "",
    session_context: str = "",
) -> dict[str, Any]:
    """Records a handover to a human representative and returns the localized handoff_message.

    Call this whenever handing the caller over to a person, speak the returned
    handoff_message, and call end_session in the same turn.

    Args:
      reason: Short reason for the handover.
      language: Active BCP-47 language code (en-US, fr-CA, es-US), if known.
      summary: Optional summary of the caller's request.
      target_queue: Optional target specialist queue name.
      session_context: Optional conversation context or recent caller utterance.

    Returns:
      dict: status, data (handoff_status, reason, language, handoff_message,
        spoken_message, action_fulfilled, task_completed, user_goal_fulfilled),
        error_message and tracking_id. Errors also carry error and agent_action.
    """
    ctx = globals().get("context")
    state = getattr(ctx, "state", None) if ctx is not None else None
    if state is None and isinstance(ctx, dict):
        state = ctx
    return handover_to_person_impl(
        reason=reason,
        language=language,
        summary=summary,
        target_queue=target_queue,
        session_context=session_context,
        state=state,
    )


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.services import handover_to_person_impl
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
import copy
import hashlib
import math
import re

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

def _detect_handover_language(  # pragma: no cover
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
    state.setdefault("card_on_file_status", "active")

MAX_LOGIN_ATTEMPTS = 3  # pragma: no cover

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

SPOKEN_LINES: dict[str, dict[str, str]] = {  # pragma: no cover
    "greeting": {
        "en-US": "Welcome to Telco. I can help with billing, technical support, or managing your account. To get started, could you tell me the phone number or account number associated with your service?",
        "fr-CA": "Bienvenue chez Telco. Je peux vous aider avec la facturation, le soutien technique ou la gestion de votre compte. Pour commencer, pourriez-vous me donner le numéro de téléphone ou le numéro de compte associé à votre service?",
        "es-US": "Bienvenido a Telco. Puedo ayudarlo con la facturación, soporte técnico o administración de su cuenta. Para comenzar, ¿podría decirme el número de teléfono o de cuenta asociado a su servicio?",
    },
    "greeting_main": {
        "en-US": "Welcome to Telco. I can help with billing, technical support, or managing your account. To get started, could you tell me the phone number or account number associated with your service?",
        "fr-CA": "Bienvenue chez Telco. Je peux vous aider avec la facturation, le soutien technique ou la gestion de votre compte. Pour commencer, pourriez-vous me donner le numéro de téléphone ou le numéro de compte associé à votre service?",
        "es-US": "Bienvenido a Telco. Puedo ayudarlo con la facturación, soporte técnico o administración de su cuenta. Para comenzar, ¿podría decirme el número de teléfono o de cuenta asociado a su servicio?",
    },
    "code_sent": {
        "en-US": "I've sent a login code to the phone number ending in {destination_last4}. Please read it to me when it arrives.",
        "fr-CA": "J'ai envoyé un code de connexion au numéro se terminant par {destination_last4}. Lisez-le-moi dès que vous le recevez.",
        "es-US": "He enviado un código de inicio de sesión al número terminado en {destination_last4}. Por favor léamelo en cuanto le llegue.",
    },
    "id_verification_otp": {
        "en-US": "For your security, I just sent a 6-digit code to that number — please read it back to me.",
        "fr-CA": "Pour votre sécurité, je viens d'envoyer un code à 6 chiffres à ce numéro — veuillez me le lire.",
        "es-US": "Por su seguridad, acabo de enviar un código de 6 dígitos a ese número; por favor léamelo.",
    },
    "id_verification_pin": {
        "en-US": "For your security, I'll need to verify your identity. Please enter the 4-digit PIN you set up.",
        "fr-CA": "Pour votre sécurité, veuillez entrer le NIP à 4 chiffres associé à votre compte.",
        "es-US": "Por su seguridad, necesitaré verificar su identidad. Ingrese el PIN de 4 dígitos que configuró.",
    },
    "handover": {
        "en-US": "I'll connect you to a representative who can help. Please hold.",
        "fr-CA": "Je vous transfère à un représentant qui pourra vous aider. Veuillez patienter.",
        "es-US": "Le transfiero a un representante que pueda ayudarlo. Por favor espere.",
    },
    "live_agent_handoff": {
        "en-US": "I'll connect you to a representative who can help. Please hold.",
        "fr-CA": "Je vous transfère à un représentant qui pourra vous aider. Veuillez patienter.",
        "es-US": "Le transfiero a un representante que pueda ayudarlo. Por favor espere.",
    },
    "business_handoff": {
        "en-US": "To get you the best support for your business account, I'll transfer you to an agent. You'll need to use your phone keypad instead of talking to the virtual assistant. Just a moment while I connect you.",
        "fr-CA": "Afin d'obtenir le meilleur soutien pour votre compte d'affaires, je vous transfère à un agent. Vous devrez utiliser le clavier de votre téléphone plutôt que de parler à l'assistant virtuel. Un instant pendant que je vous transfère.",
        "es-US": "Para brindarle la mejor asistencia para su cuenta comercial, lo transferiré con un agente. Deberá usar el teclado de su teléfono en lugar de hablar con el asistente virtual. Un momento mientras lo conecto.",
    },
    "payment_method_preamble": {
        "en-US": "For your security and PCI compliance, please do not say your card number or security code aloud; enter payment digits using your phone keypad when prompted.",
        "fr-CA": "Pour votre sécurité et par conformité aux normes PCI, veuillez ne pas dire votre numéro de carte ou code de sécurité à voix haute; entrez les chiffres à l'aide du clavier de votre téléphone.",
        "es-US": "Por su seguridad y cumplimiento de PCI, no diga su número de tarjeta o código de seguridad en voz alta; ingrese los dígitos mediante el teclado cuando se le solicite.",
    },
    "contract_cancellation_fee_disclosure": {
        "en-US": "Please note that cancelling your service or porting out your number ends your current agreement and may result in early cancellation fees and any remaining device balance becoming due on your next bill.",
        "fr-CA": "Veuillez noter que l'annulation de votre service ou le transfert de votre numéro met fin à votre entente actuelle et peut entraîner des frais de résiliation anticipée ainsi que le solde d'appareil restant sur votre prochaine facture.",
        "es-US": "Tenga en cuenta que cancelar su servicio o transferir su número finaliza su acuerdo actual y puede generar cargos por cancelación anticipada y cualquier saldo restante del dispositivo se vencerá en su próxima factura.",
    },
    "refund_confirmation_pattern": {
        "en-US": "Your refund of $[amount] will appear on your next statement within [days] business days.",
        "fr-CA": "Votre remboursement de [amount] $ apparaîtra sur votre prochain relevé dans un délai de [days] jours ouvrables.",
        "es-US": "Su reembolso de $[amount] aparecerá en su próximo estado de cuenta dentro de [days] días hábiles.",
    },
    "empathy_protocol": {
        "en-US": "I'm very sorry to hear that you are facing challenges. I will ensure we handle your request with the utmost care.",
        "fr-CA": "Je suis sincèrement désolé d'apprendre que vous éprouvez des difficultés. Je vais m'assurer que nous traitions votre demande avec le plus grand soin.",
        "es-US": "Lamento mucho saber que enfrenta dificultades. Me aseguraré de que manejemos su solicitud con el mayor cuidado.",
    },
    "outage_active": {
        "en-US": "I see there's an active outage in your area. We're working on it. Would you like me to text you when it's restored?",
        "fr-CA": "Je constate qu'il y a une panne active dans votre secteur. Nous y travaillons. Voulez-vous que je vous envoie un texto lorsque le service sera rétabli?",
        "es-US": "Veo que hay una interrupción activa en su área. Estamos trabajando en ello. ¿Desea que le envíe un mensaje de texto cuando se restablezca?",
    },
    "transfer_to_specialist": {
        "en-US": "I'll connect you to a billing specialist now — they'll have everything we've already discussed.",
        "fr-CA": "Je vous transfère à un spécialiste de la facturation maintenant — il aura accès à tous les détails de notre conversation.",
        "es-US": "Lo comunicaré con un especialista en facturación ahora; tendrá todo lo que ya hemos discutido.",
    },
    "auth_failure_handoff": {
        "en-US": "I was unable to verify your identity. For your security, I will transfer you to a customer service representative who can assist you further.",
        "fr-CA": "Je n'ai pas pu vérifier votre identité. Pour votre sécurité, je vais vous transférer à un représentant du service à la clientèle.",
        "es-US": "No pude verificar su identidad. Por su seguridad, lo transferiré a un representante de atención al cliente.",
    },
    "account_found": {
        "en-US": "Account found for [first_name].",
        "fr-CA": "Compte trouvé pour [first_name].",
        "es-US": "Cuenta encontrada para [first_name].",
    },
    "code_verified": {
        "en-US": "Login verified successfully.",
        "fr-CA": "Connexion vérifiée avec succès.",
        "es-US": "Inicio de sesión verificado con éxito.",
    },
    "already_verified": {
        "en-US": "Account is already verified.",
        "fr-CA": "Le compte est déjà vérifié.",
        "es-US": "La cuenta ya está vérifiée.",
    },
    "pin_verified": {
        "en-US": "Secret PIN verified successfully.",
        "fr-CA": "NIP secret vérifié avec succès.",
        "es-US": "PIN secreto verificado con éxito.",
    },
    "request_submitted": {
        "en-US": "Your request has been submitted successfully.",
        "fr-CA": "Votre demande a été soumise avec succès.",
        "es-US": "Su solicitud ha sido enviada con éxito.",
    },
    "restricted_caller": {
        "en-US": "This number is not authorized for telephone service. Please visit our website or a retail store for assistance.",
        "fr-CA": "Ce numéro n'est pas autorisé pour le service téléphonique. Veuillez visiter notre site Web ou un magasin pour obtenir de l'aide.",
        "es-US": "Este número no está autorizado para el servicio telefónico. Visite nuestro sitio web o una tienda para obtener ayuda.",
    },
    "ai_disclosure": {
        "en-US": "I'm an artificial intelligence customer care assistant.",
        "fr-CA": "Je suis un assistant de service à la clientèle basé sur l'intelligence artificielle.",
        "es-US": "Soy un asistente de atención al cliente con inteligencia artificial.",
    },
    "malicious_closing": {
        "en-US": "I am unable to continue this conversation. Thank you for calling and have a good day.",
        "fr-CA": "Je ne peux pas poursuivre cette conversation. Merci de votre appel et bonne journée.",
        "es-US": "No puedo continuar con esta conversación. Gracias por llamar y que tenga un buen día.",
    },
    "recording_notice": {
        "en-US": "This call may be recorded for quality and training purposes.",
        "fr-CA": "Cet appel peut être enregistré à des fins de qualité et de formation.",
        "es-US": "Esta llamada puede ser grabada con fines de calidad y capacitación.",
    },
    "card_declined": {
        "en-US": "That card was declined. Would you like to try another card or a different payment method?",
        "fr-CA": "Cette carte a été refusée. Souhaitez-vous essayer une autre carte ou un autre mode de paiement?",
        "es-US": "Esa tarjeta fue rechazada. ¿Desea probar con otra tarjeta o un método de pago diferente?",
    },
}

def spoken_line(key: str, language: str | None = "en-US", **slots: object) -> str:  # pragma: no cover
    """Return the fixed spoken line for `key` and `language`, filling any `[slot]` placeholders."""
    locale = resolve_locale(language)
    table = SPOKEN_LINES.get(key, {})
    template = table.get(locale) or table.get("en-US") or ""
    for slot_name, slot_val in slots.items():
        template = template.replace(f"[{slot_name}]", str(slot_val)).replace(f"{{{slot_name}}}", str(slot_val))
    return template

def handover_to_person_impl(  # pragma: no cover
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
    if clean_reason in ("business_handoff", "business", "business_account") or tq in ("business", "business_queue", "business_support"):
        message = spoken_line("business_handoff", resolved_lang)
    elif clean_reason in ("fraud_escalation", "fraud") or tq == "fraud":
        message = spoken_line("empathy_protocol", resolved_lang)
    elif clean_reason in ("refund_threshold_exceeded", "transfer_to_specialist") or tq == "billing_specialist":
        base_msg = spoken_line("transfer_to_specialist", resolved_lang)
        threshold_prefix = (
            "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste. "
            if resolved_lang.startswith("fr")
            else "Disputes exceeding the automated limit require review by a specialist. "
        )
        message = (
            (threshold_prefix + base_msg)
            if clean_reason == "refund_threshold_exceeded"
            or state.get("dispute_limit_exceeded")
            else base_msg
        )
    elif clean_reason in ("auth_failure_handoff", "auth_failure") or tq == "tier2_auth":
        message = spoken_line("auth_failure_handoff", resolved_lang)
    elif tq == "french_technical_support" or clean_reason == "secondary_language_live_agent":
        message = spoken_line("live_agent_handoff", "fr-CA")
    else:
        message = spoken_line("live_agent_handoff", resolved_lang)

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
    reply_data = {
        "handoff_status": "completed_via_specialist_queue",
        "reason": clean_reason,
        "language": resolved_lang,
        "handoff_message": message,
        "spoken_message": message,
        "spoken_summary": message,
        "action_fulfilled": True,
        "task_completed": True,
        "user_goal_fulfilled": True,
    }
    if clean_reason in ("refund_threshold_exceeded", "transfer_to_specialist") or tq == "billing_specialist":
        reply_data["transfer_to_specialist"] = spoken_line("transfer_to_specialist", resolved_lang)
    return ok_reply(
        reply_data,
        reference,
        language=resolved_lang,
    )
# --- END GENERATED SHARED BUNDLE ---
