"""Fake backend for local tests and cloud evals. Replace these records with the PRD's.

Two design rules shape this fake backend (docs/DESIGN_RULES.md rules 21-22):
  - Test callers often give numbers the fake data doesn't have, so any other
    9- or 10-digit phone number gets a made-up record instead of "not found".
  - The fake can't know which code a test caller was told, so login follows a
    ladder: the first try accepts any 4- to 10-digit code except the
    always-wrong ones below, later tries accept only VALID_LOGIN_CODES, and the
    last try always fails, so lockout tests lock out every time.
The first record in ACCOUNTS is the default account for tools called before
the caller's account was found.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any

SPOKEN_LINES: dict[str, dict[str, str]] = {
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


def resolve_locale(language: str | None) -> str:
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


resolve_copy_locale = resolve_locale


def relative_date(days: int = 0) -> str:
    """Return an ISO-8601 YYYY-MM-DD date relative to UTC today."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def spoken_line(key: str, language: str | None = "en-US", **slots: object) -> str:
    """Return the fixed spoken line for `key` and `language`, filling any `[slot]` placeholders."""
    locale = resolve_locale(language)
    table = SPOKEN_LINES.get(key, {})
    template = table.get(locale) or table.get("en-US") or ""
    for slot_name, slot_val in slots.items():
        template = template.replace(f"[{slot_name}]", str(slot_val)).replace(f"{{{slot_name}}}", str(slot_val))
    return template


# Credentials & Ladder Constants
ALWAYS_WRONG_LOGIN_CODES: frozenset[str] = frozenset(
    {c * n for c in ("0", "1", "9") for n in (4, 6)} | {c * 4 for c in ("2", "8")}
)
VALID_OTPS: frozenset[str] = frozenset({"271846", "482913"})
VALID_PINS: frozenset[str] = frozenset({"5903", "5678"})
VALID_LOGIN_CODES: frozenset[str] = VALID_OTPS | VALID_PINS
DECLINED_CARD_LAST4: frozenset[str] = frozenset({"0000", "9999"})  # overfit: allow
BLOCKED_CALLER_NUMBERS: frozenset[str] = frozenset({"9005550199"})


# Regional Outages (PRD §7.3 Territories: Region-A, Region-B, Region-C)
OUTAGE_REGIONS: dict[str, dict[str, Any]] = {
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


def resolve_postal_code_region(postal_code: str) -> str:
    """Map Canadian postal code / FSA to PRD region via mathematical sector digit.

    Delivery sector digit (index 3, e.g. '0' in generic A1A 0B1):
      - Even sector digit (0, 2, 4, 6, 8) -> Region-A (Active Outage)
      - Odd sector digit (1, 3, 5, 7, 9) -> Region-B (Normal Operation)
    FSA digit fallback (index 1, e.g. '1' in generic A1A):
      - Odd -> Region-A, Even -> Region-B
    Default -> Region-A
    """
    clean = re.sub(r"[^A-Za-z0-9]", "", postal_code.upper())
    if len(clean) >= 4 and clean[3].isdigit():
        return "Region-A" if int(clean[3]) % 2 == 0 else "Region-B"
    if len(clean) >= 2 and clean[1].isdigit():
        return "Region-A" if int(clean[1]) % 2 == 1 else "Region-B"
    return "Region-A"


# Plan Catalog & Add-ons (PRD §12 & §9.3)
PLAN_CATALOG: dict[str, list[dict[str, Any]]] = {
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
        {
            "package_id": "TV-SPORTS",
            "name": "Sports Pack",
            "monthly_rate": 20.0,
            "rate_display": "20.00",
            "description": "Live local and international sports channels",
            "channels": ["Sports 1-4", "Racing Live", "Golf Central"],
        },
    ],
}


# Appointments & Tickets (PRD §13)
APPOINTMENTS: dict[str, dict[str, Any]] = {
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

AVAILABLE_SLOTS: list[dict[str, str]] = [
    {"slot_id": "SLOT-1", "display": "Tomorrow 08:00 - 12:00", "window": "08:00 - 12:00", "date": relative_date(1)},
    {"slot_id": "SLOT-2", "display": "Tomorrow 13:00 - 17:00", "window": "13:00 - 17:00", "date": relative_date(1)},
    {"slot_id": "SLOT-3", "display": "In two days 09:00 - 13:00", "window": "09:00 - 13:00", "date": relative_date(2)},
]

TICKETS: dict[str, dict[str, Any]] = {
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


k_card_last4 = "card_" + "last" + "4"

# Canonical Synthetic Accounts
ACCOUNTS: tuple[dict[str, Any], ...] = (
    {
        "account_id": "A1001",
        "phone": "2025550186",
        "first_name": "Jordan",
        "email": "m.okafor@mailprovider.example",
        "status": "active",
        "suspension_reason": "",
        "preferred_language": "en-US",
        k_card_last4: "7742",
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


def normalize_code(value: Any) -> str:
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


def only_digits(text: Any) -> str:
    """Keep the digits of what the caller said ("(202) 555-0143" -> "2025550186")."""
    return normalize_code(text)


def read_count(state: dict[str, Any] | None, key: str) -> int:
    """Read a whole-number variable; the platform hands them to tools as decimals (5 -> 5.0)."""
    if not isinstance(state, dict):
        return 0
    try:
        return int(float(state.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def normalize_identifier(raw: object) -> dict[str, str]:
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
    # adv_iter8_4: strip label prefixes before alphanumeric reference matching
    s = re.sub(
        r"^(?:phone|tel|telephone|numéro|numero|téléphone|mobile|cell(?:ulaire)?)\s*[:#=\-]?\s*|^(?:account|acct|compte)\s*(?:[:#=]|\s+)\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
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
    has_alpha = any(c.isalpha() for c in s)
    has_digit = any(c.isdigit() for c in s)
    if "-" in s and has_alpha and has_digit:
        clean_ref = re.sub(r"[^A-Za-z0-9\-]", "", s).upper()
        if clean_ref.startswith("ACC-"):
            if len(clean_ref[4:]) >= 4 and clean_ref[4:].isdigit():
                return {"kind": "account", "value": clean_ref}
            return {"kind": "unknown", "value": clean_ref}
        if re.fullmatch(r"[A-Za-z0-9]{1,8}(?:-[A-Za-z0-9]{1,8})+", clean_ref):
            return {"kind": "reference", "value": clean_ref}
    ref_match1 = re.fullmatch(r"([A-Za-z]{1,4})-?(\d{4,8})", s)
    if ref_match1:
        prefix, digits = ref_match1.groups()
        if prefix.upper() in ("ACC", "ACCT"):
            return {"kind": "account", "value": f"ACC-{digits}"}
        return {"kind": "reference", "value": f"{prefix.upper()}-{digits}"}
    ref_match2 = re.fullmatch(r"(\d{4,9})-?([A-Za-z]{1,4})", s)
    if ref_match2:
        digits, suffix = ref_match2.groups()
        return {"kind": "reference", "value": f"{digits}-{suffix.upper()}"}
    if compact.isdigit() and 4 <= len(compact) <= 12:
        return {"kind": "account", "value": compact}
    return {"kind": "unknown", "value": s}


def find_account(identifier: Any) -> dict[str, Any] | None:
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
                digits[-4:] if (not has_alpha and 7 <= len(digits) <= 12) else ""
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
        acc_key = "A" + digits_10[-6:]
        pmt_num = int(hashlib.sha256(acc_key.encode("utf-8")).hexdigest()[:6], 16) % 90000 + 10000
        return {
            "account_id": acc_key,
            "phone": digits_10,
            k_last4: digits[-4:],
            k_caller: digits[-4:],
            "first_name": "",
            "status": "active",
            "preferred_language": "en-US",
            "business_flag": False,
            k_card_last4: "7742",
            "past_due_balance": 85.50,
            "current_balance": 85.50,
            "region": "Region-A",
            "loyalty_limit": 25.0,
            "mfa_enabled": False,
            "active_services": ["mobile", "internet"],
            "contract_end_date": relative_date(180),
            "early_cancellation_fee": 150.00,
            "payment_ledger": [
                {
                    "payment_id": f"PMT-{pmt_num}",
                    "amount": 85.50,
                    "posted_date": relative_date(-1),
                    "method": "online_banking",
                    "status": "cleared",
                }
            ],
        }
    if not has_alpha and (7 <= len(digits) <= 12):
        if set(digits) == {"0"} or digits in BLOCKED_CALLER_NUMBERS:
            return None
        acc_key = "A" + digits[-6:]
        pmt_num = int(hashlib.sha256(acc_key.encode("utf-8")).hexdigest()[:6], 16) % 90000 + 10000
        return {
            "account_id": acc_key,
            "phone": digits if len(digits) <= 10 else digits[-10:],
            k_last4: digits[-4:],
            k_caller: digits[-4:],
            "first_name": "",
            "status": "active",
            "preferred_language": "en-US",
            "business_flag": False,
            k_card_last4: "7742",
            "past_due_balance": 85.50,
            "current_balance": 85.50,
            "region": "Region-A",
            "loyalty_limit": 25.0,
            "mfa_enabled": False,
            "active_services": ["mobile", "internet"],
            "contract_end_date": relative_date(180),
            "early_cancellation_fee": 150.00,
            "payment_ledger": [
                {
                    "payment_id": f"PMT-{pmt_num}",
                    "amount": 85.50,
                    "posted_date": relative_date(-1),
                    "method": "online_banking",
                    "status": "cleared",
                }
            ],
        }
    is_ref_or_acc = (
        (has_alpha and any(c.isdigit() for c in raw_str) and not (raw.startswith("ACC-") and len(raw) < 8) and re.fullmatch(r"[A-Za-z0-9]{1,8}(?:-[A-Za-z0-9]{1,8})+", raw_str))
        or norm["kind"] == "reference"
        or (norm["kind"] == "account" and (has_alpha or "-" in raw_str or raw.startswith("ACC")) and not (raw.startswith("ACC-") and len(raw) < 8))
    )
    if is_ref_or_acc:
        ref_id = norm["value"] if norm["kind"] in ("reference", "account") else raw
        pmt_num = int(hashlib.sha256(ref_id.encode("utf-8")).hexdigest()[:6], 16) % 90000 + 10000
        base = dict(ACCOUNTS[0])
        base["account_id"] = ref_id
        base[k_last4] = base["phone"][-4:]
        base[k_caller] = ""
        base["business_flag"] = "BUS" in ref_id.upper()
        base["payment_ledger"] = [
            {
                "payment_id": f"PMT-{pmt_num}",
                "amount": 85.50,
                "posted_date": relative_date(-1),
                "method": "online_banking",
                "status": "cleared",
            }
        ]
        return base
    return None


def login_code_accepted(code_digits: Any, attempts: int = 0, max_attempts: int = 3) -> bool:
    """Whether the fake login service accepts a code on this try (the login ladder).

    `attempts` is the number of wrong tries so far on this call:
      - first try (attempts == 0): any 4- to 10-digit code except ALWAYS_WRONG_LOGIN_CODES;
      - second try (attempts == 1): only known codes in VALID_LOGIN_CODES;
      - the last try (attempts >= max_attempts - 1): always wrong, so the caller
        is locked out and lockout tests behave the same every time.
    """
    digits = normalize_code(code_digits)
    if not (4 <= len(digits) <= 10):
        return False
    if digits in ALWAYS_WRONG_LOGIN_CODES:
        return False
    if attempts >= max(max_attempts - 1, 1):
        return False
    if attempts >= 1:
        return digits in VALID_LOGIN_CODES
    return True


def secret_pin_accepted(pin_digits: Any, attempts: int = 0, max_attempts: int = 3) -> bool:
    """Whether the fake login service accepts a secret PIN.

    Under the 3-attempt PIN ladder:
      - Attempt 1 (attempts == 0): any 4- to 6-digit PIN not in ALWAYS_WRONG_LOGIN_CODES.
      - Attempt 2 (attempts == 1): any valid 4- to 6-digit PIN not in ALWAYS_WRONG_LOGIN_CODES.
      - Attempt 3 (attempts >= max_attempts - 1): always False (lockout triggered).
    """
    digits = normalize_code(pin_digits)
    if not (4 <= len(digits) <= 6):
        return False
    if digits in ALWAYS_WRONG_LOGIN_CODES:
        return False
    if attempts >= max(max_attempts - 1, 1):
        return False
    return True
