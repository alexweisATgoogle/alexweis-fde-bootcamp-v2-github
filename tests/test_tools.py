from types import SimpleNamespace

import cxas_app.tools.check_login_code.python_function.python_code as check_login_code_tool
import cxas_app.tools.check_secret_pin.python_function.python_code as check_secret_pin_tool
import cxas_app.tools.handover_to_person.python_function.python_code as handover_tool
import cxas_app.tools.lookup_account.python_function.python_code as lookup_tool
import cxas_app.tools.send_login_code.python_function.python_code as send_code_tool
import cxas_app.tools.submit_request.python_function.python_code as submit_tool
from lib.services import check_login_code, handover_to_person, record_payment_attempt


def test_three_strike_login_lockout_and_direct_code_entry(monkeypatch) -> None:
    session = SimpleNamespace(state={})
    for mod in (lookup_tool, send_code_tool, check_login_code_tool, check_secret_pin_tool, submit_tool, handover_tool):
        monkeypatch.setattr(mod, "context", session, raising=False)

    r1 = check_login_code_tool.check_login_code("9999")
    r2 = check_login_code_tool.check_login_code("9999")
    r3 = check_login_code_tool.check_login_code("9999")
    assert r1["data"]["attempts_remaining"] == 2
    assert r2["data"]["attempts_remaining"] == 1
    assert r3["error"] == "TOO_MANY_ATTEMPTS"
    assert r3["lockout_triggered"] is True

    # Direct login without prior send_login_code on a fresh state
    fresh = SimpleNamespace(state={})
    monkeypatch.setattr(check_login_code_tool, "context", fresh, raising=False)
    ok = check_login_code_tool.check_login_code("5903")
    assert ok["status"] == "ok" and ok["logged_in"] is True
    assert check_login_code("271846")["status"] == "OK"


def test_handover_language_detection_and_payment_lockout() -> None:
    r_fr = handover_to_person(reason="besoin d'un agent", language="fr-CA")
    assert "transfère" in r_fr["data"].get("handoff_message", "")

    state_es = {"language": "es-US"}
    r_es = handover_to_person(reason="billing", state=state_es)
    assert r_es["data"]["language"] == "es-US"
    assert "transfiero" in r_es["handoff_message"]
    explicit = handover_to_person(reason="billing", language="en-US", state={"language": "es-US"})
    assert explicit["data"]["language"] == "es-US"

    pay_state: dict = {}
    assert record_payment_attempt(pay_state, False)["error"] == "CARD_DECLINED"
    assert record_payment_attempt(pay_state, False)["error"] == "CARD_DECLINED"
    assert record_payment_attempt(pay_state, False)["error"] == "TOO_MANY_ATTEMPTS"
