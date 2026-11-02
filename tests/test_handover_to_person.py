from types import SimpleNamespace

import cxas_app.tools.handover_to_person.python_function.python_code as tool


def test_handover_to_person_sets_state_and_returns_message(monkeypatch) -> None:
    session = SimpleNamespace(state={"account_id": "A1001", "language": "fr-CA"})
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.handover_to_person(reason="besoin d'aide", language="fr-CA")
    assert reply["status"] == "ok"
    assert reply["data"]["handoff_status"] == "completed_via_specialist_queue"
    assert reply["data"]["language"] == "fr-CA"
    assert session.state["handover_complete"] is True
    assert "transfère" in session.state["handoff_message"]
