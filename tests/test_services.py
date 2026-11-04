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
    tkt = submit_request_impl("Check ticket T88219", action="check_ticket", state={})
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
    r = submit_request_impl("Dispute unexpected charge", action="dispute", amount=float("nan"), state=st)
    assert r["status"] == "ok"
    assert r["data"]["refund_approved"] is True


def test_destination_phone_and_warranty_precedence() -> None:
    st = {"logged_in": True, "account_id": "A1001", "phone_last4": "0186"}
    r_code = send_login_code_impl(destination_phone="5550199", state=st)
    assert r_code["status"] == "ok"
    assert st["phone_last4"] == "0199"

    st_war = {"logged_in": True, "account_id": "A1001", "phone_last4": "0186"}
    r_war = submit_request_impl("mon téléphone ne charge plus", action="warranty", state=st_war, language="fr-CA")
    assert r_war["status"] == "ok"
    assert r_war["data"]["warranty_submitted"] is True
    assert "dispute" not in r_war["data"].get("adjustment_type", "")


def test_check_balance_does_not_execute_payment() -> None:
    st = {"logged_in": True, "account_id": "ACC-TEST-1", "past_due_balance": 85.50, "card_last4": "8888"}
    res = submit_request_impl("Check current balance", action="check_balance", state=st)
    assert res["status"] == "ok"
    assert res["data"]["past_due_balance"] == 85.50
    assert res["data"]["card_on_file_last4"] == "8888"
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





