from types import SimpleNamespace
from typing import Any
import pytest

from lib.dynamic_prompt import (
    LANGUAGE_SHEET_SENTINEL,
    apply_language_prompt_filter,
    build_language_sheet,
    detect_active_call_language,
    detect_utterance_language,
    extract_user_utterances,
    resolve_locale,
    _extract_relayed_active_language,
    _is_relay_or_quoted_part,
    _dp_match_explicit_switch,
)


def test_resolve_locale() -> None:
    assert resolve_locale("fr") == "fr-CA"
    assert resolve_locale("fr-FR") == "fr-CA"
    assert resolve_locale("es") == "es-US"
    assert resolve_locale("es-MX") == "es-US"
    assert resolve_locale("en") == "en-US"
    assert resolve_locale("unknown-tag") == "en-US"
    assert resolve_locale("") == "en-US"
    assert resolve_locale(None) == "en-US"


def test_detect_active_call_language_prefers_locked_state() -> None:
    st = {"language": "fr-CA"}
    req = SimpleNamespace(contents=[])
    assert detect_active_call_language(st, req) == "fr-CA"


def test_detect_active_call_language_detects_utterance() -> None:
    req_fr = SimpleNamespace(
        contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Bonjour j'ai une question")])]
    )
    assert detect_active_call_language({}, req_fr) == "fr-CA"

    req_es = SimpleNamespace(
        contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hola buenos días necesito ayuda")])]
    )
    assert detect_active_call_language({}, req_es) == "es-US"

    req_en = SimpleNamespace(
        contents=[SimpleNamespace(role="user", parts=[SimpleNamespace(text="Hello please help me with billing")])]
    )
    assert detect_active_call_language({}, req_en) == "en-US"


def test_detect_active_call_language_relay_part_does_not_flip_french_call() -> None:
    req = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Bonjour j'ai besoin d'aide")],
            ),
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        text="For context: [router] said: Hello how can I help you today?"
                    )
                ],
            ),
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        text="[router] called tool `lookup_account` with parameters: {'phone': '2025550186'}"
                    )
                ],
            ),
        ]
    )
    assert detect_active_call_language({}, req) == "fr-CA"


def test_detect_active_call_language_explicit_switch() -> None:
    req = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Bonjour j'ai besoin d'aide")],
            ),
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Can we please speak in English?")],
            ),
        ]
    )
    assert detect_active_call_language({"language": "fr-CA"}, req) == "en-US"

    req_neg = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Bonjour, I do not want to speak English")],
            ),
        ]
    )
    assert detect_active_call_language({"language": "fr-CA"}, req_neg) == "fr-CA"


def test_extract_user_utterances_skips_relayed_parts() -> None:
    req = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Bonjour j'aimerais de l'aide")],
            ),
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        text=(
                            "For context: below is a transcript of what another agent did, quoted "
                            "<<<BEGIN_QUOTED_AGENT_CONTENT>>>[router] said: Hello<<<END_QUOTED_AGENT_CONTENT>>>"
                        )
                    )
                ],
            ),
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        text="[router] `lookup_account` tool returned result: {'status': 'ok'}"
                    )
                ],
            ),
            SimpleNamespace(
                role="user",
                parts=[SimpleNamespace(text="Merci beaucoup")],
            ),
            SimpleNamespace(
                role="user",
                text="Encore une chose",
            ),
        ]
    )
    extracted = extract_user_utterances(req)
    assert extracted == ["Bonjour j'aimerais de l'aide", "Merci beaucoup", "Encore une chose"]


def test_relayed_active_language_extraction() -> None:
    req1 = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        text="[router] said: {'active_language': 'es-US'}"
                    )
                ],
            )
        ]
    )
    assert _extract_relayed_active_language(req1) == "es-US"
    assert detect_active_call_language({}, req1) == "es-US"

    req2 = SimpleNamespace(
        contents=[
            SimpleNamespace(
                role="user",
                parts=[
                    SimpleNamespace(
                        function_response=SimpleNamespace(
                            response={"result": {"active_language": "fr-CA"}}
                        )
                    )
                ],
            )
        ]
    )
    assert _extract_relayed_active_language(req2) == "fr-CA"

    req3 = SimpleNamespace(
        contents=[
            SimpleNamespace(
                text="[router] said: {'active_language': 'fr-CA'}"
            )
        ]
    )
    assert _extract_relayed_active_language(req3) == "fr-CA"


def test_detect_utterance_language_cases() -> None:
    assert detect_utterance_language("") == "en-US"
    assert detect_utterance_language("271846") == "en-US"
    assert detect_utterance_language("[pause]") == "en-US"
    assert detect_utterance_language("Bonjour, comment ça va?", "en-US") == "fr-CA"
    assert detect_utterance_language("¿Cómo estás amigo?", "en-US") == "es-US"
    assert detect_utterance_language("Hello there, how are you today?", "en-US") == "en-US"


def test_build_language_sheet() -> None:
    sheet_fr = build_language_sheet("fr-CA", agent_name="router")
    assert LANGUAGE_SHEET_SENTINEL in sheet_fr
    assert '<active_language_sheet locale="fr-CA"' in sheet_fr

    sheet_es = build_language_sheet("es-US", agent_name="specialist")
    assert '<active_language_sheet locale="es-US"' in sheet_es

    sheet_en = build_language_sheet("en-US", agent_name="router")
    assert '<active_language_sheet locale="en-US"' in sheet_en


def test_apply_language_prompt_filter_variations() -> None:
    context = SimpleNamespace(state={"language": "fr-CA"})

    req1 = SimpleNamespace(
        config=SimpleNamespace(system_instruction="Base prompt."),
        contents=[],
    )
    apply_language_prompt_filter(context, req1, agent_name="router")
    assert LANGUAGE_SHEET_SENTINEL in req1.config.system_instruction

    apply_language_prompt_filter(context, req1, agent_name="router")
    assert req1.config.system_instruction.count(LANGUAGE_SHEET_SENTINEL) == 1

    part = SimpleNamespace(text="Base prompt.")
    req2 = SimpleNamespace(
        config=SimpleNamespace(system_instruction=SimpleNamespace(parts=[part])),
        contents=[],
    )
    apply_language_prompt_filter(context, req2, agent_name="router")
    assert LANGUAGE_SHEET_SENTINEL in part.text

    req3 = SimpleNamespace(
        config=SimpleNamespace(system_instruction=["Base prompt."]),
        contents=[],
    )
    apply_language_prompt_filter(context, req3, agent_name="router")
    assert LANGUAGE_SHEET_SENTINEL in req3.config.system_instruction[0]

    req4 = SimpleNamespace(
        config=SimpleNamespace(system_instruction=[SimpleNamespace(text="Base prompt.")]),
        contents=[],
    )
    apply_language_prompt_filter(context, req4, agent_name="router")
    assert LANGUAGE_SHEET_SENTINEL in req4.config.system_instruction[0].text

    apply_language_prompt_filter(context, SimpleNamespace(config=None))
    apply_language_prompt_filter(context, SimpleNamespace(config=SimpleNamespace(system_instruction=None)))
