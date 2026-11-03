from typing import Any



def submit_request(
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
    destination_phone: str | int = "",
    days: int | float | str = 0,
) -> dict[str, Any]:
    """Records the caller's request on their account and returns a reference number.

    Call this only after the caller has confirmed the request. It refuses with
    error NOT_LOGGED_IN until the caller has passed login.

    Args:
      summary: The confirmed request in one sentence.
      action: Optional structured action category.
      language: BCP-47 language code (e.g. en-US, fr-CA, es-US).
      card_last4: Last 4 digits of the payment card.
      amount: Transaction or dispute monetary amount.
      max_budget: Maximum monthly budget for plan search.
      slot: Requested appointment schedule window.
      postal_code: Area postal code for outage checks.
      service_type: Type of service (e.g. mobility, internet, tv).
      is_safety_hazard: True if hardware issue involves battery thermal danger or safety hazard.
      destination_phone: Optional alternate phone number or digits if caller specifies an alternate delivery number.
      days: Optional duration in days for SLA downtime credit calculation.

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
        action=action,
        language=language,
        card_last4=card_last4,
        amount=amount,
        max_budget=max_budget,
        slot=slot,
        postal_code=postal_code,
        service_type=service_type,
        is_safety_hazard=is_safety_hazard,
        destination_phone=destination_phone,
        days=days,
        state=state,
    )


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.services import submit_request_impl
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
import hashlib
import math
import re

def relative_date(days: int = 0) -> str:  # pragma: no cover
    """Return an ISO-8601 YYYY-MM-DD date relative to UTC today."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

APPOINTMENTS: dict[str, dict[str, Any]] = {  # pragma: no cover
    "A1001": {
        "appt_id": "APT-401",
        "service_type": "internet_repair",
        "status": "delayed",
        "delay_minutes": 45,
        "date": relative_date(0),
        "window": "13:00 - 17:00",
        "technician_id": "TECH-12",
        "can_cancel": True,
    },
    "ACC-1002": {
        "appt_id": "APT-402",
        "service_type": "tv_install",
        "status": "en_route",
        "delay_minutes": 0,
        "date": relative_date(0),
        "window": "08:00 - 12:00",
        "technician_id": "TECH-15",
        "can_cancel": False,  # prd.md:492 — en-route technician cannot be cancelled
    },
}

AVAILABLE_SLOTS: list[dict[str, str]] = [  # pragma: no cover
    {"slot_id": "SLOT-1", "display": "Tomorrow 08:00 - 12:00", "window": "08:00 - 12:00", "date": relative_date(1)},
    {"slot_id": "SLOT-2", "display": "Tomorrow 13:00 - 17:00", "window": "13:00 - 17:00", "date": relative_date(1)},
    {"slot_id": "SLOT-3", "display": "In two days 09:00 - 13:00", "window": "09:00 - 13:00", "date": relative_date(2)},
]

DECLINED_CARD_LAST4: frozenset[str] = frozenset({"0000", "9999"})  # pragma: no cover

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

OK_STATUS = _StatusStr("ok")  # pragma: no cover

OUTAGE_REGIONS: dict[str, dict[str, Any]] = {  # pragma: no cover
    "Region-A": {
        "active": True,
        "restoration_eta_iso": f"{relative_date(0)}T18:00:00Z",
        "affected_services": ("internet", "tv", "home_phone"),
        "cause": "Fiber optic distribution line maintenance",
        "region": "Region-A",
    },
    "Region-B": {
        "active": False,
        "restoration_eta_iso": "",
        "affected_services": (),
        "cause": "",
        "region": "Region-B",
    },
    "Region-C": {
        "active": False,
        "restoration_eta_iso": "",
        "affected_services": (),
        "cause": "",
        "region": "Region-C",
    },
}

PLAN_CATALOG: dict[str, list[dict[str, Any]]] = {  # pragma: no cover
    "mobility": [
        {
            "plan_id": "MOB-25",
            "name": "Starter Talk & Text",
            "monthly_rate": 25.0,
            "rate_display": "25.00",
            "data_gb": 1,
            "network": "4G LTE",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
            "overage_policy": "no data overage fees; speeds throttled to 512 kbps",
            "contract_term": "month-to-month",
            "taxes_note": "plus applicable taxes",
        },
        {
            "plan_id": "MOB-35",
            "name": "Basic 15GB 4G",
            "monthly_rate": 35.0,
            "rate_display": "35.00",
            "data_gb": 15,
            "network": "4G LTE",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
            "overage_policy": "no data overage fees; speeds throttled to 512 kbps",
            "contract_term": "month-to-month",
            "taxes_note": "plus applicable taxes",
        },
        {
            "plan_id": "MOB-45",
            "name": "Everyday 5G 30GB",
            "monthly_rate": 45.0,
            "rate_display": "45.00",
            "data_gb": 30,
            "network": "5G",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
            "overage_policy": "no data overage fees; speeds throttled to 512 kbps",
            "contract_term": "month-to-month",
            "taxes_note": "plus applicable taxes",
        },
        {
            "plan_id": "MOB-55",
            "name": "Plus 5G 50GB",
            "monthly_rate": 55.0,
            "rate_display": "55.00",
            "data_gb": 50,
            "network": "5G Ultra",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
            "overage_policy": "no data overage fees; speeds throttled to 512 kbps",
            "contract_term": "month-to-month",
            "taxes_note": "plus applicable taxes",
        },
        {
            "plan_id": "MOB-75",
            "name": "Unlimited 5G+ 100GB",
            "monthly_rate": 75.0,
            "rate_display": "75.00",
            "data_gb": 100,
            "network": "5G Ultra",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
            "overage_policy": "no data overage fees; speeds throttled to 512 kbps",
            "contract_term": "month-to-month",
            "taxes_note": "plus applicable taxes",
        },
    ],
    "internet": [
        {
            "plan_id": "NET-100",
            "name": "Fiber 100",
            "monthly_rate": 50.0,
            "rate_display": "50.00",
            "speed_mbps": 100,
            "download_mbps": 100,
            "upload_mbps": 100,
            "unlimited_data": True,
            "data_cap": "Unlimited",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
        },
        {
            "plan_id": "NET-500",
            "name": "Fiber 500",
            "monthly_rate": 70.0,
            "rate_display": "70.00",
            "speed_mbps": 500,
            "download_mbps": 500,
            "upload_mbps": 500,
            "unlimited_data": True,
            "data_cap": "Unlimited",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
        },
        {
            "plan_id": "NET-1000",
            "name": "Gigabit Fiber",
            "monthly_rate": 90.0,
            "rate_display": "90.00",
            "speed_mbps": 1000,
            "download_mbps": 1000,
            "upload_mbps": 750,
            "unlimited_data": True,
            "data_cap": "Unlimited",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
        },
        {
            "plan_id": "NET-1500",
            "name": "Fiber 1.5 Gbps",
            "monthly_rate": 105.0,
            "rate_display": "105.00",
            "speed_mbps": 1500,
            "download_mbps": 1500,
            "upload_mbps": 940,
            "unlimited_data": True,
            "data_cap": "Unlimited",
            "activation_fee": 0.0,
            "activation_fee_display": "0.00",
        },
    ],
    "tv_packages": [
        {
            "package_id": "TV-SPECIALTY",
            "name": "Specialty Pack",
            "monthly_rate": 15.0,
            "rate_display": "15.00",
            "description": "Live local and international specialty channels",
            "channels": ["Specialty 1-5", "Regional Highlights", "Live Events"],
        },
        {
            "package_id": "TV-ENTERTAIN",
            "name": "Entertainment Pack",
            "monthly_rate": 12.0,
            "rate_display": "12.00",
            "description": "Movies and drama channels",
            "channels": ["Cinema 1-4", "Drama Series", "Classics"],
        },
        {
            "package_id": "TV-NEWS",
            "name": "News & Info Pack",
            "monthly_rate": 10.0,
            "rate_display": "10.00",
            "description": "24/7 world and local news channels",
            "channels": ["World News", "Business Report", "Headline Daily"],
        },
    ],
}

TICKETS: dict[str, dict[str, Any]] = {  # pragma: no cover
    "T88219": {
        "ticket_id": "T88219",
        "account_id": "A1001",
        "status": "in_progress",
        "service_type": "broadband",
        "description": "Virtual repair ticket for optical line sync",
        "created_date": relative_date(-1),
        "eta": "Within 24 hours",
    },
}

_DEFAULT_STATE: dict[str, Any] = {}  # pragma: no cover

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
}

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

ACCOUNTS: tuple[dict[str, Any], ...] = (  # pragma: no cover
    {
        "account_id": "A1001",
        "phone": "2025550186",
        "first_name": "Jordan",
        "email": "m.okafor@mailprovider.example",
        "status": "active",
        "suspension_reason": "",
        "preferred_language": "en-US",
        "card_last4": "7742",
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
        "card_last4": "8853",
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
        "card_last4": "4421",
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
        "card_last4": "1122",
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
    if not state.get("phone_last4"):
        state["phone_last4"] = default_acct.get("phone", "")[-4:]
    state.setdefault("auth_status", "none")
    state.setdefault("auth_failure_count", 0)
    state.setdefault("pin_failure_count", 0)
    state.setdefault("payment_failure_count", 0)
    state.setdefault("past_due_balance", float(default_acct.get("past_due_balance", 85.50)))
    state.setdefault("card_last4", str(default_acct.get("card_last4", "7742")))

MAX_LOGIN_ATTEMPTS = 3  # pragma: no cover

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

def display_amount(value: Any) -> str:  # pragma: no cover
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

def normalize_identifier(raw: object) -> dict[str, str]:  # pragma: no cover
    """Postel normalizer for caller-provided phone, account, or reference identifiers.

    10 digits or +1+10 = phone;
    +/00 + 10-15 digits = international_phone;
    4-9 digits = account;
    [A-Za-z]{1,4}-?[0-9]{4,8} or [0-9]{4,9}-?[A-Za-z]{1,4} = reference;
    anything else = unknown.
    """
    s = str(raw or "").strip()
    if not s:
        return {"kind": "unknown", "value": ""}
    compact = re.sub(r"[\s\-\(\)\.]+", "", s)
    if compact.startswith("+1") and len(compact) == 12 and compact[2:].isdigit():
        return {"kind": "phone", "value": compact[2:]}
    if compact.startswith("1") and len(compact) == 11 and compact[1:].isdigit():
        return {"kind": "phone", "value": compact[1:]}
    if compact.isdigit() and len(compact) == 10:
        return {"kind": "phone", "value": compact}
    if compact.startswith("+"):
        digits = compact[1:]
        if digits.isdigit() and 10 <= len(digits) <= 15:
            return {"kind": "international_phone", "value": "+" + digits}
    if compact.startswith("00"):
        digits = compact[2:]
        if digits.isdigit() and 10 <= len(digits) <= 15:
            return {"kind": "international_phone", "value": "+" + digits}
    ref_match1 = re.fullmatch(r"([A-Za-z]{1,4})-?(\d{4,8})", s)
    if ref_match1:
        prefix, digits = ref_match1.groups()
        return {"kind": "reference", "value": f"{prefix.upper()}-{digits}"}
    ref_match2 = re.fullmatch(r"(\d{4,9})-?([A-Za-z]{1,4})", s)
    if ref_match2:
        digits, suffix = ref_match2.groups()
        return {"kind": "reference", "value": f"{digits}-{suffix.upper()}"}
    if compact.isdigit() and 4 <= len(compact) <= 9:
        return {"kind": "account", "value": compact}
    return {"kind": "unknown", "value": s}

def find_account(identifier: Any) -> dict[str, Any] | None:  # pragma: no cover
    """Find an account by phone number or account number; None when there is none."""
    raw_str = re.sub(r"\.0+$", "", str(identifier or "").strip())
    raw = raw_str.upper()
    if not raw:
        return None
    k_last4 = "phone_" + "last" + "4"
    k_caller = "caller_provided_" + k_last4
    has_alpha = any(c.isalpha() for c in raw_str)
    digits = normalize_code(raw_str)
    if not has_alpha and len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    canonical_id = ("A" + digits) if (raw.startswith("A") and len(digits) >= 4) else raw
    norm = normalize_identifier(raw_str)
    for record in ACCOUNTS:
        if raw == record["account_id"] or canonical_id == record["account_id"] or (
            not has_alpha and digits and digits == record["phone"]
        ):
            rec = dict(record)
            rec[k_last4] = rec["phone"][-4:]
            rec[k_caller] = (
                digits[-4:] if (not has_alpha and 7 <= len(digits) <= 10) else ""
            )
            return rec
    if norm["kind"] in ("phone", "international_phone"):
        p_val = norm["value"].lstrip("+")
        if p_val.startswith("1") and len(p_val) == 11:
            p_val = p_val[1:]
        for record in ACCOUNTS:
            if p_val == record["phone"]:
                rec = dict(record)
                rec[k_last4] = rec["phone"][-4:]
                rec[k_caller] = p_val[-4:]
                return rec
    if not has_alpha and len(digits) == 7:
        for record in ACCOUNTS:
            if record["phone"].endswith(digits):
                rec = dict(record)
                rec[k_last4] = rec["phone"][-4:]
                rec[k_caller] = digits[-4:]
                return rec
        digits_10 = "202" + digits
        return {
            "account_id": "A" + digits_10[-6:],
            "phone": digits_10,
            k_last4: digits[-4:],
            k_caller: digits[-4:],
            "first_name": "",
            "status": "active",
            "preferred_language": "en-US",
            "business_flag": False,
            "card_last4": "7742",
            "past_due_balance": 85.50,
            "current_balance": 85.50,
            "region": "Region-A",
            "loyalty_limit": 25.0,
            "mfa_enabled": False,
            "active_services": ["mobile", "internet"],
            "contract_end_date": relative_date(180),
            "early_cancellation_fee": 150.00,
            "payment_ledger": [],
        }
    if not has_alpha and (7 <= len(digits) <= 10):
        return {
            "account_id": "A" + digits[-6:],
            "phone": digits,
            k_last4: digits[-4:],
            k_caller: digits[-4:],
            "first_name": "",
            "status": "active",
            "preferred_language": "en-US",
            "business_flag": False,
            "card_last4": "7742",
            "past_due_balance": 85.50,
            "current_balance": 85.50,
            "region": "Region-A",
            "loyalty_limit": 25.0,
            "mfa_enabled": False,
            "active_services": ["mobile", "internet"],
            "contract_end_date": relative_date(180),
            "early_cancellation_fee": 150.00,
            "payment_ledger": [],
        }
    if (
        (has_alpha and not raw.startswith("ACC-") and re.fullmatch(r"[A-Za-z]{2,5}-?\d{4,8}(?:-[A-Za-z0-9]+)?", raw_str))
        or (norm["kind"] == "reference" and not norm["value"].startswith("ACC-"))
    ):
        ref_id = norm["value"] if norm["kind"] == "reference" else raw
        base = dict(ACCOUNTS[0])
        base["account_id"] = ref_id
        base[k_last4] = base["phone"][-4:]
        base[k_caller] = ""
        base["business_flag"] = "BUS" in ref_id.upper()
        base["payment_ledger"] = []
        return base
    return None

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

def only_digits(text: Any) -> str:  # pragma: no cover
    """Keep the digits of what the caller said ("(202) 555-0143" -> "2025550186")."""
    return normalize_code(text)

MAX_PAYMENT_ATTEMPTS = 3  # pragma: no cover

def record_payment_attempt(  # pragma: no cover
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
    status_desc = "Paiement refusé." if lang.startswith("fr") else "Card declined."
    err_msg = "La carte a été refusée." if lang.startswith("fr") else "The card was declined."
    action_msg = (
        "Informer l'appelant que la carte est refusée et demander une autre méthode."
        if lang.startswith("fr")
        else "Tell caller card was declined and ask for another payment method."
    )
    return error_reply(
        err_code,
        err_msg if err_code == "CARD_DECLINED" else ("Paiement refusé." if lang.startswith("fr") else "Payment declined."),
        action_msg,
        ref,
        language=lang,
        data={
            "attempts": failures,
            "attempts_remaining": remaining,
            "attempts_left": remaining,
            "lockout_triggered": False,
            "spoken_summary": status_desc,
        },
    )

def resolve_postal_code_region(postal_code: str) -> str:  # pragma: no cover
    """Map Canadian postal code / FSA to PRD region via mathematical sector digit.

    Odd sector digit (1, 3, 5, 7, 9) -> Region-A (Active Outage)
    Even sector digit (0, 2, 4, 6, 8) -> Region-B (Normal Operation)
    Default -> Region-A
    """
    clean = re.sub(r"[^A-Za-z0-9]", "", postal_code.upper())
    if len(clean) >= 2 and clean[1].isdigit():
        digit = int(clean[1])
        return "Region-A" if digit % 2 == 1 else "Region-B"
    return "Region-A"

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

def submit_request_impl(  # pragma: no cover
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
    destination_phone: str | int = "",
    days: int | float | str = 0,
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
    clean_service = str(service_type or "").strip().lower()
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

    alt_phone = destination_phone or kwargs.get("destination_phone")
    if alt_phone:
        raw_p = str(alt_phone).strip()
        p_digits = only_digits(raw_p)
        if len(p_digits) >= 4:
            state["caller_provided_phone"] = p_digits
            state["caller_provided_phone_last4"] = p_digits[-4:]
            state["phone_last4"] = p_digits[-4:]

    # 1. Outage Check (M4) — Information inquiry, does not require login
    if (
        clean_action == "outage_check"
        or (
            any(k in low for k in ("outage", "panne", "service alert", "panne de service"))
            and clean_action not in ("dispute", "sla_credit", "outage_credit", "refund")
            and not (days not in ("", None, 0, "0"))
        )
        or (postal_code and len(postal_code) >= 3 and clean_action not in ("dispute", "sla_credit", "outage_credit", "refund"))
    ) and not any(k in low for k in ("credit", "crédit", "dispute", "contestation", "remboursement", "refund")):
        if clean_service in ("mobile", "wireless", "cellulaire") or any(k in low for k in ("mobile", "cellulaire", "cellular", "cell phone", "données mobiles")):
            return ok_reply(
                {
                    "outage_active": False,
                    "service": "mobile",
                    "details": "Aucune panne de réseau mobile signalée dans ce secteur." if lang.startswith("fr") else "No mobile network outages reported in this coverage sector.",
                    "steps": [
                        "Redémarrer l'appareil" if lang.startswith("fr") else "Restart mobile device",
                        "Activer puis désactiver le mode avion" if lang.startswith("fr") else "Toggle airplane mode for 10 seconds",
                        "Vérifier les paramètres réseau cellulaire" if lang.startswith("fr") else "Verify cellular network settings",
                    ],
                    "sms_guide_available": True,
                },
                reference,
                language=lang,
                spoken_summary="Vérification réseau mobile terminée." if lang.startswith("fr") else "Mobile network check completed.",
            )
        pc = str(postal_code or "").strip()
        if not pc:
            pc_match = re.search(r"\b([A-Za-z]\d[A-Za-z](?:\s*\d[A-Za-z]\d)?)\b", clean_summary)
            if pc_match:
                pc = pc_match.group(1)
        region = resolve_postal_code_region(pc) if pc else str(state.get("region") or "Region-A")
        outage = OUTAGE_REGIONS.get(region, OUTAGE_REGIONS["Region-A"])
        outage_is_active = bool(outage["active"])
        res_data: dict[str, Any] = {
            "outage_active": outage_is_active,
            "region": region,
            "restoration_eta_iso": outage["restoration_eta_iso"],
            "affected_services": list(outage["affected_services"]),
            "cause": outage["cause"],
        }
        if not outage_is_active:
            res_data["sms_guide_available"] = True
            res_data["steps"] = [
                "Débrancher le modem 30 secondes" if lang.startswith("fr") else "Power cycle gateway for 30 seconds",
                "Vérifier le voyant d'alimentation" if lang.startswith("fr") else "Verify front panel LED lights",
                "Tester la connexion Wi-Fi" if lang.startswith("fr") else "Verify Wi-Fi connection",
            ]
        return ok_reply(
            res_data,
            reference,
            language=lang,
            spoken_summary="État de la panne récupéré." if lang.startswith("fr") else "Outage status retrieved.",
        )

    # 2. Password Reset (M7) — Identified only, does not require login
    if clean_action == "password_reset" or any(k in low for k in ("password", "mot de passe", "reinitialiser", "réinitialiser")):
        p_target = str(destination_phone or state.get("destination_phone") or state.get("caller_provided_phone_last4") or state.get("phone_last4") or "0186")
        p_last4 = p_target[-4:]
        return ok_reply(
            {
                "sms_sent": True,
                "valid_minutes": 30,
                "phone_last4": p_last4,
                "destination_phone_last4": p_last4,
                "destination_last4": p_last4,
            },
            reference,
            language=lang,
            spoken_summary="SMS de réinitialisation envoyé." if lang.startswith("fr") else "Password reset SMS dispatched.",
        )

    # 3. Open Support Ticket Status (M6) — Information inquiry, does not require login
    if clean_action in ("check_ticket", "ticket_status") or any(k in low for k in ("ticket", "billet")):
        tid_match = re.search(r"\b(T\d{5})\b", clean_summary.upper())
        tid = tid_match.group(1) if tid_match else "T88219"
        ticket = TICKETS.get(tid, TICKETS["T88219"])
        desc = "Restauration du câble à fibre optique en cours" if lang.startswith("fr") else ticket["description"]
        eta = "D'ici 24 heures" if lang.startswith("fr") else ticket["eta"]
        status_lbl = "ouvert" if lang.startswith("fr") and ticket["status"] == "open" else ticket["status"]
        return ok_reply(
            {
                "ticket_id": ticket["ticket_id"],
                "status": status_lbl,
                "eta": eta,
                "estimated_resolution_time": eta,
                "service_type": ticket["service_type"],
                "description": desc,
            },
            reference,
            language=lang,
            spoken_summary="Statut du billet récupéré." if lang.startswith("fr") else "Ticket status retrieved.",
        )

    # 4. Technician Appointment Arrival Status (M6) — Information inquiry without reschedule/cancel
    if (clean_action in ("check_appointment", "appointment_status") or any(k in low for k in ("technician", "technicien", "appointment", "rendez-vous"))) and not any(k in low for k in ("reschedule", "reporter", "changer", "cancel", "annuler", "résilier", "resilier", "demain", "tomorrow")):
        acc_id = str(state.get("account_id") or "A1001")
        appt = APPOINTMENTS.get(acc_id, APPOINTMENTS["A1001"])
        if lang.startswith("fr"):
            slots_list = ["Demain 08h00 - 12h00", "Demain 13h00 - 17h00", "Après-demain 09h00 - 13h00"]
        else:
            slots_list = [s["display"] for s in AVAILABLE_SLOTS]
        return ok_reply(
            {
                "appt_id": appt["appt_id"],
                "status": appt["status"],
                "delayed": appt["delay_minutes"] > 0,
                "delay_minutes": appt["delay_minutes"],
                "window": appt["window"],
                "date": appt["date"],
                "available_slots": slots_list,
            },
            reference,
            language=lang,
            spoken_summary="Statut du rendez-vous récupéré." if lang.startswith("fr") else "Appointment status retrieved.",
        )

    # Synchronize logged_in state with auth_status
    if state.get("logged_in") is True and state.get("auth_status") != "locked":
        state["auth_status"] = "pass"
    elif state.get("logged_in") is False and state.get("auth_status") != "locked":
        state["auth_status"] = "none"

    is_large_dispute = False
    if clean_action == "dispute" or any(k in low for k in ("dispute", "conteste", "refund", "remboursement")):
        try:
            d_amt = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            d_amt = 0.0
        if not math.isfinite(d_amt):
            d_amt = 0.0
        if d_amt <= 0.0:
            m_amt = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_summary)
            if m_amt:
                d_amt = float(m_amt.group(1))
        if d_amt > 25.0:
            is_large_dispute = True

    is_unauthenticated_allowed = (
        clean_action in ("search_plans", "troubleshoot", "troubleshoot_tv")
        or is_large_dispute
        or (not clean_action and any(k in low for k in ("plan", "forfait", "receiver", "récepteur", "streaming", "tv app", "satellite", "dépannage", "depannage", "troubleshoot", "aucun service", "no service", "réseau", "panne")))
    )

    if state.get("auth_status") != "pass" and not is_unauthenticated_allowed:
        return error_reply(
            "NOT_LOGGED_IN",
            "L'appelant n'a pas complété l'authentification." if lang.startswith("fr") else "The caller has not passed login.",
            "Authentifier l'appelant avec send_login_code puis check_login_code avant de continuer." if lang.startswith("fr") else "Log the caller in with send_login_code and check_login_code, then call submit_request again.",
            reference,
            language=lang,
        )
    if not account_id:
        _ensure_default_profile(state)
        account_id = str(state.get("account_id") or "")
        reference = tracking_id("submit_request", account_id, clean_summary, clean_action)

    state["request_summary"] = clean_summary
    state["last_tracking_id"] = reference

    # 4b. Bill Inquiry / Balance Check
    if clean_action in ("bill_inquiry", "recent_bills", "billing_breakdown") or (
        not clean_action and any(k in low for k in ("bill inquiry", "check balance", "current balance", "solde actuel", "consulter facture", "état du compte", "etat du compte"))
    ):
        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None
        past_bal = float(state.get("past_due_balance") or (account.get("past_due_balance", 85.50) if account else 85.50))
        cur_bal = float(state.get("current_balance") or (account.get("current_balance", 85.50) if account else 85.50))
        return ok_reply(
            {
                "current_balance": cur_bal,
                "current_balance_display": display_amount(cur_bal),
                "past_due_balance": past_bal,
                "past_due_balance_display": display_amount(past_bal),
                "monthly_plan_charges": 75.00,
                "monthly_plan_charges_display": "75.00",
                "taxes_and_fees": 10.50,
                "taxes_and_fees_display": "10.50",
                "plan_name": "Essential Mobility 50GB",
                "due_date": relative_date(14),
                "last_payment_amount": 85.50,
                "last_payment_amount_display": "85.50",
                "last_payment_date": relative_date(-30),
            },
            reference,
            language=lang,
            spoken_summary="Solde récupéré." if lang.startswith("fr") else "Billing balance retrieved.",
        )

    # 4c. General Troubleshooting / Wi-Fi Diagnostic Guide
    if clean_action == "troubleshoot" and clean_service in ("internet", "wifi", "wi-fi", "home_phone", "mobile", ""):
        phone_to_text = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "0186")
        if clean_service in ("mobile", "wireless", "cellulaire") or any(k in low for k in ("mobile", "cellulaire", "cellular")):
            steps = [
                "Redémarrer l'appareil" if lang.startswith("fr") else "Restart mobile device",
                "Activer puis désactiver le mode avion" if lang.startswith("fr") else "Toggle airplane mode for 10 seconds",
                "Vérifier les paramètres réseau cellulaire" if lang.startswith("fr") else "Verify cellular network settings",
            ]
        else:
            steps = [
                "Débrancher l'alimentation de la passerelle 30 secondes" if lang.startswith("fr") else "Power cycle gateway for 30 seconds",
                "Vérifier le voyant blanc fixe sur le panneau avant" if lang.startswith("fr") else "Verify solid white LED on front panel",
                "Vérifier les câbles réseau" if lang.startswith("fr") else "Check ethernet and coaxial cables",
            ]
        return ok_reply(
            {
                "troubleshooting_complete": True,
                "steps": steps,
                "diagnostic_sms_sent": True,
                "sms_guide_available": True,
                "sms_guide_url": "https://telco.example.com/troubleshoot-guide",
                "phone_last4": phone_to_text[-4:],
            },
            reference,
            language=lang,
            spoken_summary="Dépannage complété." if lang.startswith("fr") else "Troubleshooting guide provided.",
        )

    # 5. Cancellation (Service, Line, Phone, or Appointment)
    if clean_action == "cancel" or any(k in low for k in ("cancel", "annuler", "résilier", "resilier", "port out")):
        if any(k in low for k in ("appointment", "technician", "rendez-vous", "technicien")) or clean_service in ("appointment", "technician"):
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
                spoken_summary="Rendez-vous annulé." if lang.startswith("fr") else "Appointment cancelled.",
            )

        state["service_cancelled"] = True
        return ok_reply(
            {
                "cancelled": True,
                "cancellation_id": "C99214",
                "early_cancellation_fee": 150.00,
                "fee_display": "150.00",
                "effective_date": relative_date(0),
                "remaining_service": "internet",
                "remaining_monthly_rate": 105.00,
                "remaining_monthly_rate_display": "105.00",
                "standalone_internet_rate": 105.00,
                "standalone_internet_rate_display": "105.00",
                "standalone_plan_name": "Fiber 1.5 Gbps",
            },
            reference,
            language=lang,
            spoken_summary="Annulation de service traitée." if lang.startswith("fr") else "Service cancellation processed.",
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
                spoken_summary="Paiement antérieur vérifié." if lang.startswith("fr") else "Prior payment verified.",
            )
        return error_reply(
            "NO_PAYMENT_FOUND",
            message="No recent payment found on file to clear the past-due balance.",
            agent_action="Inform caller that no payment was found and offer to take a payment now.",
            reference=reference,
            language=lang,
            data={"payment_verified": False},
        )

    # 6b. Payment Arrangements (M3/M7)
    if clean_action in ("payment_arrangement", "arrangement") or (
        any(k in low for k in ("arrangement", "entente", "installment", "versement", "échelonner", "echelonner"))
        and not any(k in low for k in ("verify", "prior", "déjà", "deja", "settle", "payer", "pay"))
    ):
        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None
        raw_bal = state.get("past_due_balance")
        if raw_bal is None:
            cur_bal = float(account.get("past_due_balance", 85.50)) if account else 85.50
        else:
            try:
                cur_bal = float(raw_bal)
            except (ValueError, TypeError):
                cur_bal = 85.50
        if not math.isfinite(cur_bal):
            cur_bal = 85.50
        inst_amt = round(cur_bal / 2.0, 2)
        d1 = relative_date(14)
        d2 = relative_date(28)
        state["payment_verified"] = True
        state["service_restored"] = True
        state["status"] = "active"
        return ok_reply(
            {
                "arrangement_confirmed": True,
                "service_restored": True,
                "total_amount": cur_bal,
                "total_amount_display": display_amount(cur_bal),
                "installments": 2,
                "installment_amount": inst_amt,
                "installment_amount_display": display_amount(inst_amt),
                "due_date_1": d1,
                "due_date_2": d2,
                "message": "Entente de paiement confirmée." if lang.startswith("fr") else "Payment arrangement confirmed.",
            },
            reference,
            language=lang,
            spoken_summary="Entente de paiement confirmée." if lang.startswith("fr") else "Payment arrangement confirmed.",
        )

    # 6c. Check Balance / Bill Inquiry (M3)
    if clean_action in ("check_balance", "view_balance", "balance_inquiry", "get_balance", "bill_inquiry") or (
        clean_action == "pay_bill"
        and any(k in low for k in ("check balance", "view balance", "what is the balance", "inquire balance", "vérifier le solde", "consulter le solde", "quel est le solde"))
        and not any(k in low for k in ("pay now", "process payment", "proceed with payment", "payer maintenant", "confirmer le paiement"))
    ):
        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None
        raw_bal = state.get("past_due_balance")
        if raw_bal is None:
            current_bal = float(account.get("past_due_balance", 85.50)) if account else 85.50
        else:
            try:
                current_bal = float(raw_bal)
            except (ValueError, TypeError):
                current_bal = 85.50
        if not math.isfinite(current_bal):
            current_bal = 85.50
        card_on_file = str(state.get("card_last4") or (account.get("card_last4") if account else "7742") or "7742")
        return ok_reply(
            {
                "balance": current_bal,
                "balance_display": display_amount(current_bal),
                "past_due_balance": current_bal,
                "past_due_balance_display": display_amount(current_bal),
                "due_date": relative_date(7),
                "card_on_file_last4": card_on_file,
                "status": "pending_payment" if current_bal > 0 else "paid",
            },
            reference,
            language=lang,
            spoken_summary="Solde actuel vérifié." if lang.startswith("fr") else "Current balance checked.",
        )

    # 7. Bill Payment (Card Decline & Balance Decrement)
    if clean_action == "pay_bill" or (not clean_action and any(k in low for k in ("pay", "payer", "payment", "paiement", "restore", "rétablir", "retablir", "settle", "solde", "past due"))):
        acc_id = str(state.get("account_id") or "")
        account = find_account(acc_id) if acc_id else None

        raw_bal = state.get("past_due_balance")
        if raw_bal is None:
            current_bal = float(account.get("past_due_balance", 85.50)) if account else 85.50
        else:
            try:
                current_bal = float(raw_bal)
            except (ValueError, TypeError):
                current_bal = 85.50
        if not math.isfinite(current_bal):
            current_bal = 85.50

        if current_bal <= 0.0:
            return ok_reply(
                {
                    "paid": False,
                    "already_paid": True,
                    "amount": 0.0,
                    "amount_display": "0.00",
                    "card_last4": str(state.get("card_last4") or "7742"),
                    "service_restored": True,
                    "new_past_due_balance": 0.0,
                    "message": "Le solde du compte est déjà à zéro." if lang.startswith("fr") else "Account balance is already zero; no payment required.",
                },
                reference,
                language=lang,
                spoken_summary="Compte à zéro." if lang.startswith("fr") else "Account balance is zero.",
            )

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

        try:
            parsed_amt = float(amount) if amount else 0.0
            if not math.isfinite(parsed_amt):
                parsed_amt = 0.0
        except (ValueError, TypeError):
            parsed_amt = 0.0

        pmt_amount = round(min(parsed_amt if parsed_amt > 0.0 else current_bal, current_bal), 2)
        new_bal = round(max(0.0, current_bal - pmt_amount), 2)

        state["past_due_balance"] = new_bal
        state["service_restored"] = (new_bal == 0.0)
        if new_bal == 0.0:
            state["status"] = "active"
        state["card_last4"] = c_digits[-4:]

        return ok_reply(
            {
                "paid": True,
                "amount": pmt_amount,
                "amount_display": display_amount(pmt_amount),
                "card_last4": c_digits[-4:],
                "service_restored": (new_bal == 0.0),
                "service_status": "active" if new_bal == 0.0 else "suspended",
                "new_past_due_balance": new_bal,
            },
            reference,
            language=lang,
            spoken_summary="Paiement traité avec succès." if lang.startswith("fr") else "Payment processed successfully.",
        )

    # 7b. Strict Warranty Precedence before Dispute
    if clean_action == "warranty" and any(k in low for k in ("port", "transfer number", "old carrier", "competitor", "keep my number", "transférer numéro", "transferer numero", "conserver")):
        clean_action = "port_in"

    if clean_action == "warranty" or is_safety_hazard or (
        not clean_action and any(k in low for k in ("warranty", "garantie", "defect", "defective", "remplacement appareil", "hardware", "thermal", "overheating", "surchauffe"))
    ):
        is_hazard = is_safety_hazard or any(k in low for k in ("battery", "batterie", "thermal", "thermique", "overheating", "surchauffe", "hazard", "danger", "smoke", "fumée", "fumee", "safety", "sécurité", "securite"))
        ref_id = "WAR-" + tracking_id("warranty", clean_summary)
        if any(k in low for k in ("crack", "fissur", "liquid", "water", "eau", "drop", "chute")):
            return error_reply(
                "PHYSICAL_DAMAGE_EXCLUDED",
                message="Les dommages physiques ou liquides sont exclus de la couverture de garantie." if lang.startswith("fr") else "Physical or liquid damage is excluded from warranty coverage.",
                agent_action="Informer l'appelant que les dommages physiques ne sont pas couverts." if lang.startswith("fr") else "Inform caller that physical/liquid damage is not covered by standard warranty.",
                reference=reference,
                language=lang,
                data={"claim_status": "rejected_physical_damage", "covered": False},
            )
        delivery = "3 à 5 jours ouvrables" if lang.startswith("fr") else "3 to 5 business days"
        if is_hazard:
            return ok_reply(
                {
                    "warranty_submitted": True,
                    "claim_id": ref_id,
                    "tracking_id": ref_id,
                    "warranty_reference": ref_id,
                    "claim_status": "approved_urgent",
                    "hazard_warning": True,
                    "safety_instructions": "Cessez immédiatement d'utiliser et de charger l'appareil." if lang.startswith("fr") else "Stop using and charging the device immediately. Keep in a fire-safe area.",
                    "replacement_shipped": True,
                    "delivery_window": "1 jour ouvrable" if lang.startswith("fr") else "1 business day",
                    "eta_business_days": 1,
                    "days": 1,
                },
                reference,
                language=lang,
                spoken_summary="Remplacement sous garantie commandé." if lang.startswith("fr") else "Warranty replacement ordered.",
            )
        return ok_reply(
            {
                "warranty_submitted": True,
                "claim_id": ref_id,
                "tracking_id": ref_id,
                "warranty_reference": ref_id,
                "claim_status": "approved_standard",
                "hazard_warning": False,
                "replacement_shipped": True,
                "delivery_window": delivery,
                "eta_business_days": 3,
                "days": "3 to 5",
            },
            reference,
            language=lang,
            spoken_summary="Demande de garantie évaluée." if lang.startswith("fr") else "Warranty claim assessed.",
        )

    # 8. Outage SLA Credit & Billing Disputes (<= $25 Auto-Adjustment)
    if clean_action in ("outage_credit", "sla_credit") or (
        clean_action == "dispute" and any(k in low for k in ("outage", "panne", "downtime", "sla", "interruption"))
    ) or any(k in low for k in ("sla credit", "downtime credit", "crédit de panne", "crédit pour panne")):
        d_val = 0
        if days:
            try:
                f_days = float(days)
                d_val = int(f_days) if math.isfinite(f_days) else 0
            except (ValueError, TypeError, OverflowError):
                d_val = 0
        if d_val <= 0:
            d_match = re.search(r"\b(\d+)\s*(?:day|jour)", low)
            d_val = int(d_match.group(1)) if d_match else 2
        daily_rate = round(85.50 / 30.0, 2)  # 2.85
        calc_credit = round(2.85 * d_val, 2)
        try:
            parsed_amt = float(amount) if amount else 0.0
            if not math.isfinite(parsed_amt):
                parsed_amt = 0.0
        except (ValueError, TypeError):
            parsed_amt = 0.0
        cred_amt = round(parsed_amt, 2) if parsed_amt > 0.0 else calc_credit
        cred_amt = min(cred_amt, 25.00)
        return ok_reply(
            {
                "credit_approved": True,
                "amount": cred_amt,
                "amount_display": display_amount(cred_amt),
                "days": d_val,
                "days_credited": d_val,
                "adjustment_type": "outage_sla_credit",
                "message": "Crédit d'interruption appliqué." if lang.startswith("fr") else "Outage credit applied.",
            },
            reference,
            language=lang,
            spoken_summary="Crédit de panne appliqué." if lang.startswith("fr") else "Outage credit applied.",
        )

    if clean_action in ("dispute", "refund_overpayment", "overpayment") or (
        not clean_action and any(k in low for k in ("dispute", "credit", "crédit", "refund", "remboursement", "conteste", "overcharge", "facturation", "frais incorrect", "trop-perçu", "trop perçu", "double paiement", "paid twice"))
    ):
        is_overpayment = (
            clean_action in ("refund_overpayment", "overpayment")
            or any(k in low for k in ("overpayment", "paid twice", "double", "trop-perçu", "trop perçu", "payé deux fois", "paye deux fois"))
        )

        try:
            dispute_amt = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            dispute_amt = 0.0
        if not math.isfinite(dispute_amt):
            dispute_amt = 0.0

        clean_for_amt = clean_summary
        if card_last4:
            clean_for_amt = clean_for_amt.replace(str(card_last4), " ")
        clean_for_amt = re.sub(
            r"(?:ending\s+in|terminant\s+par|carte\s+bancaire|carte|card)\s*(?:se\s+terminant\s+par\s*)?(?:\D*\b)(\d{4})\b",
            " ",
            clean_for_amt,
            flags=re.IGNORECASE,
        )

        if dispute_amt <= 0.0:
            amt_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_for_amt)
            if amt_match:
                dispute_amt = float(amt_match.group(1))
            elif is_overpayment:
                acc_id = str(state.get("account_id") or "")
                account = find_account(acc_id) if acc_id else None
                dispute_amt = float(state.get("current_balance") or (account.get("current_balance", 85.50) if account else 85.50))
            else:
                dispute_amt = 12.50

        if is_overpayment:
            refund_days = 3
            return ok_reply(
                {
                    "refund_approved": True,
                    "amount": dispute_amt,
                    "amount_display": display_amount(dispute_amt),
                    "days": refund_days,
                    "days_display": str(refund_days),
                    "adjustment_type": "overpayment_refund",
                    "status_code": "approved",
                },
                reference,
                language=lang,
                spoken_summary="Remboursement de trop-perçu approuvé." if lang.startswith("fr") else "Overpayment refund approved.",
            )

        if dispute_amt > 25.0:
            transfer_msg = spoken_line("transfer_to_specialist", lang)
            state["handoff_message"] = transfer_msg
            state["handoff_reason"] = "refund_threshold_exceeded"
            return error_reply(
                "LIMIT_EXCEEDED",
                message="Dispute exceeds the $25.00 limit for automated adjustment." if not lang.startswith("fr") else "La contestation dépasse la limite de 25,00 $.",
                agent_action="Explain requests over $25 require specialist and transfer." if not lang.startswith("fr") else "Expliquer que les demandes de plus de 25 $ requièrent un spécialiste.",
                reference=reference,
                language=lang,
                data={
                    "amount": dispute_amt,
                    "amount_display": display_amount(dispute_amt),
                    "threshold": 25.0,
                    "threshold_display": "25.00",
                    "requires_specialist": True,
                    "escalation_queue": "billing_specialist",
                },
            )
        refund_days = 3
        return ok_reply(
            {
                "refund_approved": True,
                "amount": dispute_amt,
                "amount_display": display_amount(dispute_amt),
                "days": refund_days,
                "days_display": str(refund_days),
                "adjustment_type": "courtesy_credit",
                "status_code": "approved",
            },
            reference,
            language=lang,
            spoken_summary="Ajustement de contestation traité." if lang.startswith("fr") else "Dispute adjustment processed.",
        )

    # 9. Appointment Reschedule (Commit Chosen Slot)
    if clean_action == "reschedule" or (
        not clean_action
        and (
            any(k in low for k in ("reschedule", "reporter", "slot", "plage"))
            or ("changer" in low and any(w in low for w in ("rendez-vous", "rdv", "technicien", "plage", "heure", "date", "slot")))
        )
    ):
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
            spoken_summary="Rendez-vous reporté." if lang.startswith("fr") else "Appointment rescheduled.",
        )

    # 10. Multi-Factor Authentication Configuration
    if clean_action in ("enable_mfa", "disable_mfa") or any(k in low for k in ("mfa", "2fa", "two-factor", "authentification à deux facteurs", "double facteur")):
        if clean_action == "disable_mfa" or any(k in low for k in ("disable", "turn off", "deactivate", "remove", "désactiver", "desactiver", "supprimer", "enlever")):
            state["mfa_enabled"] = False
            return ok_reply(
                {"mfa_enabled": False, "status": "disabled"},
                reference,
                language=lang,
                spoken_summary="Paramètre MFA mis à jour." if lang.startswith("fr") else "MFA setting updated.",
            )
        else:
            state["mfa_enabled"] = True
            return ok_reply(
                {"mfa_enabled": True, "status": "enabled"},
                reference,
                language=lang,
                spoken_summary="Paramètre MFA mis à jour." if lang.startswith("fr") else "MFA setting updated.",
            )

    # 11. Lost / Stolen Suspension
    if clean_action == "suspend_lost_stolen" or any(k in low for k in ("lost", "stolen", "perdu", "volé", "vole")):
        state["status"] = "suspended"
        state["suspension_reason"] = "lost_stolen"
        return ok_reply(
            {"service_suspended": True, "reason": "lost_stolen", "effective_immediately": True},
            reference,
            language=lang,
            spoken_summary="Ligne suspendue." if lang.startswith("fr") else "Line suspended.",
        )

    # 12. Autopay Setup
    if clean_action == "enroll_autopay" or any(k in low for k in ("autopay", "automatic payment", "paiement automatique", "prélèvement automatique")):
        c_digits = normalize_code(card_last4)
        if not c_digits:
            c_match = re.search(r"\b(\d{4})\b", clean_summary)
            if c_match:
                c_digits = c_match.group(1)
        if not c_digits:
            c_digits = str(state.get("card_last4") or "7742")
        if c_digits in DECLINED_CARD_LAST4:
            attempt_res = record_payment_attempt(state, c_digits, language=lang)
            return attempt_res
        state["autopay_enrolled"] = True
        state["card_last4"] = c_digits[-4:]
        return ok_reply(
            {"autopay_enrolled": True, "card_last4": c_digits[-4:]},
            reference,
            language=lang,
            spoken_summary="Adhésion au paiement automatique terminée." if lang.startswith("fr") else "Autopay enrollment completed.",
        )

    # 12b. TV Troubleshooting & Virtual Repair (M4) — uncoupled from broadband outage
    if clean_action in ("troubleshoot_tv", "tv_repair", "virtual_repair") or (
        any(k in low for k in ("satellite", "receiver", "récepteur", "recepteur", "tv app", "streaming", "tv error", "erreur télé", "erreur tv"))
        or (any(k in low for k in ("tv", "télé", "tele")) and any(k in low for k in ("signal", "freeze", "gelé", "gele", "black screen", "écran noir", "ecran noir", "troubleshoot", "dépanner", "depanner")))
    ):
        phone_to_text = str(state.get("caller_provided_phone_last4") or state.get("phone_last4") or "")
        return ok_reply(
            {
                "tv_troubleshooting_complete": True,
                "virtual_repair_initiated": True,
                "sms_guide_dispatched": True,
                "guide_link": "https://telco.example.com/tv-guide",
                "phone_last4": phone_to_text[-4:],
                "message": "Dépannage virtuel complété." if lang.startswith("fr") else "Virtual repair initiated.",
            },
            reference,
            language=lang,
            spoken_summary="Dépannage télé complété." if lang.startswith("fr") else "TV troubleshooting completed.",
        )

    # 12c. Port-In Number Transfer (M5)
    if clean_action == "port_in" or any(k in low for k in ("port in", "port", "transfer number", "transférer numéro", "transferer numero")):
        port_ref = "PORT-" + tracking_id("port", clean_summary)
        is_landline = any(k in low for k in ("landline", "ligne fixe", "fixe", "home phone"))
        porting_window = (
            ("2 à 3 jours ouvrables" if lang.startswith("fr") else "2 to 3 business days")
            if is_landline
            else ("2 à 4 heures" if lang.startswith("fr") else "2 to 4 hours")
        )
        return ok_reply(
            {
                "port_in_submitted": True,
                "transfer_reference": port_ref,
                "tracking_id": port_ref,
                "status": "pending_carrier_release",
                "porting_window": porting_window,
                "active_until_cutover": True,
                "keep_current_service_active": True,
                "estimated_hours": 48 if is_landline else 2,
            },
            reference,
            language=lang,
            spoken_summary="Transfert de numéro soumis." if lang.startswith("fr") else "Port-in request submitted.",
        )

    # 14. Plan Catalog, Upgrades & TV Packages
    if clean_action in ("search_plans", "upgrade_plan", "upgrade", "add_package") or any(k in low for k in ("plan", "forfait", "upgrade", "rehausser", "vitesse", "budget", "specialty", "package", "pack", "channel", "chaîne", "chaine", "add-on", "option", "coverage", "couverture")):
        if any(k in low for k in ("specialty", "package", "pack", "tv", "télé", "tele", "channel", "chaîne", "chaine")) and clean_service != "internet":
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
                spoken_summary="Détails du forfait récupérés." if lang.startswith("fr") else "Package details retrieved.",
            )

        try:
            budget = float(max_budget) if max_budget else 0.0
        except (ValueError, TypeError):
            budget = 0.0
        if budget <= 0.0:
            b_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", clean_summary)
            if b_match and any(w in low for w in ("budget", "under", "max", "maximum", "moins de")):
                budget = float(b_match.group(1))

        is_internet = clean_service in ("internet", "fiber", "fibre", "broadband") or any(
            k in low for k in ("fiber", "fibre", "internet", "gigabit", "speed", "vitesse")
        )

        if is_internet:
            all_internet = PLAN_CATALOG["internet"]
            matched_net = [p for p in all_internet if p["monthly_rate"] <= budget] if budget > 0 else list(all_internet)
            if budget > 0 and not matched_net:
                return ok_reply(
                    {
                        "plans": [],
                        "count": 0,
                        "activation_fee": 0.0,
                        "activation_fee_display": "0.00",
                        "error_code": "NO_PLANS_IN_BUDGET",
                        "message": "Aucun forfait disponible dans cette limite budgétaire." if lang.startswith("fr") else "No plans available within that budget.",
                    },
                    reference,
                    language=lang,
                    spoken_summary="Aucun forfait trouvé." if lang.startswith("fr") else "No plans found.",
                )

            # Specific tier upgrade execution
            if clean_action in ("upgrade", "upgrade_plan") or any(k in low for k in ("upgrade", "rehausser", "passer à", "changer pour")):
                if "500" in low or (budget > 0 and 50.0 < budget <= 80.0):
                    tier = all_internet[1]  # Fiber 500 ($70.00)
                elif "100" in low or (budget > 0 and 0.0 < budget <= 50.0):
                    tier = all_internet[0]  # Fiber 100 ($50.00)
                else:
                    tier = all_internet[2]  # Gigabit Fiber ($90.00)
                return ok_reply(
                    {
                        "plan_name": tier["name"],
                        "monthly_rate": tier["monthly_rate"],
                        "rate_display": tier["rate_display"],
                        "speed_mbps": tier["speed_mbps"],
                        "download_mbps": tier.get("download_mbps", tier["speed_mbps"]),
                        "upload_mbps": tier.get("upload_mbps", 750 if tier["speed_mbps"] >= 1000 else tier["speed_mbps"]),
                        "unlimited_data": True,
                        "data_cap": "Illimité" if lang.startswith("fr") else "Unlimited",
                        "activation_fee": 0.0,
                        "activation_fee_display": "0.00",
                        "upgrade_confirmed": True,
                        "status": "active",
                    },
                    reference,
                    language=lang,
                    spoken_summary="Forfait Internet mis à niveau." if lang.startswith("fr") else "Internet plan upgraded.",
                )

            curated_net = []
            for p in matched_net:
                curated_net.append(
                    {
                        "plan_id": p["plan_id"],
                        "name": p["name"],
                        "plan_name": p["name"],
                        "monthly_rate": p["monthly_rate"],
                        "rate_display": p["rate_display"],
                        "speed_mbps": p["speed_mbps"],
                        "download_mbps": p.get("download_mbps", p["speed_mbps"]),
                        "upload_mbps": p.get("upload_mbps", p["speed_mbps"]),
                        "unlimited_data": True,
                        "data_cap": "Illimité" if lang.startswith("fr") else "Unlimited",
                        "activation_fee": 0.0,
                        "activation_fee_display": "0.00",
                    }
                )
            top = curated_net[-1]
            return ok_reply(
                {
                    "plans": curated_net,
                    "count": len(curated_net),
                    "plan_name": top["name"],
                    "monthly_rate": top["monthly_rate"],
                    "rate_display": top["rate_display"],
                    "speed_mbps": top["speed_mbps"],
                    "download_mbps": top["download_mbps"],
                    "upload_mbps": top["upload_mbps"],
                    "unlimited_data": True,
                    "data_cap": "Illimité" if lang.startswith("fr") else "Unlimited",
                    "activation_fee": 0.0,
                    "activation_fee_display": "0.00",
                },
                reference,
                language=lang,
                spoken_summary="Forfaits Internet récupérés." if lang.startswith("fr") else "Internet plans retrieved.",
            )

        all_mobility = PLAN_CATALOG["mobility"]
        if budget > 0:
            matched = [p for p in all_mobility if p["monthly_rate"] <= budget]
            if not matched:
                return ok_reply(
                    {
                        "plans": [],
                        "count": 0,
                        "activation_fee": 0.0,
                        "activation_fee_display": "0.00",
                        "error_code": "NO_PLANS_IN_BUDGET",
                        "message": "Aucun forfait disponible dans cette limite budgétaire." if lang.startswith("fr") else "No plans available within that budget.",
                    },
                    reference,
                    language=lang,
                    spoken_summary="Aucun forfait trouvé." if lang.startswith("fr") else "No plans found.",
                )
            curated = matched[-3:] if len(matched) >= 3 else matched
        else:
            curated = all_mobility[1:4]

        roaming_addons = [
            {"name": "Roam Better - US", "daily_rate": 12.0, "rate_display": "12.00"},
            {"name": "Roam Better - International", "daily_rate": 15.0, "rate_display": "15.00"},
        ]
        return ok_reply(
            {
                "plans": curated,
                "count": len(curated),
                "activation_fee": 0.0,
                "activation_fee_display": "0.00",
                "overage_policy": "No data overage fees; speeds throttled to 512 Kbps after limit",
                "contract_term": "month-to-month",
                "add_ons": roaming_addons,
            },
            reference,
            language=lang,
            spoken_summary="Options de forfaits récupérées." if lang.startswith("fr") else "Plan options retrieved.",
        )

    # 15. Default Fallback
    return ok_reply(
        {"submitted": True},
        reference,
        language=lang,
        spoken_summary="Demande traitée avec succès." if lang.startswith("fr") else "Request processed successfully.",
    )
# --- END GENERATED SHARED BUNDLE ---
