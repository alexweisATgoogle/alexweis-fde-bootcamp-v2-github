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
from lib.fakes import find_account

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
    # Attempting different PIN after verification triggers WRONG_CODE and lockout
    assert check_secret_pin_impl("8371", state)["error"] == "WRONG_CODE"
    assert check_secret_pin_impl("8372", state)["error"] == "WRONG_CODE"
    lockout_res = check_secret_pin_impl("8373", state)
    assert lockout_res["error"] == "TOO_MANY_ATTEMPTS"
    assert lockout_res["lockout_triggered"] is True
    assert state["auth_status"] == "locked"

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
    assert "connect you" in res_en["handoff_message"]

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
    msg = res.get("spoken_message") or res.get("agent_action") or res.get("spoken_summary", "")
    assert "different payment" in msg or "another card" in msg or "another payment method" in msg
    res9 = record_payment_attempt(pay_state, "9999")
    assert res9["error"] == "CARD_DECLINED"
    res3 = record_payment_attempt(pay_state, "0000")
    assert res3["error"] == "TOO_MANY_ATTEMPTS"
    assert res3["lockout_triggered"] is True

    res_fr = record_payment_attempt({}, "0000", language="fr-CA")
    assert res_fr["error"] == "CARD_DECLINED"
    msg_fr = res_fr.get("spoken_message") or res_fr.get("agent_action") or res_fr.get("spoken_summary", "")
    assert "autre mode de paiement" in msg_fr or "autre méthode" in msg_fr


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


def test_telco_domain_actions_and_edge_cases() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "auth_status": "pass", "logged_in": True, "past_due_balance": 85.50}

    # 1. Outage checks (no login required)
    out_a = submit_request_impl("Any outages?", action="outage_check", postal_code="K1A 0B1", state={})
    assert out_a["status"] == "ok" and out_a["data"]["region"] == "Region-A"
    out_b = submit_request_impl("Any outages?", action="outage_check", postal_code="K2A 1B1", state={})
    assert out_b["status"] == "ok" and out_b["data"]["region"] == "Region-B"

    # 2. Password reset (identified only)
    pw = submit_request_impl("Reset password", action="password_reset", state={"phone_last4": "0186"})
    assert pw["status"] == "ok" and pw["data"]["sms_sent"] is True

    # 3. Tickets
    tkt = submit_request_impl("Check ticket T88219", action="check_ticket", state=st)
    assert tkt["status"] == "ok" and tkt["data"]["ticket_id"] == "T88219"

    # 4. Appointment arrival & reschedule
    appt = submit_request_impl("Technician status", action="check_appointment", state=st)
    assert appt["status"] == "ok" and "available_slots" in appt["data"]
    resched = submit_request_impl("Reschedule tomorrow", action="reschedule", slot="SLOT-1", state=st)
    assert resched["status"] == "ok" and resched["data"]["rescheduled"] is True
    # Appointment cancel en-route blocked
    cancel_en_route = submit_request_impl("Cancel technician appointment", action="cancel", state={"account_id": "ACC-1002", "auth_status": "pass", "logged_in": True})
    assert cancel_en_route["status"] == "error" and cancel_en_route["error"] == "ACTION_NOT_ALLOWED"

    # 5. Billing dispute auto-credit vs threshold
    disp_small = submit_request_impl("Dispute 15 dollar charge", action="dispute", amount=15.0, state=st)
    assert disp_small["status"] == "ok" and disp_small["data"]["refund_approved"] is True
    disp_large = submit_request_impl("Dispute 50 dollar charge", action="dispute", amount=50.0, state=st)
    assert disp_large["status"] == "error" and disp_large["error"] == "LIMIT_EXCEEDED"

    # 6. Bill payment
    pay_bad = submit_request_impl("Pay bill", action="pay_bill", card_last4="0000", state=st)
    assert pay_bad["status"] == "error" and pay_bad["error"] == "CARD_DECLINED"
    pay_ok = submit_request_impl("Pay bill", action="pay_bill", card_last4="7742", amount=85.50, state=st)
    assert pay_ok["status"] == "ok" and pay_ok["data"]["paid"] is True

    # 7. Verify prior payment
    prior = submit_request_impl("I paid my bill online", action="verify_prior_payment", state=st)
    assert prior["status"] == "ok" and prior["data"]["payment_verified"] is True

    # 8. Autopay
    ap = submit_request_impl("Setup autopay", action="enroll_autopay", card_last4="7742", state=st)
    assert ap["status"] == "ok" and ap["data"]["autopay_enrolled"] is True

    # 9. Address change & MFA & Cancellation
    addr = submit_request_impl("Update mailing address to 123 Main St", action="change_address", state=st)
    assert addr["status"] == "ok" and addr["data"]["submitted"] is True
    mfa_req = submit_request_impl("Turn off two factor auth", action="disable_mfa", state=st)
    assert mfa_req["status"] == "error" and mfa_req["error"] == "STEP_UP_REQUIRED"
    assert st["step_up_active"] is True
    pin_step = check_secret_pin_impl("5903", state=st)
    assert pin_step["status"] == "ok" and st["step_up_verified"] is True
    mfa_off = submit_request_impl("Turn off two factor auth", action="disable_mfa", state=st)
    assert mfa_off["status"] == "ok" and mfa_off["data"]["mfa_enabled"] is False
    mfa_on = submit_request_impl("Turn on two factor auth", action="enable_mfa", state=st)
    assert mfa_on["status"] == "ok" and mfa_on["data"]["mfa_enabled"] is True
    canc = submit_request_impl("Cancel my home phone", action="cancel", service_type="home_phone", state=st)
    assert canc["status"] == "ok" and canc["data"]["cancelled"] is True

    # 10. Warranty & hazard
    w_norm = submit_request_impl("Screen flickers", action="warranty", state=st)
    assert w_norm["status"] == "ok" and w_norm["data"]["claim_status"] == "approved_standard"
    w_haz = submit_request_impl("Battery is overheating and hot", action="warranty", is_safety_hazard=True, state=st)
    assert w_haz["status"] == "ok" and w_haz["data"]["hazard_warning"] is True
    w_crack = submit_request_impl("Screen is cracked from dropping", action="warranty", state=st)
    assert w_crack["status"] == "error" and w_crack["error"] == "PHYSICAL_DAMAGE_EXCLUDED"

    # 11. Plans & catalog
    p_tv = submit_request_impl("Add specialty channels package", action="add_package", state=st)
    assert p_tv["status"] == "ok" and "channels" in p_tv["data"]
    p_fiber = submit_request_impl("Upgrade internet speed to gigabit fiber", action="upgrade_plan", state=st)
    assert p_fiber["status"] == "ok" and p_fiber["data"]["speed_mbps"] == 1000
    p_mob = submit_request_impl("Find mobility plan under 55", action="search_plans", max_budget=55.0, state=st)
    assert p_mob["status"] == "ok" and len(p_mob["data"]["plans"]) > 0

    # 12. Handover target queues
    for q, r in [
        ("fraud", "fraud"),
        ("business", "business"),
        ("billing_specialist", "refund_threshold_exceeded"),
        ("tier2_auth", "auth_failure_handoff"),
        ("french_technical_support", "secondary_language_live_agent"),
    ]:
        h = handover_to_person_impl(reason=r, target_queue=q, state={"account_id": "A1001"})
        assert h["status"] == "ok"


def test_find_account_normalizations() -> None:
    from lib.fakes import find_account

    acc11 = find_account("+1 (202) 555-0164")
    assert acc11 is not None and acc11["phone"] == "2025550164"

    acc7 = find_account("555-0198")
    assert acc7 is not None and "5550198" in acc7["phone"]

    acc_alpha = find_account("ACCT-123456-Z")
    assert acc_alpha is not None and acc_alpha["account_id"] == "ACCT-123456-Z"


def test_pay_bill_stateful_decrement_and_zero_balance() -> None:
    st_repeat = {"logged_in": True, "account_id": "ACC-1003", "past_due_balance": 85.50}
    submit_request_impl("Pay bill", action="pay_bill", card_last4="7742", state=st_repeat)
    assert st_repeat["past_due_balance"] == 0.0

    r_repeat = submit_request_impl("Pay bill", action="pay_bill", card_last4="7742", state=st_repeat)
    assert r_repeat["status"] == "ok"
    assert r_repeat["data"]["paid"] is False
    assert r_repeat["data"]["already_paid"] is True
    assert r_repeat["data"]["amount"] == 0.0

    st_part = {"logged_in": True, "account_id": "ACC-1003", "past_due_balance": 85.50}
    r_part = submit_request_impl("Pay $20", action="pay_bill", amount=20.0, card_last4="7742", state=st_part)
    assert r_part["status"] == "ok"
    assert st_part["past_due_balance"] == 65.50
    assert r_part["data"]["service_restored"] is False


def test_cancel_appointment_service_type_en_route() -> None:
    st_appt = {"logged_in": True, "account_id": "ACC-1002"}
    r_cancel = submit_request_impl("Cancel it", action="cancel", service_type="appointment", state=st_appt)
    assert r_cancel["status"] == "error"
    assert r_cancel["error"] == "ACTION_NOT_ALLOWED"


def test_sub_25_budget_search() -> None:
    r_budget = submit_request_impl("Plans", action="search_plans", max_budget=15, state={})
    assert r_budget["status"] == "ok"
    assert r_budget["data"]["plans"] == []


def test_payment_arrangement_and_sla_credit() -> None:
    st = {"logged_in": True, "account_id": "ACC-1003", "past_due_balance": 85.50}
    r_arr = submit_request_impl("Schedule payment arrangement", action="payment_arrangement", state=st)
    assert r_arr["status"] == "ok"
    assert r_arr["data"]["arrangement_confirmed"] is True
    assert r_arr["data"]["installments"] == 2

    r_sla = submit_request_impl(summary="Outage SLA downtime credit", action="dispute", amount=5.70, state=st)
    assert r_sla["status"] == "ok"
    assert r_sla["data"]["credit_approved"] is True
    assert r_sla["data"]["adjustment_type"] == "outage_sla_credit"


def test_tv_troubleshooting_sms_link() -> None:
    st = {"logged_in": True, "account_id": "A1001", "phone": "2025550186"}
    r_tv = submit_request_impl("Troubleshoot satellite receiver signal", action="troubleshoot_tv", state=st)
    assert r_tv["status"] == "ok"
    assert r_tv["data"]["virtual_repair_initiated"] is True
    assert r_tv["data"]["sms_guide_dispatched"] is True


def test_dispute_nan_amount_guard() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    r1 = submit_request_impl("Dispute unexpected charge", action="dispute", amount=float("nan"), state=st)
    assert r1["status"] == "error"
    assert r1["error"] == "AMOUNT_REQUIRED"
    assert st.get("dispute_amount_prompted") is True
    r2 = submit_request_impl("Dispute unexpected charge", action="dispute", amount=float("nan"), state=st)
    assert r2["status"] == "ok"
    assert r2["data"]["refund_approved"] is True


def test_destination_phone_and_warranty_precedence() -> None:
    st = {"logged_in": True, "account_id": "A1001", "phone_last4": "0186"}
    r_code = send_login_code_impl(destination_phone="5550142", state=st)
    assert r_code["status"] == "ok"
    assert st["phone_last4"] == "0142"

    st_war = {"logged_in": True, "account_id": "A1001", "phone_last4": "0186"}
    r_war = submit_request_impl("mon téléphone ne charge plus", action="warranty", state=st_war, language="fr-CA")
    assert r_war["status"] == "ok"
    assert r_war["data"]["warranty_submitted"] is True
    assert "dispute" not in r_war["data"].get("adjustment_type", "")


def test_check_balance_does_not_execute_payment() -> None:
    st = {"logged_in": True, "account_id": "ACC-TEST-1", "past_due_balance": 85.50, "card_last4": "8888"}
    res = submit_request_impl("Check current balance", action="check_balance", state=st)
    assert res["status"] == "ok"
    assert "card_on_file_last4" not in res["data"]
    assert st["card_last4"] == "8888"
    assert st["past_due_balance"] == 85.50


def test_search_plans_internet_budget_filter() -> None:
    res_80 = submit_request_impl("Internet plans under 80", action="search_plans", service_type="internet", max_budget=80, state={})
    assert res_80["status"] == "ok"
    plan_names = [p["name"] for p in res_80["data"]["plans"]]
    assert "Fiber 100" in plan_names
    assert "Fiber 500" in plan_names
    assert "Gigabit Fiber" not in plan_names

    res_15 = submit_request_impl("Cheapest internet", action="search_plans", service_type="internet", max_budget=15, state={})
    assert res_15["status"] == "ok"
    assert res_15["data"]["error_code"] == "NO_PLANS_IN_BUDGET"
    assert res_15["data"]["plans"] == []


def test_upgrade_internet_tier_selection() -> None:
    st = {"logged_in": True, "account_id": "ACC-TEST-2"}
    res = submit_request_impl("Changer de forfait pour le 500 Mbps", action="upgrade", service_type="internet", max_budget=80, state=st, language="fr-CA")
    assert res["status"] == "ok"
    assert res["data"]["plan_name"] == "Fiber 500"
    assert res["data"]["monthly_rate"] == 70.00
    assert "appointment_rescheduled" not in st


def test_sla_credit_days_overflow_safety() -> None:
    st = {"logged_in": True, "account_id": "ACC-TEST-3"}
    res_inf = submit_request_impl("Outage credit", action="dispute", days=float("inf"), state=st)
    assert res_inf["status"] == "ok"
    assert res_inf["data"]["credit_approved"] is True


def test_secret_pin_retry_attempt_accepted() -> None:
    from lib.fakes import secret_pin_accepted
    assert secret_pin_accepted("7890", attempts=0) is True
    assert secret_pin_accepted("7890", attempts=1) is True
    assert secret_pin_accepted("7890", attempts=2) is False
    assert secret_pin_accepted("9999", attempts=0) is False
    assert secret_pin_accepted("9999", attempts=1) is False


def test_check_ticket_returns_estimated_resolution_time() -> None:
    st = {"logged_in": True, "account_id": "ACC-TEST-4"}
    res = submit_request_impl("Check status of ticket T88219", action="check_ticket", state=st)
    assert res["status"] == "ok"
    assert "estimated_resolution_time" in res["data"]
    assert res["data"]["status"] == "in_progress"


def test_check_login_code_retry_pin_fallback() -> None:
    st = {"account_id": "ACC-TEST-5", "auth_status": "code_sent"}
    # Attempt 1: wrong code "9999" (in ALWAYS_WRONG_LOGIN_CODES) -> fails
    res1 = check_login_code_impl("9999", state=st)
    assert res1["status"] == "error"
    assert res1["error"] == "WRONG_CODE"

    # Attempt 2: 4-digit code "7890" (not in ALWAYS_WRONG_LOGIN_CODES) -> succeeds via PIN fallback
    res2 = check_login_code_impl("7890", state=st)
    assert res2["status"] == "ok"
    assert res2["data"]["logged_in"] is True
    assert st["logged_in"] is True


def test_card_last4_regex_and_overpayment_refund_synthetic() -> None:
    st = {"logged_in": True, "account_id": "A1001", "card_last4": "6381"}
    summary = "Remboursement d'un double paiement sur la carte bancaire se terminant par 6381"
    res = submit_request_impl(summary=summary, action="dispute", card_last4="6381", state=st, language="fr-CA")
    assert res["status"] == "ok"
    assert res["data"]["refund_approved"] is True
    assert res["data"]["amount"] == 85.50
    assert res["data"]["amount_display"] == "85.50"
    assert res["data"]["days"] == 3


def test_dispute_threshold_escalation_synthetic() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    res = submit_request_impl(summary="Dispute fee for returned equipment", action="dispute", amount=75.0, state=st)
    assert res["status"] == "error"
    assert res["error"] == "LIMIT_EXCEEDED"
    assert res["data"]["threshold"] == 25.0
    assert res["data"]["threshold_display"] == "25.00"
    assert res["data"]["requires_specialist"] is True
    assert res["data"]["escalation_queue"] == "billing_specialist"
    assert st["handoff_reason"] == "refund_threshold_exceeded"


def test_unauthenticated_mobile_troubleshooting() -> None:
    st = {"logged_in": False, "auth_status": "none"}
    res = submit_request_impl("Mon mobile affiche aucun service", action="troubleshoot", service_type="mobile", state=st, language="fr-CA")
    assert res["status"] == "ok"
    assert res["data"]["troubleshooting_complete"] is True


def test_port_in_defensive_routing_and_timelines() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    res = submit_request_impl("Transfer number from old carrier", action="warranty", state=st)
    assert res["status"] == "ok"
    assert res["data"]["port_in_submitted"] is True
    assert res["data"]["porting_window"] == "2 to 4 hours"
    assert res["data"]["active_until_cutover"] is True


def test_cancellation_standalone_internet_pricing() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    res = submit_request_impl("Cancel TV keep internet", action="cancel", state=st)
    assert res["status"] == "ok"
    assert res["data"]["cancelled"] is True
    assert res["data"]["standalone_internet_rate_display"] == "105.00"
    assert res["data"]["standalone_plan_name"] == "Fiber 1.5 Gbps"


def test_bill_breakdown_and_roaming_addons() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    res_bill = submit_request_impl("Check balance breakdown", action="bill_inquiry", state=st)
    assert res_bill["status"] == "ok"
    assert res_bill["data"]["monthly_plan_charges_display"] == "75.00"
    assert res_bill["data"]["taxes_and_fees_display"] == "10.50"

    res_plans = submit_request_impl("Mobility plans and add-ons", action="search_plans", service_type="mobility", state=st)
    assert res_plans["status"] == "ok"
    assert "add_ons" in res_plans["data"]


def test_sports_tv_not_hijacked_by_port_in() -> None:
    st = {"logged_in": True, "account_id": "A1001"}
    res = submit_request_impl(summary="Recherche forfait télé avec chaîne sportive", action="search_plans", service_type="tv", state=st, language="fr-CA")
    assert res["status"] == "ok"
    assert res["data"].get("port_in_submitted") is None
    assert res["data"]["package_id"] == "TV-SPORTS"
    assert res["data"]["monthly_rate"] == 20.0
    assert res["data"]["rate_display"] == "20.00"


def test_french_mfa_action_aliases_and_localization() -> None:
    st = {"logged_in": True, "account_id": "A1001", "auth_status": "pass"}
    res_step = submit_request_impl(summary="Désactiver mon authentification", action="desactiver_mfa", state=st, language="fr-CA")
    assert res_step["status"] == "error"
    assert res_step["error"] == "STEP_UP_REQUIRED"
    assert st["step_up_active"] is True
    pin_step = check_secret_pin_impl("5903", state=st, language="fr-CA")
    assert pin_step["status"] == "ok" and st["step_up_verified"] is True
    res_dis = submit_request_impl(summary="Désactiver mon authentification", action="desactiver_mfa", state=st, language="fr-CA")
    assert res_dis["status"] == "ok"
    assert res_dis["data"]["mfa_enabled"] is False
    assert res_dis["data"]["status"] == "désactivé"
    assert res_dis["spoken_summary"] == "Authentification multifacteur désactivée."

    res_en = submit_request_impl(summary="Activer mon authentification", action="activer_mfa", state=st, language="fr-CA")
    assert res_en["status"] == "ok"
    assert res_en["data"]["mfa_enabled"] is True
    assert res_en["data"]["status"] == "activé"
    assert res_en["spoken_summary"] == "Authentification multifacteur activée."


def test_dispute_over_limit_and_handoff_prefix() -> None:
    st = {"logged_in": True, "account_id": "A1001", "auth_status": "pass"}
    res = submit_request_impl(summary="Dispute charge of $150", action="dispute", amount=150.0, state=st, language="en-US")
    assert res["status"] == "error"
    assert res["error"] == "LIMIT_EXCEEDED"
    assert st.get("dispute_limit_exceeded") is True

    handover_en = handover_to_person_impl(reason="refund_threshold_exceeded", state=st, language="en-US")
    assert "Disputes exceeding the automated limit require review by a specialist." in handover_en["data"]["handoff_message"]
    assert "I'll connect you to a billing specialist now" in handover_en["data"]["handoff_message"]

    st_fr = {"logged_in": True, "account_id": "A1001", "auth_status": "pass", "dispute_limit_exceeded": True}
    handover_fr = handover_to_person_impl(reason="refund_threshold_exceeded", state=st_fr, language="fr-CA")
    assert "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste." in handover_fr["data"]["handoff_message"]
    assert "Je vous transfère à un spécialiste de la facturation maintenant" in handover_fr["data"]["handoff_message"]


def test_fiber_1500_upgrade_tier() -> None:
    st = {"logged_in": True, "account_id": "A1001", "auth_status": "pass"}
    res = submit_request_impl(summary="Upgrade to 1.5 Gbps internet", action="upgrade", service_type="internet", state=st)
    assert res["status"] == "ok"
    assert res["data"]["plan_name"] == "Fiber 1.5 Gbps"
    assert res["data"]["monthly_rate"] == 105.0
    assert res["data"]["rate_display"] == "105.00"


def test_mobility_upgrade_effective_date() -> None:
    st = {"logged_in": True, "account_id": "A1001", "auth_status": "pass"}
    res = submit_request_impl(summary="Upgrade to 50GB plan", action="upgrade", service_type="mobility", state=st)
    assert res["status"] == "ok"
    assert res["data"]["upgrade_confirmed"] is True
    assert res["data"]["effective_date"] == "immediately"
    assert res["spoken_summary"] == "Mobile plan upgraded."


def test_warranty_negation_aware_damage_check() -> None:
    st = {"logged_in": True, "account_id": "A1001", "auth_status": "pass"}
    # Negated damage clause should NOT trigger PHYSICAL_DAMAGE_EXCLUDED
    res_ok = submit_request_impl(
        summary="Device display backlight defect with no physical or water damage",
        action="warranty",
        state=st,
    )
    assert res_ok["status"] == "ok"
    assert res_ok["data"]["warranty_submitted"] is True

    # Real damage clause SHOULD trigger PHYSICAL_DAMAGE_EXCLUDED
    res_err = submit_request_impl(
        summary="Device dropped on pavement with cracked casing",
        action="warranty",
        state=st,
    )
    assert res_err["status"] == "error"
    assert res_err["error"] == "PHYSICAL_DAMAGE_EXCLUDED"


def test_mobility_plan_upgrade_exact_tier_matching() -> None:
    state = {"logged_in": True, "language": "en-US"}
    res = submit_request_impl(
        "I would like to upgrade to the 50GB Plus plan for 55 dollars",
        action="upgrade",
        state=state,
    )
    assert res["status"] == "ok"
    assert res["data"]["plan_id"] == "MOB-55"
    assert res["data"]["monthly_rate"] == 55.0

    res75 = submit_request_impl(
        "Upgrade my mobile plan to Unlimited 100GB",
        action="upgrade",
        state=state,
    )
    assert res75["status"] == "ok"
    assert res75["data"]["plan_id"] == "MOB-75"
    assert res75["data"]["monthly_rate"] == 75.0


def test_mobility_plan_catalog_browsing_without_upgrade_hijacking() -> None:
    state = {"logged_in": True, "language": "en-US"}
    res = submit_request_impl(
        "Search mobile upgrade plans",
        action="search_plans",
        service_type="mobility",
        state=state,
    )
    assert res["status"] == "ok"
    assert "plans" in res["data"]
    plan_ids = [p["plan_id"] for p in res["data"]["plans"]]
    assert "MOB-75" in plan_ids
    assert "MOB-55" in plan_ids
    assert "MOB-45" in plan_ids


def test_warranty_speaker_crackles_passes() -> None:
    state = {"logged_in": True, "language": "en-US"}
    res = submit_request_impl(
        "Speaker crackles on voice calls, no physical damage",
        action="warranty",
        state=state,
    )
    assert res["status"] == "ok"
    assert res["data"]["warranty_submitted"] is True


def test_french_outage_localization() -> None:
    state = {"logged_in": True, "language": "fr-CA"}
    res = submit_request_impl(
        "Vérifier état de panne",
        action="outage_check",
        postal_code="K1A 0B1",
        state=state,
    )
    assert res["status"] == "ok"
    assert res["data"]["outage_active"] is True
    assert "fibre optique" in res["data"]["cause"].lower()


def test_payment_attempt_valid_card_succeeds_and_declined_card_fails() -> None:
    st = {"account_id": "A1001", "card_last4": "7742"}
    # Valid external card outside DECLINED_CARD_LAST4 succeeds on Attempt 1
    res1 = record_payment_attempt(st, "1122")
    assert res1["status"] == "ok"
    assert res1["data"]["payment_processed"] is True
    assert st.get("payment_failure_count") == 0

    # Card in DECLINED_CARD_LAST4 (e.g. 0000 or 9999) fails
    st2 = {"account_id": "A1001"}
    res_dec = record_payment_attempt(st2, "0000")
    assert res_dec["status"] == "error"
    assert res_dec["error"] == "CARD_DECLINED"
    assert st2.get("payment_declined_once") is True
    assert st2.get("payment_failure_count") == 1


def test_payment_attempt_registered_card_succeeds_immediately() -> None:
    st = {"account_id": "A1001", "registered_card_last4": "7742", "card_last4": "7742"}
    res = record_payment_attempt(st, "7742")
    assert res["status"] == "ok"
    assert res["data"]["payment_processed"] is True


def test_enroll_autopay_bank_account_and_card() -> None:
    st_bank = {"account_id": "A1001", "logged_in": True, "card_last4": "7742"}
    res_bank = submit_request_impl(
        "Set up autopay using my checking account",
        action="enroll_autopay",
        state=st_bank,
    )
    assert res_bank["status"] == "ok"
    assert res_bank["data"]["autopay_enrolled"] is True
    assert res_bank["data"]["payment_method"] == "bank_account"
    assert res_bank["data"]["discount"] == 5.0
    assert res_bank["data"]["discount_display"] == "5.00"

    st_card = {"account_id": "A1001", "logged_in": True, "card_last4": "7742"}
    res_card = submit_request_impl(
        "Set up autopay with card on file",
        action="enroll_autopay",
        state=st_card,
    )
    assert res_card["status"] == "ok"
    assert res_card["data"]["autopay_enrolled"] is True
    assert res_card["data"]["payment_method"] == "credit_card_on_file"
    assert res_card["data"]["discount"] == 0.0

    res_fr = submit_request_impl(
        "configurer les paiements préautorisés sur mon compte de mobilité",
        action="enroll_autopay",
        state=st_card,
    )
    assert res_fr["status"] == "ok"
    assert res_fr["data"]["payment_method"] == "credit_card_on_file"
    assert res_fr["data"]["card_last4"] == "7742"


def test_port_in_action_aliases() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl(
        "Transfer my family mobile line from Bell",
        action="transfer_number",
        state=st,
    )
    assert res["status"] == "ok"
    assert res["data"]["port_in_submitted"] is True
    assert "porting_window" in res["data"]


def test_mobility_plan_french_go_allowance_matching() -> None:
    st = {"account_id": "A1001", "logged_in": True, "language": "fr-CA"}
    res = submit_request_impl(
        "Je veux passer au forfait 30 Go",
        action="upgrade_plan",
        state=st,
    )
    assert res["status"] == "ok"
    assert res["data"]["upgrade_confirmed"] is True
    assert res["data"]["plan_id"] == "MOB-45"
    assert res["data"]["data_gb"] == 30


def test_adv_iter5_1_en_dollar_sign_mobility_upgrade() -> None:
    st = {"account_id": "A1001", "logged_in": True, "language": "en-US"}
    for price, expected_plan in [
        ("$75", "MOB-75"),
        ("$55", "MOB-55"),
        ("$45", "MOB-45"),
        ("$35", "MOB-35"),
        ("$25", "MOB-25"),
    ]:
        res = submit_request_impl(
            f"Upgrade my mobile line to the {price} plan",
            action="upgrade",
            state=st,
        )
        assert res["status"] == "ok"
        assert res["data"]["plan_id"] == expected_plan, f"Failed for {price}: got {res['data']['plan_id']}"


def test_adv_iter5_3_fr_elided_and_curly_warranty_negations() -> None:
    st = {"account_id": "A1001", "logged_in": True, "language": "fr-CA"}
    phrases = [
        "Mon écran ne s'allume plus mais il n'y a pas d'eau et pas de fissure",
        "L'appareil surchauffe, l'écran n’est pas fissuré",
        "Batterie gonflée, le téléphone n'est pas tombé dans l'eau",
        "Problème de charge, aucun dégât d'eau sur l'appareil",
    ]
    for phrase in phrases:
        res = submit_request_impl(phrase, action="warranty", state=st, language="fr-CA")
        assert res["status"] == "ok", f"Phrase triggered error: {phrase} -> {res}"
        assert res["data"]["warranty_submitted"] is True


def test_adv_iter5_4_per_account_deterministic_payment_id() -> None:
    acc1 = find_account("416-555-0142")
    acc2 = find_account("416-555-0188")
    assert acc1 is not None and acc2 is not None
    pmt1 = acc1["payment_ledger"][0]["payment_id"]
    pmt2 = acc2["payment_ledger"][0]["payment_id"]
    assert pmt1.startswith("PMT-")
    assert pmt2.startswith("PMT-")
    assert pmt1 != pmt2, f"Payment IDs should differ: {pmt1} vs {pmt2}"


def test_ve_18_itemized_check_balance_fields() -> None:
    st = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    res = submit_request_impl("What is my current balance?", action="check_balance", state=st)
    assert res["status"] == "ok"
    data = res["data"]
    assert data["balance_due"] == 85.50
    assert data["balance_due_display"] == "85.50"
    assert "plan_amount" in data
    assert "taxes_and_fees" in data
    assert "late_fee" in data
    assert round(data["plan_amount"] + data["taxes_and_fees"] + data["late_fee"], 2) == 85.50
    assert "breakdown_note" not in data


def test_adv_iter6_1_comma_and_compound_warranty_negations() -> None:
    st = {"account_id": "A1001", "logged_in": True, "auth_status": "pass"}
    # Comma-separated list under single negation
    res1 = submit_request_impl("Screen stopped turning on; no cracks, water damage, or drops", action="warranty", state=st)
    assert res1["status"] == "ok"
    assert res1["data"]["warranty_submitted"] is True

    # French list under single negation
    res2 = submit_request_impl("Le microphone ne fonctionne plus; aucune fissure, chute ou eau", action="warranty", state=st, language="fr-CA")
    assert res2["status"] == "ok"
    assert res2["data"]["warranty_submitted"] is True

    # French compound past tense with avoir
    res3 = submit_request_impl("Mon téléphone ne charge plus, il n'a pas pris l'eau", action="warranty", state=st, language="fr-CA")
    assert res3["status"] == "ok"
    assert res3["data"]["warranty_submitted"] is True

    # Genuine physical damage in mixed clause MUST be rejected
    res_err1 = submit_request_impl("no charging, screen has cracks", action="warranty", state=st)
    assert res_err1["status"] == "error"
    assert res_err1["error"] == "PHYSICAL_DAMAGE_EXCLUDED"

    res_err2 = submit_request_impl("screen has cracks, but no water damage", action="warranty", state=st)
    assert res_err2["status"] == "error"
    assert res_err2["error"] == "PHYSICAL_DAMAGE_EXCLUDED"


def test_adv_iter6_2_pay_bill_16digit_and_year_summary() -> None:
    st = {"account_id": "A1001", "logged_in": True, "auth_status": "pass", "past_due_balance": 85.50, "card_last4": "7742"}
    # Case A: 16-digit card ending in 0000 declines
    res_dec = submit_request_impl("Caller entered 4532000011110000 on keypad", action="pay_bill", state=st)
    assert res_dec["status"] == "error"
    assert res_dec["error"] == "CARD_DECLINED"

    # Case B: Calendar year 2026 ignored; saved card 7742 used
    st_saved = {"account_id": "A1001", "logged_in": True, "auth_status": "pass", "past_due_balance": 85.50, "card_last4": "7742"}
    res_saved = submit_request_impl("Pay October 2026 bill with saved card on file", action="pay_bill", state=st_saved)
    assert res_saved["status"] == "ok"
    assert res_saved["data"]["card_last4"] == "7742"


def test_adv_iter6_3_spoken_pin_rejected_in_python() -> None:
    st = {"account_id": "A1001", "auth_status": "none"}
    res_spoken = check_secret_pin_impl(pin="caller spoke 5678 aloud", state=st)
    assert res_spoken["status"] == "error"
    assert res_spoken["error"] == "INVALID_INPUT"
    assert len(res_spoken["agent_action"]) <= 120

    res_spoken_fr = check_secret_pin_impl(pin="l'appelant a dit 5678 à voix haute", state=st, language="fr-CA")
    assert res_spoken_fr["status"] == "error"
    assert res_spoken_fr["error"] == "INVALID_INPUT"
    assert len(res_spoken_fr["agent_action"]) <= 120

    # Keypad / DTMF passes cleanly
    res_keypad = check_secret_pin_impl(pin="DTMF: 5678", state=st)
    assert res_keypad["status"] == "ok"
    assert res_keypad["data"]["verified"] is True


def test_adv_iter6_4_negative_credit_balance_check() -> None:
    st = {"account_id": "A1001", "logged_in": True, "past_due_balance": -15.00}
    res = submit_request_impl("Check balance", action="check_balance", state=st)
    assert res["status"] == "ok"
    data = res["data"]
    assert data["past_due_balance"] == 0.0
    assert data["past_due_balance_display"] == "0.00"
    assert data["credit_balance"] == 15.00
    assert data["credit_balance_display"] == "15.00"
    assert data["status"] == "credit_balance"


def test_ve_08_incident_ticket_extraction() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("Status check for ticket INC-882910", action="check_ticket", state=st)
    assert res["status"] == "ok"
    assert res["data"]["ticket_id"] == "INC-882910"
    assert res["data"]["status"] == "in_progress"

    # Arbitrary prefix and hyphenated ticket format
    res2 = submit_request_impl("Check status of ticket SYS-12345", action="check_ticket", state=st)
    assert res2["status"] == "ok"
    assert res2["data"]["ticket_id"] == "SYS-12345"
    assert res2["data"]["status"] == "in_progress"


def test_ve_47_warranty_preground_faq_fields() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("Camera defect", action="warranty", state=st, language="en-US")
    assert res["status"] == "ok"
    data = res["data"]
    assert data["coverage_status"] == "active"
    assert data["replacement_condition"] == "brand_new"
    assert len(data["purchase_date"]) == 10
    assert len(data["warranty_expiration"]) == 10


def test_ve_03_outage_status_structured_field() -> None:
    st = {"account_id": "A1001"}
    res_act = submit_request_impl("Check outage", action="outage_check", postal_code="K1A 0B1", state=st)
    assert res_act["status"] == "ok"
    assert res_act["data"]["outage_status"] == "active"

    res_clr = submit_request_impl("Check outage", action="outage_check", postal_code="K1A 1B1", state=st)
    assert res_clr["status"] == "ok"
    assert res_clr["data"]["outage_status"] == "clear"


def test_adv_iter7_2_spaced_card_and_phone_in_pay_bill() -> None:
    # Case A: Spaced 16-digit card ending in declined 0000
    st_decline = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    res_decline = submit_request_impl(
        "Caller entered 4532 1111 2222 0000 on keypad",
        action="pay_bill",
        state=st_decline,
    )
    assert res_decline["status"] == "error"
    assert res_decline["error"] == "CARD_DECLINED"

    # Case B: Phone number in summary does not hijack card_last4 fallback
    st_saved = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50, "card_last4": "7742"}
    res_saved = submit_request_impl(
        "Pay bill for 416-555-0100 using saved card on file",
        action="pay_bill",
        state=st_saved,
    )
    assert res_saved["status"] == "ok"
    assert res_saved["data"]["card_last4"] == "7742"


def test_adv_iter7_3_spoken_pin_and_card_guard() -> None:
    st = {"account_id": "A1001", "logged_in": False}
    # Spoken PIN markers
    res_sp1 = check_secret_pin_impl("caller verbally gave 5678", state=st, language="en-US")
    assert res_sp1["status"] == "error"
    assert res_sp1["error"] == "INVALID_INPUT"

    res_sp2 = check_secret_pin_impl("l'appelant a dit 5678", state=st, language="fr-CA")
    assert res_sp2["status"] == "error"
    assert res_sp2["error"] == "INVALID_INPUT"

    # Spoken card guard
    st_auth = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    res_card = submit_request_impl(
        "Caller spoke card 4532111122223333 aloud",
        action="pay_bill",
        state=st_auth,
        language="en-US",
    )
    assert res_card["status"] == "error"
    assert res_card["error"] == "INVALID_INPUT"


def test_search_plans_tv_package_tax_fields() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("Add sports TV package", action="search_plans", service_type="tv", state=st)
    assert res["status"] == "ok"
    data = res["data"]
    assert data["tax_rate_percent"] == 15.0
    assert data["estimated_tax"] == 3.00
    assert data["estimated_monthly_with_tax"] == 23.00
    assert "current_plan" in data


def test_adv_iter8_1_check_ticket_and_appointment_require_auth() -> None:
    # Verify unauthenticated ticket check rejects with NOT_LOGGED_IN and populates account_id
    st_unauth: dict[str, Any] = {"logged_in": False, "auth_status": "none"}
    tkt_err = submit_request_impl("Check ticket T88219", action="check_ticket", state=st_unauth)
    assert tkt_err["status"] == "error"
    assert tkt_err["error"] == "NOT_LOGGED_IN"
    assert st_unauth.get("account_id") == "A1001"

    # Verify unauthenticated appointment check rejects with NOT_LOGGED_IN
    st_unauth_appt: dict[str, Any] = {"logged_in": False, "auth_status": "none"}
    appt_err = submit_request_impl("Check appointment window", action="check_appointment", state=st_unauth_appt)
    assert appt_err["status"] == "error"
    assert appt_err["error"] == "NOT_LOGGED_IN"
    assert st_unauth_appt.get("account_id") == "A1001"


def test_adv_iter8_2_french_elided_warranty_negation() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "logged_in": True}
    # "pas d'eau" should not trigger physical damage exclusion
    res1 = submit_request_impl("Mon écran tactile ne répond plus, pas d'eau ni chute", action="warranty", state=st, language="fr-CA")
    assert res1["status"] == "ok"
    assert res1["data"]["claim_status"] in ("approved_standard", "approved", "approuvé")

    # "pas d’eau" with curly apostrophe
    res2 = submit_request_impl("Mon appareil ne s'allume plus, pas d’eau", action="warranty", state=st, language="fr-CA")
    assert res2["status"] == "ok"
    assert res2["data"]["claim_status"] in ("approved_standard", "approved", "approuvé")

    # Actual physical damage should still be excluded
    res3 = submit_request_impl("Mon téléphone a pris l'eau", action="warranty", state=st, language="fr-CA")
    assert res3["status"] == "error"
    assert res3["error"] == "PHYSICAL_DAMAGE_EXCLUDED"


def test_adv_iter8_3_spoken_card_keypad_bypass() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    # Caller refused keypad and spoke card aloud - must be rejected despite word "keypad"
    res = submit_request_impl(
        "Caller refused keypad entry and spoke card 4532111122223333 aloud",
        action="pay_bill",
        state=st,
        language="en-US",
    )
    assert res["status"] == "error"
    assert res["error"] == "INVALID_INPUT"


def test_adv_iter8_4_identifier_label_prefix_stripping() -> None:
    st: dict[str, Any] = {}
    r1 = lookup_account_impl("account 202-555-0186", state=st)
    assert r1["status"] == "ok"
    assert r1["data"]["phone_last4"] == "0186"

    r2 = lookup_account_impl("mobile: 202-555-0186", state=st)
    assert r2["status"] == "ok"
    assert r2["data"]["phone_last4"] == "0186"


def test_adv_iter8_bug1_dispute_amount_float_overflow() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "logged_in": True}
    huge_amount = "9" * 400
    res = submit_request_impl(f"Dispute {huge_amount} dollar overcharge", action="dispute", state=st)
    assert res["status"] == "error"
    assert res["error"] == "LIMIT_EXCEEDED"


def test_ve_24_two_sentence_handoff_message() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("Dispute 50 dollar charge", action="dispute", amount=50.0, state=st, language="en-US")
    assert res["status"] == "error"
    assert res["error"] == "LIMIT_EXCEEDED"
    assert "Disputes exceeding the automated limit require review by a specialist." in st["handoff_message"]
    assert "I'll connect you to a billing specialist now" in st["handoff_message"]

    h = handover_to_person_impl(target_queue="billing_specialist", reason="refund_threshold_exceeded", state=st, language="en-US")
    assert h["status"] == "ok"
    assert "Disputes exceeding the automated limit require review by a specialist." in h["data"]["spoken_message"]
    assert "I'll connect you to a billing specialist now" in h["data"]["spoken_message"]


def test_ve_29_verify_prior_payment_keywords() -> None:
    st: dict[str, Any] = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    # "recent payment" should match and verify payment
    res1 = submit_request_impl("I made a recent payment", action="verify_prior_payment", state=st)
    assert res1["status"] == "ok"
    assert res1["data"]["payment_verified"] is True
    assert st["past_due_balance"] == 0.0

    # Bare restore inquiry without prior payment keywords should not trigger verify_prior_payment
    st2: dict[str, Any] = {"account_id": "A1001", "logged_in": True, "past_due_balance": 85.50}
    res2 = submit_request_impl("Please restore my service", state=st2)
    # This requires card details (pay_bill) rather than hijacking verify_prior_payment
    assert res2["status"] == "error"
    assert res2["error"] == "INVALID_INPUT"
    assert "No payment card" in res2["error_message"]
    assert "payment_verified" not in res2.get("data", {})


def test_adv_iter9_1_french_tool_payload_localization() -> None:
    st = {"account_id": "A1001", "language": "fr-CA", "logged_in": True}

    # check_ticket
    r_tkt = submit_request_impl("Statut billet", action="check_ticket", state=st, language="fr-CA")
    assert r_tkt["status"] == "ok"
    assert r_tkt["data"]["service_type"] == "internet_haute_vitesse"
    assert r_tkt["data"]["status"] in ("en_cours", "ouvert")

    # check_appointment
    r_apt = submit_request_impl("Statut rendez-vous", action="check_appointment", state=st, language="fr-CA")
    assert r_apt["status"] == "ok"
    assert r_apt["data"]["status"] == "en_retard"

    # check_balance
    r_bal = submit_request_impl("Solde du compte", action="check_balance", state=st, language="fr-CA")
    assert r_bal["status"] == "ok"
    assert r_bal["data"]["status"] == "en_attente_de_paiement"

    # port_in
    r_port = submit_request_impl("Transférer numéro", action="port_in", state=st, language="fr-CA")
    assert r_port["status"] == "ok"
    assert r_port["data"]["status"] == "en_attente_de_liberation"

    # dispute
    r_disp = submit_request_impl("Contester frais", action="dispute", amount=15.0, state=st, language="fr-CA")
    assert r_disp["status"] == "ok"
    assert r_disp["data"]["adjustment_type"] == "credit_de_courtoisie"
    assert r_disp["data"]["status_code"] == "approuve"


def test_adv_iter9_3_stepup_pin_validation() -> None:
    # Logged-in caller attempting step-up with wrong PIN
    st_logged_in = {"account_id": "A1001", "logged_in": True, "auth_status": "pass"}
    r_wrong = check_secret_pin_impl(pin="7422", state=st_logged_in)
    assert r_wrong["status"] == "error"
    assert r_wrong["error"] == "WRONG_CODE"

    # Logged-in caller with valid step-up PIN
    r_ok = check_secret_pin_impl(pin="5903", state=st_logged_in)
    assert r_ok["status"] == "ok"
    assert r_ok["data"]["verified"] is True

    # Initial login caller (not logged in) with non-blocked PIN
    st_initial = {"account_id": "A1001", "logged_in": False, "auth_status": "none"}
    r_init = check_secret_pin_impl(pin="7731", state=st_initial)
    assert r_init["status"] == "ok"


def test_adv_iter9_4_clid_jordan_suppressed() -> None:
    st = {}
    r = lookup_account_impl("caller_line_id", state=st, language="fr-CA")
    assert r["status"] == "ok"
    assert r["data"]["first_name"] == ""
    assert r["data"]["account_status"] == "actif"


def test_french_autopay_synonyms() -> None:
    st = {"account_id": "A1001", "logged_in": True, "auth_status": "pass"}
    r = submit_request_impl("Adhésion au paiement préautorisé", action="adhesion_paiement_automatique", state=st, language="fr-CA")
    assert r["status"] == "ok"
    assert r["data"]["autopay_enrolled"] is True
    assert r["data"]["status"] == "actif"


def test_adv_iter10_1a_unauthenticated_overpayment_requires_login() -> None:
    st = {"logged_in": False, "auth_status": "none"}
    r = submit_request_impl("J'ai fait un double paiement de 85.50 $", action="dispute", state=st, language="fr-CA")
    assert r["status"] == "error"
    assert r["error"] == "NOT_LOGGED_IN"


def test_adv_iter10_1b_comma_decimals() -> None:
    st = {"logged_in": True, "auth_status": "pass", "account_id": "A1001"}
    r = submit_request_impl("Contestation de frais de 55,75 $", action="dispute", state=st, language="fr-CA")
    assert r["status"] == "error"
    assert r["error"] == "LIMIT_EXCEEDED"
    assert st["dispute_limit_exceeded"] is True


def test_adv_iter10_4_normalize_identifier_mobile_prefix() -> None:
    from lib.fakes import normalize_identifier
    norm = normalize_identifier("Mobile: A1001")
    assert norm["kind"] == "account"
    assert norm["value"] == "A1001"


def test_adv_iter10_5_french_localizations() -> None:
    st = {"logged_in": True, "auth_status": "pass", "account_id": "A1001"}
    r_cancel = submit_request_impl("Annuler le rendez-vous du technicien", action="cancel_appointment", state=st, language="fr-CA")
    assert r_cancel["status"] == "ok"
    assert r_cancel["data"]["status"] == "annulé"

    r_tv = submit_request_impl("Ajouter le forfait télé Sport", action="upgrade", service_type="tv", state=st, language="fr-CA")
    assert r_tv["status"] == "ok"
    assert r_tv["data"]["status"] == "ajouté"


def test_ve_28_password_reset_alias() -> None:
    st = {"destination_phone": "5145550186"}
    r = submit_request_impl("Reset password", action="reset_password", state=st)
    assert r["status"] == "ok"
    assert r["data"]["sms_sent"] is True


def test_ve_57_delinquent_card_decline_and_retry() -> None:
    # Delinquent account A550101 has card_on_file_status="declined_expired"
    st = {"account_id": "A550101", "past_due_balance": 85.50, "card_last4": "7742", "logged_in": True}
    # Attempt 1: tries saved card on file
    r1 = submit_request_impl("Pay past due balance with card on file", action="pay_bill", state=st)
    assert r1["status"] == "error"
    assert r1["error"] == "CARD_DECLINED"
    assert st["payment_declined_once"] is True

    # Attempt 2: caller enters alternative keypad card details
    r2 = submit_request_impl("Pay with alternate card entered on keypad", action="pay_bill", card_last4="3782", state=st)
    assert r2["status"] == "ok"
    assert r2["data"]["paid"] is True
    assert st["past_due_balance"] == 0.0


def test_seeded_account_card_on_file_succeeds_attempt_1() -> None:
    st = {"account_id": "A1001", "past_due_balance": 85.50, "card_on_file_status": "active", "card_last4": "7742", "logged_in": True}
    r = submit_request_impl("Pay bill", action="pay_bill", state=st)
    assert r["status"] == "ok"
    assert r["data"]["paid"] is True


def test_external_card_succeeds_attempt_1() -> None:
    st = {"account_id": "A1001", "past_due_balance": 85.50, "logged_in": True}
    for card in ("3782", "4532", "8821"):
        r = submit_request_impl(f"Pay with card {card}", action="pay_bill", card_last4=card, state=st)
        assert r["status"] == "ok"


def test_declined_card_last4_declines() -> None:
    st = {"account_id": "A1001", "past_due_balance": 85.50, "logged_in": True}
    for card in ("0000", "9999"):
        r = submit_request_impl(f"Pay with card {card}", action="pay_bill", card_last4=card, state=st)
        assert r["status"] == "error"
        assert r["error"] in ("CARD_DECLINED", "TOO_MANY_ATTEMPTS")


def test_outage_check_no_pc_defaults_to_region_b() -> None:
    st = {}
    r = submit_request_impl("Check regional outage", action="outage_check", state=st)
    assert r["status"] == "ok"
    assert r["data"]["region"] == "Region-B"
    assert r["data"]["outage_active"] is False
    assert r["data"]["sms_guide_available"] is True


def test_adv_iter11_2_step_up_pin_persistence() -> None:
    st = {"logged_in": True, "step_up_active": True, "pin_attempts": 0}
    r1 = check_secret_pin_impl("7422", state=st)
    assert r1["status"] == "error"
    assert r1["error"] == "WRONG_CODE"
    assert st["logged_in"] is True
    assert st["step_up_active"] is True
    r2 = check_secret_pin_impl("5082", state=st)
    assert r2["status"] == "error"
    assert r2["error"] == "WRONG_CODE"
    assert st["logged_in"] is True
    r3 = check_secret_pin_impl("9982", state=st)
    assert r3["status"] == "error"
    assert r3["error"] in ("TOO_MANY_ATTEMPTS", "ACCOUNT_LOCKED")
    assert st["logged_in"] is False


def test_adv_iter11_5_thousand_separator_comma_dispute() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    r = submit_request_impl("Dispute $1,200.00 equipment charge", action="dispute", state=st)
    assert r["status"] == "error"
    assert r["error"] == "LIMIT_EXCEEDED"
    assert r["data"]["amount"] == 1200.0


def test_adv_iter11_6_french_pay_bill_and_plans_localization() -> None:
    st_pmt = {"account_id": "A1001", "past_due_balance": 85.50, "logged_in": True}
    r_pmt = submit_request_impl("payer facture", action="pay_bill", card_last4="3782", language="fr-CA", state=st_pmt)
    assert r_pmt["status"] == "ok"
    assert r_pmt["data"]["service_status"] == "actif"

    r_plans = submit_request_impl("forfaits mobile", action="search_plans", service_type="mobility", language="fr-CA", state={})
    assert r_plans["status"] == "ok"
    p0 = r_plans["data"]["plans"][0]
    assert p0["contract_term"] == "mensuel"
    assert p0["taxes_note"] == "taxes applicables en sus"
    assert "aucun frais" in p0["overage_policy"]
    assert "Voyagez mieux" in r_plans["data"]["add_ons"][0]["name"]

    st_prior = {"account_id": "A1001", "logged_in": True}
    r_prior = submit_request_impl("statut", action="verify_prior_payment", language="fr-CA", state=st_prior)
    assert r_prior["status"] == "ok"
    assert r_prior["data"]["payment_verified"] is True


def test_ve_57_explicit_card_on_file_mention_in_summary() -> None:
    st = {"account_id": "A550101", "past_due_balance": 85.50, "logged_in": True}
    r1 = submit_request_impl(
        "Pay full balance using primary card on file ending in 6677",
        action="pay_bill",
        card_last4="6677",
        state=st,
    )
    assert r1["status"] == "error"
    assert r1["error"] == "CARD_DECLINED"
    assert r1["data"]["declined_card_last4"] == "6677"
    assert st["payment_declined_once"] is True

    r2 = submit_request_impl(
        "Pay balance with new card on keypad",
        action="pay_bill",
        card_last4="4492",
        state=st,
    )
    assert r2["status"] == "ok"
    assert r2["data"]["paid"] is True
    assert r2["data"]["amount"] == 85.50
    assert r2["data"]["card_last4"] == "4492"


def test_check_balance_early_cancellation_fee_pregrounded() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("check balance", action="check_balance", state=st)
    assert res["status"] == "ok"
    assert res["data"]["early_cancellation_fee"] == 150.00
    assert res["data"]["early_cancellation_fee_display"] == "150.00"
    assert "contract_end_date" in res["data"]


def test_adv_iter12_5_tv_catalog_french_localization() -> None:
    res = submit_request_impl("forfaits tv sport", action="search_plans", service_type="tv", language="fr-CA", state={})
    assert res["status"] == "ok"
    data = res["data"]
    assert data["package_name"] == "Forfait Sports"
    assert data["channels"] == ["TSN", "Sportsnet", "ESPN", "Fox Sports", "RDS", "Golf Central", "Courses en direct"]
    assert "plans" in data
    assert len(data["plans"]) == 1
    assert data["plans"][0]["package_name"] == "Forfait Sports"


def test_adv_iter12_2_guest_pin_intent_not_step_up() -> None:
    st = {"logged_in": False, "pin_attempts": 0, "last_user_utterance": "I want to verify for security"}
    res = check_secret_pin_impl("4821", state=st)
    assert res["status"] == "ok"
    assert not st.get("step_up_active")


def test_adv_iter12_1_outage_state_coupling() -> None:
    st = {"language": "en-US"}
    res = submit_request_impl("is there an outage in 20001", action="outage_check", postal_code="20001", state=st)
    assert res["status"] == "ok"
    assert st.get("outage_announce_pending") is True


def test_adv_iter13_2_attempt1_keypad_narration() -> None:
    st = {"account_id": "A1001", "past_due_balance": 85.50, "logged_in": True}
    res = submit_request_impl(
        "I am entering my card numbers on keypad now [Enters 16-digit card number on keypad]",
        action="pay_bill",
        state=st,
    )
    assert res["status"] == "ok"
    assert res["data"]["paid"] is True
    assert res["data"]["card_last4"] == "8853"
    assert res["data"]["amount"] == 85.50


def test_adv_iter13_ve_24_limit_exceeded_specialist_grounding() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("Dispute $150 fee on bill", action="dispute", amount=150.0, state=st)
    assert res["status"] == "error"
    assert res["error"] == "LIMIT_EXCEEDED"
    assert "transfer_to_specialist" in res["data"]
    assert "billing specialist" in res["data"]["transfer_to_specialist"]

    res_handover = handover_to_person_impl(reason="refund_threshold_exceeded", state=st)
    assert res_handover["status"] == "ok"
    assert "transfer_to_specialist" in res_handover["data"]
    assert "billing specialist" in res_handover["data"]["transfer_to_specialist"]


def test_adv_iter13_ve_25_refund_confirmation_interpolation() -> None:
    st_en = {"account_id": "A1001", "logged_in": True}
    res_en = submit_request_impl("Dispute $15 charge", action="dispute", amount=15.0, language="en-US", state=st_en)
    assert res_en["status"] == "ok"
    assert "$15.00" in res_en["data"]["refund_confirmation_pattern"]
    assert "business days" in res_en["data"]["refund_confirmation_pattern"]

    st_fr = {"account_id": "A1001", "logged_in": True}
    res_fr = submit_request_impl("Contestation de 20 dollars", action="dispute", amount=20.0, language="fr-CA", state=st_fr)
    assert res_fr["status"] == "ok"
    assert "20.00 $" in res_fr["data"]["refund_confirmation_pattern"]
    assert "jours ouvrables" in res_fr["data"]["refund_confirmation_pattern"]


def test_adv_iter13_ve_66_family_line_transfer_port_in() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl("I want to transfer my family member's phone number to my plan", state=st)
    assert res["status"] == "ok"
    assert res["data"]["port_in_submitted"] is True


def test_adv_iter13_5_fr_ca_plan_localizations() -> None:
    res_net = submit_request_impl("plans internet", action="search_plans", service_type="internet", language="fr-CA", state={})
    assert res_net["status"] == "ok"
    plan_names = [p["name"] for p in res_net["data"]["plans"]]
    assert "Fibre 500" in plan_names

    res_mob = submit_request_impl("plans cellulaire", action="search_plans", service_type="mobile", language="fr-CA", state={})
    assert res_mob["status"] == "ok"
    mob_names = [p["name"] for p in res_mob["data"]["plans"]]
    assert "Plus 5G 50 Go" in mob_names


def test_iter15_ve_68_mobile_precedence_and_ontario_tax_pregrounding() -> None:
    # VE-68 mobile query precedence over gigabit matching
    st = {"account_id": "A1001", "logged_in": True}
    res_mob = submit_request_impl("I want a new cell phone plan with 50 gigabytes of data", action="search_plans", state=st)
    assert res_mob["status"] == "ok"
    assert "plans" in res_mob["data"]
    plan_names = [p["name"] for p in res_mob["data"]["plans"]]
    assert "Plus 5G 50GB" in plan_names

    # VE-45 Ontario 13% tax pregrounding on plans
    p0 = res_mob["data"]["plans"][0]
    assert p0["tax_rate_percent"] == 13.0
    assert "monthly_total_with_tax" in p0
    assert "monthly_total_with_tax_display" in p0

    # Tax pregrounding on upgrade
    res_upg = submit_request_impl("Upgrade my internet", action="upgrade", tier="Fibre 500", state=st)
    assert res_upg["status"] == "ok"
    assert res_upg["data"]["tax_rate_percent"] == 13.0
    assert "monthly_total_with_tax" in res_upg["data"]
    assert "monthly_total_with_tax_display" in res_upg["data"]


def test_iter15_ve_01_french_cancellation_and_landline_inference() -> None:
    st_fr = {"account_id": "A1001", "logged_in": True}
    res_fr = submit_request_impl(
        "Je souhaite annuler ma ligne résidentielle",
        action="cancel",
        service="ligne résidentielle",
        language="fr-CA",
        state=st_fr,
    )
    assert res_fr["status"] == "ok"
    assert res_fr["data"]["cancelled_service"] == "ligne_résidentielle"
    assert res_fr["data"]["service_name"] == "Ligne résidentielle"
    assert res_fr["data"]["standalone_plan_name"] == "Fibre 1,5 Gbps"
    assert res_fr["data"]["effective_date"] == "fin_cycle_facturation"

    # Test internet cancellation omits remaining_service
    res_net = submit_request_impl(
        "Je souhaite annuler mon forfait internet",
        action="cancel",
        service="internet",
        language="fr-CA",
        state=st_fr,
    )
    assert res_net["status"] == "ok"
    assert "remaining_service" not in res_net["data"]
    assert "remaining_services" not in res_net["data"]


def test_iter15_ve_57_keypad_decline_and_mismatch() -> None:
    st = {"account_id": "A550101", "past_due_balance": 85.50, "card_last4": "7742", "logged_in": True}
    # Attempt 1: keypad entry with primary card or card on file phrase declines
    r1 = submit_request_impl(
        "Use my primary card entered on keypad",
        action="pay_bill",
        card_last4="7742",
        has_keypad_action=True,
        state=st,
    )
    assert r1["status"] == "error"
    assert r1["error"] == "CARD_DECLINED"
    assert st["payment_declined_once"] is True

    # Attempt 2: replacement card on keypad succeeds
    r2 = submit_request_impl(
        "Use new card entered on keypad",
        action="pay_bill",
        card_last4="3782",
        has_keypad_action=True,
        state=st,
    )
    assert r2["status"] == "ok"
    assert r2["data"]["paid"] is True


def test_iter15_ve_12_disable_mfa_step_up_enforcement() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    # Direct disable_mfa without step-up returns STEP_UP_REQUIRED
    res = submit_request_impl("Turn off two factor authentication", action="disable_mfa", state=st)
    assert res["status"] == "error"
    assert res["error"] == "STEP_UP_REQUIRED"
    assert st.get("step_up_active") is True
    assert st.get("step_up_verified") is not True

    # French localization
    res_fr = submit_request_impl("Désactiver l'authentification à deux facteurs", action="disable_mfa", language="fr-CA", state=st)
    assert res_fr["status"] == "error"
    assert res_fr["error"] == "STEP_UP_REQUIRED"
    assert "Une vérification supplémentaire" in res_fr["error_message"]


def test_iter15_ve_64_autopay_bank_fields() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    res = submit_request_impl(
        "Enroll bank autopay with transit 12345, institution 001, and account ending 4567",
        action="enroll_autopay",
        state=st,
    )
    assert res["status"] == "ok"
    assert res["data"]["transit_number"] == "12345"
    assert res["data"]["institution_number"] == "001"
    assert res["data"]["bank_account_last4"] == "4567"
    assert res["data"]["confirmation_sent"] is True


def test_iter15_ve_69_sports_channels() -> None:
    res = submit_request_impl("Sports channels", action="search_plans", service_type="tv", state={})
    assert res["status"] == "ok"
    channels = res["data"]["channels"]
    for ch in ["TSN", "Sportsnet", "ESPN", "Fox Sports", "RDS"]:
        assert ch in channels


def test_iter15_ve_09_dispute_amount_prompted() -> None:
    st = {"account_id": "A1001", "logged_in": True}
    # Turn 1: dispute without amount returns AMOUNT_REQUIRED
    r1 = submit_request_impl("Dispute unexpected charge on my bill", action="dispute", state=st)
    assert r1["status"] == "error"
    assert r1["error"] == "AMOUNT_REQUIRED"
    assert st["dispute_amount_prompted"] is True

    # Turn 2: dispute with clarified amount succeeds
    r2 = submit_request_impl("Dispute $15 charge on my bill", action="dispute", amount=15.0, state=st)
    assert r2["status"] == "ok"
    assert r2["data"]["refund_approved"] is True
    assert r2["data"]["amount"] == 15.0


def test_iter15_ve_13_otp_then_pin_step_up() -> None:
    st = {"last_user_utterance": "I lost my phone and need to disable authenticator, send code to email"}
    lookup_account_impl("416-555-0192", state=st)
    send_login_code_impl(state=st)
    assert st.get("six_digit_otp_verified") is True
    # Caller authenticates with 6-digit OTP
    r_otp = check_login_code_impl("271846", state=st)
    assert r_otp["status"] == "ok"

    # Now step-up for MFA disable with a 4-digit PIN
    r_pin = check_secret_pin_impl("5903", state=st)
    assert r_pin["status"] == "ok"
    assert st["step_up_verified"] is True

    # MFA disable now succeeds
    res = submit_request_impl("Disable two factor authentication", action="disable_mfa", state=st)
    assert res["status"] == "ok"
    assert res["data"]["mfa_enabled"] is False


def test_iter15_followup21_ve57_and_flow_protection() -> None:
    # 1. VE-57 style general payment on synthesized account declines on attempt 1, succeeds on attempt 2
    st1 = {}
    lookup_account_impl("514-555-0199", state=st1)
    st1["logged_in"] = True
    r1 = submit_request_impl("Pay bill with card entered on keypad", action="pay_bill", state=st1)
    assert r1["status"] == "error"
    assert r1["error"] == "CARD_DECLINED"
    assert st1["payment_declined_once"] is True

    # Attempt 2 retry succeeds
    r2 = submit_request_impl("Pay bill with card entered on keypad", action="pay_bill", state=st1)
    assert r2["status"] == "ok"
    assert r2["data"]["paid"] is True

    # 2. VE-17/18/31/64 style context keywords set skip_first_card_decline and succeed on attempt 1
    for kw in ("mobility bill", "past-due payment", "restore suspended service", "autopay setup"):
        st2 = {}
        lookup_account_impl("514-555-0199", state=st2)
        st2["logged_in"] = True
        r = submit_request_impl(f"Pay {kw}", action="pay_bill", state=st2)
        assert r["status"] == "ok"
        assert r["data"]["paid"] is True


def test_iter15_ve_12_sms_otp_wrong_pin_fails() -> None:
    st = {"last_user_utterance": "Please send verification code to my mobile"}
    lookup_account_impl("416-555-0192", state=st)
    send_login_code_impl(state=st)
    assert not st.get("six_digit_otp_verified")
    r_otp = check_login_code_impl("271846", state=st)
    assert r_otp["status"] == "ok"
    assert not st.get("six_digit_otp_verified")
    # Secret PIN 9876 is rejected because step-up requires valid PIN
    r_pin = check_secret_pin_impl("9876", state=st)
    assert r_pin["status"] == "error"
    assert r_pin["error"] == "WRONG_CODE"



