from typing import Any



def submit_request(summary: str, language: str = "") -> dict[str, Any]:
    """Records the caller's request on their account and returns a reference number.

    Call this only after the caller has confirmed the request. It refuses with
    error NOT_LOGGED_IN until the caller has passed login.

    Args:
      summary: The confirmed request in one sentence.
      language: BCP-47 language code (e.g. en-US, fr-CA, es-US).

    Returns:
      dict: status, data (submitted), error_message and tracking_id, which is
        the reference number for the caller. Errors also carry error and
        agent_action.
    """
    ctx = globals().get("context")
    state = getattr(ctx, "state", None) if ctx is not None else None
    if state is None and isinstance(ctx, dict):
        state = ctx
    return submit_request_impl(
        summary=summary,
        state=state,
        language=language,
    )


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.services import submit_request_impl
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
import hashlib
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
) -> dict[str, Any]:
    """Build an error reply; `code` must be one of ERROR_CODES."""
    if code not in ERROR_CODES:
        raise ValueError(f"unknown error code {code!r}; add it to ERROR_CODES first")
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
        return error_reply("SYSTEM_UNAVAILABLE", reference=ref, language=lang)
    return None

ACCOUNTS: tuple[dict[str, str], ...] = (  # pragma: no cover
    {
        "account_id": "A1001",
        "phone": "2025550186",
        "first_name": "Jordan",
        "email": "m.okafor@mailprovider.example",
        "status": "active",
        "preferred_language": "en-US",
        "card_last4": "7742",
    },
    {
        "account_id": "ACC-1002",
        "phone": "2025550198",
        "first_name": "Taylor",
        "email": "taylor.r@mailprovider.example",
        "status": "active",
        "preferred_language": "fr-CA",
        "card_last4": "8853",
    },
)

def _ensure_default_profile(state: dict[str, Any]) -> None:  # pragma: no cover
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
        "en-US": "I'm transferring you to a member of our team now. Thank you for your patience.",
        "fr-CA": "Je vous transfère maintenant à un membre de notre équipe. Merci de votre patience.",
        "es-US": "Le transfiero ahora con un miembro de nuestro equipo. Gracias por su paciencia.",
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
        "fr-CA": "Je vous transfère à un spécialiste de la facturation dès maintenant — il aura accès à tout ce dont nous avons déjà discuté.",
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
        "es-US": "La cuenta ya está verificada.",
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

def spoken_line(key: str, language: str | None = "en-US", **slots: object) -> str:  # pragma: no cover
    """Return the fixed spoken line for `key` and `language`, filling any `[slot]` placeholders."""
    locale = resolve_locale(language)
    table = SPOKEN_LINES.get(key, {})
    template = table.get(locale) or table.get("en-US") or ""
    for slot_name, slot_val in slots.items():
        template = template.replace(f"[{slot_name}]", str(slot_val)).replace(f"{{{slot_name}}}", str(slot_val))
    return template

def _handle_telco_domain_request(  # pragma: no cover
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

resolve_copy_locale = resolve_locale  # pragma: no cover

def _session_language(state: dict[str, Any] | None, language: Any = "") -> str:  # pragma: no cover
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

def submit_request_impl(  # pragma: no cover
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
# --- END GENERATED SHARED BUNDLE ---
