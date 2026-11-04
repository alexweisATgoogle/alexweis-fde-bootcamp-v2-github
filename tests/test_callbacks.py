from types import SimpleNamespace

from cxas_app.agents.router.after_model_callbacks.speech_hygiene import python_code as router_cb
from cxas_app.agents.specialist.after_model_callbacks.speech_hygiene import python_code as specialist_cb


def test_callbacks_prefer_caller_last4_and_inject_handover_line() -> None:
    state = {
        "phone_last4": "0186",
        "caller_provided_phone_last4": "0142",
        "handover_complete": False,
    }
    resp = SimpleNamespace(
        content=SimpleNamespace(
            parts=[SimpleNamespace(text="**Your number ending in 0143 is ready.**")]
        )
    )
    out = router_cb.after_model_callback(SimpleNamespace(state=state), resp)
    assert out is resp
    assert resp.content.parts[0].text == "Your number ending in 0142 is ready."

    handover_msg = "I'm transferring you to a member of our team now. Thank you for your patience."
    h_state = {"handover_complete": True, "handoff_message": handover_msg}
    empty_resp = SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="")]))
    out2 = specialist_cb.after_model_callback(SimpleNamespace(state=h_state), empty_resp)
    assert out2 is empty_resp
    assert empty_resp.content.parts[0].text == handover_msg
