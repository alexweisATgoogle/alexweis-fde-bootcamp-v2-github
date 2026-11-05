from types import SimpleNamespace

import pytest

from cxas_app.agents.router.after_model_callbacks.speech_hygiene import python_code as router_callback
from cxas_app.agents.specialist.after_model_callbacks.speech_hygiene import python_code as specialist_callback

CALLBACKS = [router_callback, specialist_callback]


def make_response(*texts: str) -> SimpleNamespace:
    parts = [SimpleNamespace(text=text) for text in texts]
    parts.append(SimpleNamespace(text=None, function_call=SimpleNamespace(name="end_session")))
    return SimpleNamespace(content=SimpleNamespace(parts=parts))


@pytest.mark.parametrize("callback", CALLBACKS)
def test_cleans_text_parts_and_keeps_tool_calls(callback) -> None:
    response = make_response("**Your number is 2025550186.**", "Anything else?")
    assert callback.after_model_callback(SimpleNamespace(state={}), response) is response
    assert response.content.parts[0].text == "Your number is 0186."
    assert response.content.parts[1].text == "Anything else?"
    assert response.content.parts[2].function_call.name == "end_session"


@pytest.mark.parametrize("callback", CALLBACKS)
def test_injects_handoff_message_when_handover_turn_has_no_spoken_text(callback) -> None:
    msg = "Je vous transfère maintenant à un membre de notre équipe. Merci de votre patience."
    state = {"handover_complete": True, "handoff_message": msg}
    tool_only = SimpleNamespace(
        content=SimpleNamespace(
            parts=[SimpleNamespace(text=None, function_call=SimpleNamespace(name="end_session"))]
        )
    )
    assert callback.after_model_callback(SimpleNamespace(state=state), tool_only) is tool_only
    assert tool_only.content.parts[0].text == msg


@pytest.mark.parametrize("callback", CALLBACKS)
def test_keeps_the_spoken_transfer_line_after_a_handover(callback) -> None:
    msg = "I'm transferring you to a member of our team now. Thank you for your patience."
    state = {"handover_complete": True, "handoff_message": msg}
    step_line = "I'm transferring you to a billing specialist now."
    response = make_response(step_line)
    assert callback.after_model_callback(SimpleNamespace(state=state), response) is None
    assert response.content.parts[0].text == step_line


@pytest.mark.parametrize("callback", CALLBACKS)
def test_returns_none_when_nothing_changes(callback) -> None:
    assert callback.after_model_callback(SimpleNamespace(state={}), make_response("All set.")) is None
    assert callback.after_model_callback(SimpleNamespace(state={}), SimpleNamespace(content=None)) is None


@pytest.mark.parametrize("callback", CALLBACKS)
def test_adv_iter9_2_threshold_handover_2_sentence_guarantee(callback) -> None:
    # 1. State-based dispute_limit_exceeded (English)
    st_en = {
        "handover_complete": True,
        "dispute_limit_exceeded": True,
        "handoff_reason": "refund_threshold_exceeded",
        "language": "en-US",
    }
    partial_text = "I'll connect you to a billing specialist now."
    resp_en = make_response(partial_text)
    out_en = callback.after_model_callback(SimpleNamespace(state=st_en), resp_en)
    assert out_en is resp_en
    assert "Disputes exceeding the automated limit require review by a specialist." in resp_en.content.parts[0].text
    assert partial_text in resp_en.content.parts[0].text

    # 2. State-based dispute_limit_exceeded (French)
    st_fr = {
        "handover_complete": True,
        "dispute_limit_exceeded": True,
        "handoff_reason": "refund_threshold_exceeded",
        "language": "fr-CA",
    }
    partial_fr = "Je vous transfère à un spécialiste de la facturation maintenant."
    resp_fr = make_response(partial_fr)
    out_fr = callback.after_model_callback(SimpleNamespace(state=st_fr), resp_fr)
    assert out_fr is resp_fr
    assert "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste." in resp_fr.content.parts[0].text
    assert partial_fr in resp_fr.content.parts[0].text

    # 3. Same-turn function_call to handover_to_person with refund_threshold_exceeded
    resp_fc = SimpleNamespace(
        content=SimpleNamespace(
            parts=[
                SimpleNamespace(text="I'll transfer you now."),
                SimpleNamespace(
                    text=None,
                    function_call=SimpleNamespace(
                        name="handover_to_person",
                        args={"reason": "refund_threshold_exceeded", "language": "en-US"},
                    ),
                ),
            ]
        )
    )
    st_fc = {"language": "en-US"}
    out_fc = callback.after_model_callback(SimpleNamespace(state=st_fc), resp_fc)
    assert out_fc is resp_fc
    assert "Disputes exceeding the automated limit require review by a specialist." in resp_fc.content.parts[0].text

    # 4. Spoken text already contains explanation -> not duplicated
    full_text = "Disputes exceeding the automated limit require review by a specialist. Transferring you."
    resp_full = make_response(full_text)
    out_full = callback.after_model_callback(SimpleNamespace(state=st_en), resp_full)
    assert resp_full.content.parts[0].text == full_text

