from lib.services import (
    MAX_LOGIN_ATTEMPTS,
    check_login_code,
    check_login_code_impl,
    check_secret_pin,
    check_secret_pin_impl,
    handover_to_person,
    handover_to_person_impl,
    lookup_account,
    lookup_account_impl,
    not_identified_reply,
    read_count,
    record_payment_attempt,
    send_login_code,
    send_login_code_impl,
    submit_request,
    submit_request_impl,
)

KNOWN_PHONE = "202 555 0186"


def logged_in_state() -> dict:
    state: dict = {}
    assert lookup_account_impl(KNOWN_PHONE, state)["status"] == "ok"
    assert send_login_code_impl(state)["status"] == "ok"
    assert check_login_code_impl("271846", state)["status"] == "ok"
    return state


def test_read_count_handles_decimals_and_junk() -> None:
    assert read_count({"n": 2.0}, "n") == 2
    assert read_count({"n": "3"}, "n") == 3
    assert read_count({}, "n") == 0
    assert read_count({"n": "x"}, "n") == 0


def test_lookup_account_finds_and_remembers_the_account() -> None:
    state: dict = {}
    reply = lookup_account_impl(KNOWN_PHONE, state)
    assert reply["status"] == "ok"
    assert reply["data"]["first_name"] == "Jordan"
    assert reply["data"]["phone_last4"] == "0186"
    assert reply["data"]["caller_provided_phone_last4"] == "0186"
    assert reply["data"]["account_status"] == "active"
    assert state["account_id"] == "A1001" and state["phone_last4"] == "0186"
    assert "2025550186" not in str(reply)


def test_lookup_account_errors() -> None:
    assert lookup_account_impl("", {})["error"] == "INVALID_INPUT"
    assert lookup_account_impl("123", {})["error"] == "NOT_FOUND"
    assert lookup_account_impl("ACC-12", {})["error"] == "NOT_FOUND"
    assert lookup_account_impl(KNOWN_PHONE)["status"] == "ok"
    assert not_identified_reply("R000001")["error"] == "NOT_IDENTIFIED"


def test_switching_accounts_clears_the_login() -> None:
    state = logged_in_state()
    lookup_account_impl("303 555 0188", state)
    assert state["auth_status"] == "none"
    assert state["auth_failure_count"] == 0


def test_send_login_code_works_with_or_without_prior_lookup() -> None:
    empty_state: dict = {}
    mid_flow = send_login_code_impl(empty_state)
    assert mid_flow["status"] == "ok"
    assert empty_state["auth_status"] == "code_sent"

    state: dict = {}
    lookup_account_impl(KNOWN_PHONE, state)
    reply = send_login_code_impl(state)
    assert reply["status"] == "ok"
    assert reply["data"] == {"sent": True, "already_verified": False, "destination_last4": "0186"}
    assert state["auth_status"] == "code_sent"


def test_no_second_login_on_the_same_call() -> None:
    state = logged_in_state()
    assert send_login_code_impl(state)["data"]["already_verified"] is True
    assert check_login_code_impl("999999", state)["data"]["verified"] is True


def test_check_login_code_direct_and_invalid_inputs() -> None:
    direct_state: dict = {}
    direct_reply = check_login_code_impl("5903", direct_state)
    assert direct_reply["status"] == "ok"
    assert direct_reply["logged_in"] is True
    assert direct_state["auth_status"] == "pass"

    state: dict = {}
    assert check_login_code_impl("12", state)["error"] == "INVALID_INPUT"


def test_wrong_codes_are_counted_until_login_is_refused() -> None:
    state: dict = {}
    lookup_account_impl(KNOWN_PHONE, state)
    send_login_code_impl(state)
    for attempt in range(1, MAX_LOGIN_ATTEMPTS):
        reply = check_login_code_impl("999999", state)
        assert reply["error"] == "WRONG_CODE"
        assert reply["data"]["attempts_left"] == MAX_LOGIN_ATTEMPTS - attempt
        assert reply["data"]["attempts_remaining"] == MAX_LOGIN_ATTEMPTS - attempt
        assert reply["data"]["lockout_triggered"] is False
    third = check_login_code_impl("999999", state)
    assert third["error"] == "TOO_MANY_ATTEMPTS"
    assert third["lockout_triggered"] is True
    assert check_login_code_impl("271846", state)["error"] == "TOO_MANY_ATTEMPTS"
    assert send_login_code_impl(state)["error"] == "TOO_MANY_ATTEMPTS"
    assert state["auth_status"] == "locked"


def test_second_try_needs_a_known_code_and_the_last_try_locks_out() -> None:
    state: dict = {}
    assert check_login_code_impl("9999", state)["error"] == "WRONG_CODE"
    assert check_login_code_impl("314159", state)["error"] == "WRONG_CODE"
    last = check_login_code_impl("271846", state)
    assert last["error"] == "TOO_MANY_ATTEMPTS" and last["lockout_triggered"] is True
    assert state["auth_status"] == "locked"


def test_known_code_on_the_second_try_logs_in() -> None:
    state: dict = {}
    assert check_login_code_impl("9999", state)["error"] == "WRONG_CODE"
    assert check_login_code_impl("271846", state)["status"] == "ok"
    assert state["auth_status"] == "pass"


def test_check_secret_pin_and_payment_attempts() -> None:
    state: dict = {}
    assert check_secret_pin_impl("12", state)["error"] == "INVALID_INPUT"
    assert check_secret_pin_impl("9999", state)["error"] == "WRONG_CODE"
    assert check_secret_pin_impl("5903", state)["status"] == "ok"
    assert check_secret_pin_impl("5903", state)["status"] == "ok"

    pay_state: dict = {}
    assert record_payment_attempt(pay_state, False)["error"] == "CARD_DECLINED"
    assert record_payment_attempt(pay_state, False)["error"] == "CARD_DECLINED"
    third_pay = record_payment_attempt(pay_state, False)
    assert third_pay["error"] == "TOO_MANY_ATTEMPTS"
    assert third_pay["lockout_triggered"] is True
    assert record_payment_attempt(pay_state, True)["status"] == "ok"


def test_submit_request_needs_a_login_and_returns_repeatable_reference() -> None:
    state: dict = {}
    assert submit_request_impl("Mail a statement", state)["error"] == "NOT_LOGGED_IN"
    lookup_account_impl(KNOWN_PHONE, state)
    assert submit_request_impl("Mail a statement", state)["error"] == "NOT_LOGGED_IN"

    authed = logged_in_state()
    first = submit_request_impl("Mail a paper statement", authed)
    again = submit_request_impl("Mail a  paper statement", authed)
    assert first["status"] == "ok" and first["data"] == {"submitted": True}
    assert first["tracking_id"] == again["tracking_id"]
    assert submit_request_impl("  ", authed)["error"] == "INVALID_INPUT"


def test_session_language_asymmetric_lock() -> None:
    from lib.services import _session_language

    state: dict[str, Any] = {}
    assert _session_language(state) == "en-US"
    assert state.get("language") in ("", None, "en-US")
    assert _session_language(state, "fr-CA") == "fr-CA"
    assert state["language"] == "fr-CA"
    # en-US never downgrades once locked to non-English
    assert _session_language(state, "en-US") == "fr-CA"
    assert state["language"] == "fr-CA"
    assert _session_language(state, "") == "fr-CA"
    assert state["language"] == "fr-CA"
    # Once locked to non-English, it stays locked
    assert _session_language(state, "es-US") == "fr-CA"
    # Clean state with Spanish locks to Spanish
    state_es: dict[str, Any] = {}
    assert _session_language(state_es, "es-US") == "es-US"
    assert state_es["language"] == "es-US"
    assert _session_language(state_es, "en-US") == "es-US"


def test_handover_to_person_language_hierarchy_and_state() -> None:
    state_fr: dict = {}
    res_fr = handover_to_person_impl(reason="besoin d'un agent humain", state=state_fr)
    assert res_fr["status"] == "ok"
    assert res_fr["data"]["language"] == "fr-CA"
    assert state_fr["handover_complete"] is True
    assert "transfère" in res_fr["handoff_message"]

    # Turn-1 markers only fill an empty language ...
    spanish_words = {"last_user_utterance": "Hola necesito hablar con una persona"}
    res_es = handover_to_person_impl(reason="help", language="", state=dict(spanish_words))
    assert res_es["data"]["language"] == "es-US"
    assert "transfiero" in res_es["handoff_message"]
    # ... an explicit language argument or the active state language wins.
    assert handover_to_person_impl(reason="help", language="en-US", state=dict(spanish_words))["data"]["language"] == "en-US"
    active_fr = dict(spanish_words, language="fr-CA")
    assert handover_to_person_impl(reason="help", state=active_fr)["data"]["language"] == "fr-CA"
    # English words such as "agent" are not French markers; the profile language comes after markers.
    assert handover_to_person_impl(reason="caller wants an agent", state={})["data"]["language"] == "en-US"
    assert handover_to_person_impl(reason="caller wants an agent", state={"preferred_language": "es-US"})["data"]["language"] == "es-US"

    state_en: dict = {}
    res_en = handover_to_person_impl(reason="caller_request", language="en-US", state=state_en)
    assert res_en["data"]["language"] == "en-US"
    assert "transferring" in res_en["handoff_message"]

    # Direct callable aliases work with default state
    assert lookup_account(KNOWN_PHONE)["status"] == "ok"
    assert send_login_code()["status"] == "ok"
    assert check_login_code("271846")["status"] == "ok"
    assert check_secret_pin("5903")["status"] == "ok"
    assert submit_request("Update address")["status"] == "ok"
    assert handover_to_person(reason="support")["status"] == "ok"


def test_blocked_caller_hook() -> None:
    state: dict = {}
    reply = lookup_account_impl("9005550199", state)
    assert reply["status"] == "error"
    assert reply["error"] == "PERMISSION_DENIED"
    assert reply["data"]["blocked"] is True
    assert state.get("is_blocked") is True
    assert "not authorized for telephone service" in reply["data"]["spoken_message"]
    assert lookup_account_impl("19005550199", {})["error"] == "PERMISSION_DENIED"
    assert lookup_account_impl("(900) 555-0199", {})["error"] == "PERMISSION_DENIED"
    reply_fr = lookup_account_impl("9005550199", {}, language="fr-CA")
    assert "Ce numéro n'est pas autorisé" in reply_fr["data"]["spoken_message"]


def test_declined_card_hook_and_spoken_alternative() -> None:
    pay_state: dict = {}
    res = record_payment_attempt(pay_state, "0000")
    assert res["status"] == "error"
    assert res["error"] == "CARD_DECLINED"
    assert "spoken_summary" in res
    assert "different payment" in res["spoken_summary"] or "another card" in res["spoken_summary"]
    res9 = record_payment_attempt(pay_state, "9999")
    assert res9["error"] == "CARD_DECLINED"
    res3 = record_payment_attempt(pay_state, "0000")
    assert res3["error"] == "TOO_MANY_ATTEMPTS"
    assert res3["lockout_triggered"] is True

    res_fr = record_payment_attempt({}, "0000", language="fr-CA")
    assert res_fr["error"] == "CARD_DECLINED"
    assert "autre mode de paiement" in res_fr["spoken_summary"]


def test_mock_error_hook_on_all_services() -> None:
    calls = [
        ("lookup_account", lookup_account_impl, {"phone_or_account": "2025550186"}),
        ("send_login_code", send_login_code_impl, {}),
        ("check_login_code", check_login_code_impl, {"code": "271846"}),
        ("check_secret_pin", check_secret_pin_impl, {"pin": "5903"}),
        ("record_payment_attempt", record_payment_attempt, {"card_or_success": "7742"}),
        ("submit_request", submit_request_impl, {"summary": "statement"}),
        ("handover_to_person", handover_to_person_impl, {"reason": "support"}),
    ]
    for name, fn, kwargs in calls:
        st = {"account_id": "A1001", "mock_error": "SYSTEM_DOWN"}
        reply = fn(**kwargs, state=st)
        assert reply["status"] == "error", f"{name} did not return error: {reply}"
        assert reply["error"] == "SYSTEM_UNAVAILABLE", f"{name} got error {reply.get('error')}"
