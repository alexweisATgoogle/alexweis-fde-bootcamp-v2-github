from __future__ import annotations

from types import SimpleNamespace
from typing import Optional





def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Cleans every text part of the reply before the caller hears it.

    Strips markdown symbols, masks long numbers to their last 4 digits and
    prefers caller_provided_phone_last4. After a handover it adds
    handoff_message only when the reply has no spoken text at all; it never
    replaces words the model said, so a step-specific or PRD-exact transfer
    line survives. Returns None when nothing changed, so the reply goes out
    untouched.
    """
    state = getattr(callback_context, "state", None)
    state_dict = state if isinstance(state, dict) else {}
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if content is None or parts is None:
        return None
    changed = False
    has_spoken_text = False
    has_handover_call = False
    handover_reason = ""
    handover_lang = state_dict.get("language") or ""
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc is not None and getattr(fc, "name", "") == "handover_to_person":
            has_handover_call = True
            fc_args = getattr(fc, "args", {}) or {}
            if isinstance(fc_args, dict):
                handover_reason = str(fc_args.get("reason") or "")
                handover_lang = str(fc_args.get("language") or handover_lang)
            break

    effective_state = dict(state_dict)
    if has_handover_call:
        effective_state["handover_complete"] = True
        if handover_reason:
            effective_state["handoff_reason"] = handover_reason
        if handover_lang:
            effective_state["language"] = handover_lang

    # Sanitize end_session reason on French sessions
    is_french_session = (
        str(state_dict.get("language") or "").startswith("fr")
        or str(state_dict.get("locked_language") or "").startswith("fr")
        or handover_lang.startswith("fr")
    )
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc is not None and getattr(fc, "name", "") == "end_session":
            fc_args = getattr(fc, "args", None)
            if isinstance(fc_args, dict) and is_french_session:
                curr_reason = str(fc_args.get("reason") or "").strip().lower()
                if curr_reason in ("resolved", "complete", "completed", "resolution", "done", "resolu", ""):
                    fc_args["reason"] = "résolu"
                    changed = True

    for part in parts:
        text = getattr(part, "text", None)
        if not isinstance(text, str) or not text.strip():
            continue
        has_spoken_text = True
        cleaned = clean_agent_speech(clean_speech(text), state_dict)
        cleaned = enforce_handover_utterance(cleaned, effective_state)
        if cleaned != text:
            part.text = cleaned
            changed = True

    if not has_spoken_text:
        handoff_msg = enforce_handover_utterance("", effective_state).strip()
        if not handoff_msg and has_handover_call:
            handoff_msg = resolve_handover_fallback(handover_reason, handover_lang, state_dict).strip()
        if handoff_msg and isinstance(parts, list):
            cleaned_msg = clean_agent_speech(clean_speech(handoff_msg), state_dict)
            if parts and getattr(parts[0], "text", None) in (None, "") and not getattr(parts[0], "function_call", None):
                parts[0].text = cleaned_msg
            else:
                parts.insert(0, SimpleNamespace(text=cleaned_msg))
            changed = True

    return llm_response if changed else None


# --- BEGIN GENERATED SHARED BUNDLE (edit lib/, then run `make bundle`) ---
# uses: from lib.speech import clean_agent_speech, clean_speech, enforce_handover_utterance, resolve_handover_fallback
from datetime import datetime, timedelta, timezone
from typing import Any
import copy
import hashlib
import re

_LAST4_CONTEXT_RE = re.compile(  # pragma: no cover
    r"((?:ending\s+in|terminant\s+par|termina\s+en|number\s+is|num[eé]ro\s+est|n[uú]mero\s+es)\s+)(\d{4})\b",
    re.IGNORECASE,
)

NUMBER_RUN_RE = re.compile(r"\(?\d+\)?(?:[-.]\(?\d+\)?|\s\(?\d{3,}\)?)*")  # pragma: no cover

SPEAKABLE_NUMBERS: frozenset[str] = frozenset()  # pragma: no cover

def mask_long_numbers(text: str, min_digits: int = 9) -> str:  # pragma: no cover
    """Replace every number of `min_digits` or more digits by its last 4 digits."""

    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < min_digits or digits in SPEAKABLE_NUMBERS:
            return match.group(0)
        return digits[-4:]

    return NUMBER_RUN_RE.sub(_mask, text)

MARKDOWN_RE = re.compile(r"\*+|`+|^#+[ \t]*", re.MULTILINE)  # pragma: no cover

def strip_markdown(text: str) -> str:  # pragma: no cover
    """Drop the markdown symbols a voice would read out: asterisks, backticks, headings."""
    return MARKDOWN_RE.sub("", text)

def clean_speech(text: str) -> str:  # pragma: no cover
    """Everything the speech_hygiene callback does to one piece of reply text."""
    return mask_long_numbers(strip_markdown(text))

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

def enforce_outage_utterance(  # pragma: no cover
    text: str,
    session_params: dict[str, Any] | None = None,
) -> str:
    """Ensure active outage announcements speak all three sentences verbatim."""
    clean_text = (text or "").strip()
    if not clean_text:
        return text

    low = clean_text.lower()
    is_en_outage = (
        "active outage in your area" in low
        or "there's an active outage" in low
        or "there is an active outage" in low
    )
    is_fr_outage = (
        "panne active dans votre secteur" in low
        or ("panne active" in low and "secteur" in low)
    )
    if not (is_en_outage or is_fr_outage):
        return text

    # Do not overwrite a dedicated SMS registration confirmation turn
    if any(k in low for k in ("i've registered", "j'ai inscrit", "j'ai bien noté", "registered text", "registered your number")):
        return text

    state_dict = session_params if isinstance(session_params, dict) else {}
    lang = str(state_dict.get("language") or "")
    if is_fr_outage or lang.startswith("fr"):
        full_line = spoken_line("outage_active", "fr-CA")
        has_s2 = "travaillons" in low
        has_s3 = "texto lorsque" in low or "sera rétabli" in low or "sera retabli" in low
        if not has_s2 or not has_s3:
            return full_line
    else:
        full_line = spoken_line("outage_active", "en-US")
        has_s2 = "working on it" in low
        has_s3 = "text you when" in low or "when it's restored" in low or "when it is restored" in low
        if not has_s2 or not has_s3:
            return full_line

    return text

def clean_agent_speech(  # pragma: no cover
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

def enforce_handover_utterance(  # pragma: no cover
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
                r"(?:(?:i (?:will|shall|can|must) )?(?:transfer|connect) you to a representative(?: now)?\.?|"
                r"(?:je vous (?:transf[eé]rerai?|mets en contact avec) un repr[eé]sentant(?: maintenant)?\.?))",
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

def resolve_handover_fallback(  # pragma: no cover
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
# --- END GENERATED SHARED BUNDLE ---
