"""The one reply shape every tool returns (docs/DESIGN_RULES.md rule 10).

ok:    {"status": "ok", "data": {...}, "error_message": "", "tracking_id": "R790315"}
error: the same keys, plus "error" (a code from ERROR_CODES) and "agent_action"
       (what the model should do next; it is never read aloud).

Money goes out as a number plus a two-decimal string, for example
{"amount": 85.5, "amount_display": display_amount(85.5), "currency": "CAD"}:
an agent given only 85.5 read it aloud as "85.5 dollars".
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
import hashlib
from typing import Any


class _StatusStr(str):
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


OK_STATUS = _StatusStr("ok")
ERROR_STATUS = _StatusStr("error")

# Every error code a tool may return. suite/tool_tests.py checks tests against
# this list, so add a new code here first.
ERROR_CODES = (
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
)

ERROR_CODE_DEFAULTS: dict[str, tuple[str, str]] = {
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
}

ERROR_CODE_DEFAULTS_FR: dict[str, tuple[str, str]] = {
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


def tracking_id(tool: str, *inputs: object) -> str:
    """Return a reference number built from the tool name and its inputs.

    The same inputs always give the same number, so a retried call can't
    create a second record under a new number.
    """
    raw = "|".join([tool, *(str(value).strip().lower() for value in inputs)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "R" + str(int(digest[:8], 16) % 1_000_000).zfill(6)


def display_amount(value: Any) -> str:
    """Format money for the agent to say: 85.5 -> "85.50" (two decimals, half-up rounding).

    Return it next to the number, never instead of it:
    {"amount": 85.5, "amount_display": "85.50", "currency": "CAD"}.
    """
    if isinstance(value, bool) or value is None:
        raise ValueError(f"not an amount: {value!r}")
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not an amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"not an amount: {value!r}")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def ok_reply(
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


def error_reply(
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
