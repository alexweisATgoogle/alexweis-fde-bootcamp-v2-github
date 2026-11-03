from __future__ import annotations

from typing import Optional



def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject active language rules and verbatim lines before model invocation."""
    apply_language_prompt_filter(
        callback_context,
        llm_request,
        agent_name="specialist",
    )
    return None


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.dynamic_prompt import apply_language_prompt_filter
from datetime import datetime, timedelta, timezone
from typing import Any
import re

LANGUAGE_SHEET_SENTINEL = "<!-- ACTIVE_LANGUAGE_SHEET -->"  # pragma: no cover

AGENT_VERBATIM_KEYS: dict[str, tuple[str, ...]] = {  # pragma: no cover
    "router": (
        "greeting",
        "greeting_main",
        "recording_notice",
        "handover",
        "live_agent_handoff",
        "business_handoff",
        "empathy_protocol",
        "ai_disclosure",
        "malicious_closing",
    ),
    "specialist": (
        "code_sent",
        "id_verification_otp",
        "id_verification_pin",
        "handover",
        "live_agent_handoff",
        "business_handoff",
        "empathy_protocol",
        "payment_method_preamble",
        "contract_cancellation_fee_disclosure",
        "outage_active",
        "transfer_to_specialist",
        "auth_failure_handoff",
        "refund_confirmation_pattern",
        "card_declined",
        "ai_disclosure",
        "malicious_closing",
        "recording_notice",
    ),
}

WORLD_LANGUAGE_NAMES: dict[str, str] = {  # pragma: no cover
    "en-US": "English",
    "fr-CA": "French (Canada)",
    "es-US": "Spanish",
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
        "en-US": (
            "This request exceeds the self-service limit and requires specialist approval. "
            "I'll connect you to a billing specialist now — they'll have everything we've already discussed."
        ),
        "fr-CA": (
            "Cette demande dépasse la limite libre-service et nécessite l'approbation d'un spécialiste. "
            "Je vous transfère à un spécialiste de la facturation maintenant — il aura accès à tous les détails de notre conversation."
        ),
        "es-US": (
            "Esta solicitud supera el límite de autoservicio y requiere la aprobación de un especialista. "
            "Lo comunicaré con un especialista en facturación ahora; tendrá todo lo que ya hemos discutido."
        ),
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

def build_language_sheet(locale: str, agent_name: str = "router") -> str:  # pragma: no cover
    """Generate dynamic language sheet containing localized rules and verbatim lines."""
    loc = resolve_locale(locale)
    lang_name = WORLD_LANGUAGE_NAMES.get(loc, loc)
    keys = AGENT_VERBATIM_KEYS.get(agent_name, AGENT_VERBATIM_KEYS.get("router", ("greeting", "handover")))

    lines = [
        LANGUAGE_SHEET_SENTINEL,
        f'<active_language_sheet locale="{loc}" language="{lang_name}">',
    ]

    if loc in ("en-US", "fr-CA", "es-US"):
        lines.append("### Required Disclosures & Spoken Lines (Emit Exact Wording):")
        for k in keys:
            line_text = spoken_line(k, loc)
            if line_text:
                lines.append(f'- {k}: "{line_text}"')
        lines.append("")
        lines.append("### Mandatory Conversational Rules:")
        lines.append(
            f"1. Speak 100% in {lang_name} ({loc}). Never mix languages or repeat lines in another language."
        )
        lines.append(
            f'2. Always pass language="{loc}" when calling tools (and write any free-text reason/summary in {lang_name} while keeping structural enum values unchanged).'
        )
        lines.append(
            "3. Emit the verbatim lines above word-for-word whenever their trigger fires, filling slots from tool output only."
        )
    else:
        lines.append("### Canonical Templates:")
        for k in keys:
            line_text = spoken_line(k, "en-US")
            if line_text:
                lines.append(f'- {k}: "{line_text}"')
        lines.append("")
        lines.append("### Mandatory Conversational Rules:")
        lines.append(
            f"1. Speak 100% natively and fluently in {lang_name} ({loc}), translating disclosures faithfully into {lang_name} with zero English mixing."
        )
        lines.append(
            f'2. Pass language="{loc}" to tools; if a request cannot be completed accurately without language degradation, politely offer to connect a specialist via handover_to_person(reason="secondary_language_live_agent", language="{loc}").'
        )

    lines.append("</active_language_sheet>")
    return "\n".join(lines)

_DP_EXPLICIT_SWITCH_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (  # pragma: no cover
    ("fr-CA", ("en français", "en francais", "parlez-vous français", "parlez vous francais", "in french", "speak french", "french please", "switch to french")),
    ("es-US", ("en español", "en espanol", "habla español", "habla espanol", "in spanish", "speak spanish", "spanish please", "switch to spanish")),
    ("en-US", ("in english", "speak english", "english please", "switch to english")),
    ("de-DE", ("auf deutsch", "sprechen sie deutsch", "in german", "speak german", "german please", "switch to german")),
    ("it-IT", ("in italiano", "parla italiano", "in italian", "speak italian", "italian please", "switch to italian")),
    ("pt-BR", ("em português", "em portugues", "fala português", "fala portugues", "in portuguese", "speak portuguese", "portuguese please", "switch to portuguese")),
)

_DP_NEGATED_SWITCH_PREFIX_RE = re.compile(  # pragma: no cover
    r"(?:"
    r"\b(?:don't|do\s+not|dont|cannot|can't|cant|not|unable to|not able to)\s+"
    r"(?:want\s+to\s+|know\s+how\s+to\s+)?(?:speak\s+|talk\s+|switch\s+to\s+)?"
    r"|\b(?:pas|jamais)\s+(?:parler\s+|continuer\s+)?"
    r"|\bno\s+(?:hablo|habla|hablas|hablamos|puedo|podemos|quiero)\s+(?:hablar\s+)?"
    r")\s*$",
    re.IGNORECASE,
)

def _dp_match_explicit_switch(low: str) -> str:  # pragma: no cover
    """Return target locale for the last non-negated explicit switch term in low."""
    best_end = -1
    best_locale = ""
    for target_locale, terms in _DP_EXPLICIT_SWITCH_TERMS:
        for term in terms:
            for m in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", low):
                if _DP_NEGATED_SWITCH_PREFIX_RE.search(low[: m.start()]):
                    continue
                if m.end() > best_end:
                    best_end = m.end()
                    best_locale = target_locale
    return best_locale

_RE_RELAY_ACTIVE_LANG = re.compile(  # pragma: no cover
    r"""['"]active_language['"]\s*:\s*['"]([a-zA-Z]{2}(?:-[a-zA-Z]{2})?)['"]"""
)

def _extract_relayed_active_language(llm_request: Any) -> str:  # pragma: no cover
    """Extract the most recent active_language from relayed tool results in contents."""
    contents = getattr(llm_request, "contents", None)
    if not contents or not isinstance(contents, (list, tuple)):
        return ""
    last_lang = ""
    for item in contents:
        parts = getattr(item, "parts", None)
        if parts and isinstance(parts, (list, tuple)):
            for part in parts:
                txt = getattr(part, "text", None)
                if txt and isinstance(txt, str):
                    matches = _RE_RELAY_ACTIVE_LANG.findall(txt)
                    if matches:
                        last_lang = matches[-1]
                fn_resp = getattr(part, "function_response", None)
                if fn_resp:
                    resp = getattr(fn_resp, "response", None)
                    if isinstance(resp, dict):
                        al = resp.get("active_language")
                        if not al and isinstance(resp.get("result"), dict):
                            al = resp["result"].get("active_language")
                        if al and isinstance(al, str):
                            last_lang = al
        elif isinstance(getattr(item, "text", None), str):
            matches = _RE_RELAY_ACTIVE_LANG.findall(item.text)
            if matches:
                last_lang = matches[-1]
    if last_lang:
        return resolve_locale(last_lang)
    return ""

_ENGLISH_MARKERS: frozenset[str] = frozenset({  # pragma: no cover
    "hello", "hi", "thanks", "thank", "yes", "yeah", "account", "bill",
    "pay", "service", "help", "need", "representative", "agent", "speak",
    "code", "received", "please", "support",
})

_FRENCH_MARKERS: frozenset[str] = frozenset({  # pragma: no cover
    "bonjour", "merci", "oui", "non", "svp", "compte", "facture", "payer",
    "service", "aide", "besoin", "agent", "parler", "code", "reçu", "francais",
    "français", "salut", "allo", "allô", "s'il", "vous", "plaît", "plait",
})

_SPANISH_MARKERS: frozenset[str] = frozenset({  # pragma: no cover
    "hola", "gracias", "si", "sí", "cuenta", "factura", "pagar", "servicio",
    "ayuda", "necesito", "agente", "hablar", "codigo", "código", "espanol",
    "español", "buenas", "tardes", "días", "favor", "por",
})

def detect_utterance_language(utterance: str, current_language: str = "en-US") -> str:  # pragma: no cover
    """Detect language from an utterance with contextual inertia on silence and numbers."""
    cleaned = re.sub(r"\\[(?:pause|silence)\\]", " ", str(utterance or ""), flags=re.IGNORECASE)
    cleaned = re.sub(r"[0-9\W_]+", " ", cleaned).strip()
    if not cleaned:
        return resolve_locale(current_language)

    low = str(utterance or "").lower()

    explicit_switch = _dp_match_explicit_switch(low)
    if explicit_switch:
        return explicit_switch

    words = [w.lower() for w in cleaned.split()]

    if words == ["merci"] and resolve_locale(current_language) == "en-US":
        return "en-US"
    if words == ["gracias"] and resolve_locale(current_language) == "en-US":
        return "en-US"

    french_words = sum(1 for w in words if w in _FRENCH_MARKERS)
    has_french_accents = bool(re.search(r"[éèêëàâùûîïôçœ]", low))
    french_score = french_words + (1 if has_french_accents else 0)

    spanish_words = sum(1 for w in words if w in _SPANISH_MARKERS)
    has_spanish_punct = bool(re.search(r"[¿¡ñ]", low))
    spanish_score = spanish_words + (1 if has_spanish_punct else 0)

    english_words = sum(1 for w in words if w in _ENGLISH_MARKERS)

    if french_score > 0 and french_score >= spanish_score and french_score >= english_words:
        return "fr-CA"
    if spanish_score > 0 and spanish_score > french_score and spanish_score >= english_words:
        return "es-US"
    if english_words >= 3 and french_score == 0 and spanish_score == 0:
        return "en-US"

    return resolve_locale(current_language)

_RE_QUOTED_AGENT_BLOCK = re.compile(  # pragma: no cover
    r"<<<BEGIN_QUOTED_AGENT_CONTENT>>>[\s\S]*?<<<END_QUOTED_AGENT_CONTENT>>>"
)

_RE_RELAY_PREFIX = re.compile(  # pragma: no cover
    r"^(?:For context|\s*\[[^\]]+\]\s*(?:said:|thought:|called tool |`[^`]*` tool returned result:))",
    re.IGNORECASE,
)

def _is_relay_or_quoted_part(txt: str) -> bool:  # pragma: no cover
    """Return True if txt is an ADK relay part, agent event, or quoted content block."""
    s = txt.strip()
    if not s:
        return True
    if _RE_RELAY_PREFIX.match(s):
        return True
    cleaned = _RE_QUOTED_AGENT_BLOCK.sub("", s).strip()
    if not cleaned:
        return True
    if _RE_RELAY_PREFIX.match(cleaned):
        return True
    return False

def extract_user_utterances(llm_request: Any) -> list[str]:  # pragma: no cover
    """Safely extract genuine user utterance strings from LLM request contents, skipping relay parts."""
    utterances: list[str] = []
    contents = getattr(llm_request, "contents", None)
    if not contents or not isinstance(contents, (list, tuple)):
        return utterances
    for item in contents:
        if getattr(item, "role", "") == "user":
            parts = getattr(item, "parts", None)
            if parts and isinstance(parts, (list, tuple)):
                for part in parts:
                    txt = getattr(part, "text", None)
                    if txt and isinstance(txt, str) and txt.strip():
                        if not _is_relay_or_quoted_part(txt):
                            utterances.append(txt.strip())
            elif isinstance(getattr(item, "text", None), str):
                t = item.text.strip()
                if t and not _is_relay_or_quoted_part(t):
                    utterances.append(t)
    return utterances

def detect_active_call_language(state_dict: Any, llm_request: Any) -> str:  # pragma: no cover
    """Determine the active conversation language from state and user turns."""
    user_utterances = extract_user_utterances(llm_request)
    locked = (
        str(state_dict.get("language") or "").strip()
        if callable(getattr(state_dict, "get", None))
        else ""
    )
    if locked:
        locked = resolve_locale(locked)
    else:
        relayed = _extract_relayed_active_language(llm_request)
        if relayed:
            locked = relayed

    if locked and locked != "en-US":
        current = locked
        for utt in user_utterances:
            switch = _dp_match_explicit_switch(utt.lower())
            if switch:
                current = switch
        return current

    current = resolve_locale(locked) if locked else "en-US"
    for utt in user_utterances:
        if current != "en-US":
            switch = _dp_match_explicit_switch(utt.lower())
            if switch:
                current = switch
        else:
            current = detect_utterance_language(utt, current_language=current)

    return current

def apply_language_prompt_filter(  # pragma: no cover
    callback_context: Any,
    llm_request: Any,
    agent_name: str = "router",
) -> None:
    """Inject language rules and verbatim lines into system instruction in-place without touching state."""
    state = getattr(callback_context, "state", None)
    state_dict = state if callable(getattr(state, "get", None)) else {}
    locale = detect_active_call_language(state_dict, llm_request)
    sheet = build_language_sheet(locale, agent_name=agent_name)

    config = getattr(llm_request, "config", None)
    if config is None:
        return None
    sys_inst = getattr(config, "system_instruction", None)
    if sys_inst is None:
        return None

    def _update_text(text: str) -> str:
        if LANGUAGE_SHEET_SENTINEL in text:
            text = text.split(LANGUAGE_SHEET_SENTINEL, 1)[0].rstrip()
        return f"{text}\n\n{sheet}"

    if isinstance(sys_inst, str):
        config.system_instruction = _update_text(sys_inst)
    elif hasattr(sys_inst, "parts"):
        parts = getattr(sys_inst, "parts", None)
        if parts and len(parts) > 0:
            first = parts[0]
            if hasattr(first, "text") and isinstance(first.text, str):
                first.text = _update_text(first.text)
    elif isinstance(sys_inst, list) and len(sys_inst) > 0:
        if isinstance(sys_inst[0], str):
            sys_inst[0] = _update_text(sys_inst[0])
        elif hasattr(sys_inst[0], "text") and isinstance(sys_inst[0].text, str):
            sys_inst[0].text = _update_text(sys_inst[0].text)
# --- END GENERATED SHARED BUNDLE ---
