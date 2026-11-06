from lib.fakes import (
    ALWAYS_WRONG_LOGIN_CODES,
    SPOKEN_LINES,
    find_account,
    login_code_accepted,
    normalize_identifier,
    normalize_code,
    only_digits,
    read_count,
    relative_date,
    resolve_locale,
    resolve_postal_code_region,
    secret_pin_accepted,
    spoken_line,
)


def test_only_digits_and_normalize_code() -> None:
    assert only_digits("(202) 555-0186") == "2025550186"
    assert only_digits("") == ""
    assert normalize_code(5903.0) == "5903"
    assert normalize_code("59-03") == "5903"
    assert normalize_code(271846) == "271846"
    assert normalize_code(None) == ""
    assert normalize_code(True) == ""


def test_read_count_and_locales() -> None:
    assert read_count({"a": 2.0}, "a") == 2
    assert read_count(None, "a") == 0
    assert resolve_locale("fr") == "fr-CA"
    assert resolve_locale("es-MX") == "es-US"
    assert resolve_locale("en-GB") == "en-US"
    assert resolve_locale("") == "en-US"
    assert "0186" in spoken_line("code_sent", "en-US", destination_last4="0186")
    assert set(SPOKEN_LINES["handover"]) == {"en-US", "fr-CA", "es-US"}


def test_normalize_identifier() -> None:
    assert normalize_identifier("2025550186") == {"kind": "phone", "value": "2025550186"}
    assert normalize_identifier("+1 (202) 555-0186") == {"kind": "phone", "value": "2025550186"}
    assert normalize_identifier("+44 20 7946 0958") == {"kind": "international_phone", "value": "+442079460958"}
    assert normalize_identifier("0044 20 7946 0958") == {"kind": "international_phone", "value": "+442079460958"}
    assert normalize_identifier("12345") == {"kind": "account", "value": "12345"}
    assert normalize_identifier("REF-12345") == {"kind": "reference", "value": "REF-12345"}
    assert normalize_identifier("12345-REF") == {"kind": "reference", "value": "12345-REF"}
    assert normalize_identifier("unknown-word") == {"kind": "unknown", "value": "unknown-word"}


def test_relative_date() -> None:
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert relative_date(0) == today
    assert len(relative_date(3)) == 10


def test_known_account_by_phone_or_account_number() -> None:
    by_phone = find_account("202-555-0186")
    assert by_phone is not None and by_phone["account_id"] == "A1001"
    assert by_phone["caller_provided_phone_last4"] == "0186"
    by_id = find_account("a1001")
    assert by_id is not None and by_id["account_id"] == "A1001"
    assert by_id["caller_provided_phone_last4"] == ""
    assert find_account("ACC-1001") == by_id


def test_other_nine_or_ten_digit_numbers_get_a_made_up_record() -> None:
    record = find_account("303 555 0188")
    assert record is not None
    assert record["phone"] == "3035550188" and record["first_name"] == ""
    nine_digit = find_account("303555019")
    assert nine_digit is not None and nine_digit["phone"] == "303555019"


def test_short_or_alpha_numbers_are_not_found() -> None:
    assert find_account("12345") is None
    assert find_account("ACC-12") is None
    assert find_account("ABC982736451") is None
    assert find_account("") is None


def test_login_ladder_for_codes_and_secret_pins() -> None:
    assert login_code_accepted("271846")
    assert login_code_accepted("314159", attempts=0)  # first try: any 4-10 digit code
    assert not login_code_accepted("314159", attempts=1)  # second try: only known codes
    assert login_code_accepted("271846", attempts=1)
    assert not login_code_accepted("271846", attempts=2)  # last try: always wrong (lockout)
    assert login_code_accepted("271846", attempts=2, max_attempts=5)
    assert secret_pin_accepted("5903", attempts=1)
    assert not secret_pin_accepted("5903", attempts=2)
    assert not login_code_accepted("12")
    assert all(not login_code_accepted(code) for code in ALWAYS_WRONG_LOGIN_CODES)


def test_login_ladder_extended_invariants() -> None:
    expected_wrong = {"0000", "000000", "1111", "111111", "2222", "8888", "9999", "999999"}
    assert expected_wrong == ALWAYS_WRONG_LOGIN_CODES
    assert len(ALWAYS_WRONG_LOGIN_CODES) <= 8
    for c in expected_wrong:
        assert not login_code_accepted(c, attempts=0)
        assert not secret_pin_accepted(c, attempts=0)

    # Secret PIN 2nd attempt leniency with synthetic values
    assert secret_pin_accepted("6472", attempts=1) is True
    assert secret_pin_accepted("8392", attempts=1) is True

    # Secret PIN 3rd attempt lockout
    assert secret_pin_accepted("5903", attempts=2) is False
    assert secret_pin_accepted("5678", attempts=2) is False


def test_resolve_postal_code_region_generic_sectors() -> None:
    # Even sector digit (index 3) -> Region-A (active outage)
    assert resolve_postal_code_region("K1A 0B1") == "Region-A"
    assert resolve_postal_code_region("A1A 0B1") == "Region-A"
    # Odd sector digit (index 3) -> Region-B (normal operation)
    assert resolve_postal_code_region("K1A 1B1") == "Region-B"
    assert resolve_postal_code_region("A1A 1B1") == "Region-B"
    # 3-char FSA fallback (index 1) with generic synthetic codes (0 hits in bench/dev)
    assert resolve_postal_code_region("K2P") == "Region-A"
    assert resolve_postal_code_region("K1P") == "Region-B"


def test_secret_pin_step_up_validation() -> None:
    # Initial login lenient
    assert secret_pin_accepted("7731", attempts=0, is_step_up=False) is True
    # Step-up accepts only VALID_PINS
    assert secret_pin_accepted("5903", attempts=0, is_step_up=True) is True
    assert secret_pin_accepted("5678", attempts=0, is_step_up=True) is True
    assert secret_pin_accepted("7731", attempts=0, is_step_up=True) is False
    assert secret_pin_accepted("7422", attempts=0, is_step_up=True) is False


def test_synthesized_account_payment_ledger() -> None:
    acc = find_account("416-555-0142")
    assert acc is not None
    assert len(acc["payment_ledger"]) == 1
    ledger_entry = acc["payment_ledger"][0]
    assert ledger_entry["status"] == "cleared"
    assert ledger_entry["amount"] == 85.50
    assert ledger_entry["payment_id"].startswith("PMT-")


def test_ve_61_hyphenated_alphanumeric_account_id() -> None:
    norm = normalize_identifier("8829-XJ-01")
    assert norm["kind"] == "reference"
    assert norm["value"] == "8829-XJ-01"

    acc = find_account("8829-XJ-01")
    assert acc is not None
    assert acc["account_id"] == "8829-XJ-01"
    assert len(acc["payment_ledger"]) == 1
    assert acc["payment_ledger"][0]["payment_id"].startswith("PMT-")

    # Numeric phone is NEVER hijacked (Override A1: use generic 416-555-0100)
    assert normalize_identifier("416-555-0100")["kind"] == "phone"


def test_secret_pin_accepted_length_restriction() -> None:
    # 4 to 6 digits accepted
    assert secret_pin_accepted("5678", attempts=0) is True
    assert secret_pin_accepted("123456", attempts=0) is True
    # 9-digit account numbers rejected
    assert secret_pin_accepted("928374651", attempts=0) is False
    assert secret_pin_accepted("123", attempts=0) is False


def test_adv_iter7_1_normalize_label_prefix() -> None:
    res = normalize_identifier("phone: 202-555-0186")
    assert res["kind"] == "phone"
    assert res["value"] == "2025550186"

    res_fr = normalize_identifier("numéro: 202-555-0186")
    assert res_fr["kind"] == "phone"
    assert res_fr["value"] == "2025550186"

    acc = find_account("phone: 202-555-0186")
    assert acc is not None
    assert acc["account_id"] == "A1001"


def test_acc_identifier_normalization_and_synthesis() -> None:
    res1 = normalize_identifier("ACC-10200")
    assert res1["kind"] == "account"
    assert res1["value"] == "ACC-10200"

    acc1 = find_account("ACC-10200")
    assert acc1 is not None
    assert acc1["account_id"] == "ACC-10200"
    assert acc1["status"] == "active"
    assert len(acc1["payment_ledger"]) >= 1

    res2 = normalize_identifier("ACC-30400")
    assert res2["kind"] == "account"
    assert res2["value"] == "ACC-30400"

    acc2 = find_account("ACC-30400")
    assert acc2 is not None
    assert acc2["account_id"] == "ACC-30400"


def test_adv_iter11_1_label_prefixed_phone_lookup() -> None:
    acc_en = find_account("Mobile: 416-555-0101")
    assert acc_en is not None
    assert acc_en["account_id"] == "A550101"

    acc_fr = find_account("Téléphone: 613-555-0123")
    assert acc_fr is not None
    assert acc_fr["account_id"] == "A550123"


def test_adv_iter11_3_find_account_deepcopy_isolation() -> None:
    acc1 = find_account("ACC-88291")
    assert acc1 is not None
    acc1["status"] = "mutated_status"
    acc1["payment_ledger"].append({"extra": True})

    acc2 = find_account("ACC-88291")
    assert acc2 is not None
    assert acc2["status"] == "active"
    assert len(acc2["payment_ledger"]) == 1


def test_adv_iter12_3_multiword_prefix_and_numeric_caching() -> None:
    acc_12_3a = find_account("Phone number: 416-555-0101")
    assert acc_12_3a is not None
    assert acc_12_3a["account_id"] == "A550101"
    assert acc_12_3a["phone"] == "4165550101"

    acc_12_3b = find_account("A550101")
    assert acc_12_3b is not None
    assert acc_12_3b["account_id"] == "A550101"
    assert acc_12_3b["phone"] == "2025550101"

    acc_num = find_account("847291034")
    assert acc_num is not None
    assert acc_num["card_on_file_status"] == "active"
    assert acc_num["region"] == "Region-B"

def test_adv_iter13_1_cold_process_stability_and_name_synthesis() -> None:
    from lib.fakes import _SYNTHESIZED_ACCOUNTS

    _SYNTHESIZED_ACCOUNTS.clear()
    acc_cold = find_account("A880144")
    assert acc_cold is not None
    assert acc_cold["phone_last4"] == "0144"
    assert acc_cold["phone"] == "2025550144"

    acc_name = find_account("Alex Morgan")
    assert acc_name is not None
    assert acc_name["first_name"] == "Alex"
    assert acc_name["card_on_file_status"] == "active"

    acc_phone = find_account("416-555-0192")
    assert acc_phone is not None
    assert acc_phone["card_on_file_status"] == "active"


def test_adv_iter14_5_find_account_cache_order_independence() -> None:
    from lib.fakes import _SYNTHESIZED_ACCOUNTS

    # Order 1: Phone lookup first, then account ID lookup
    _SYNTHESIZED_ACCOUNTS.clear()
    acc_ph1 = find_account("416-555-0188")
    assert acc_ph1 is not None
    assert acc_ph1["card_on_file_status"] == "active"
    acc_id1 = find_account("A550188")
    assert acc_id1 is not None
    assert acc_id1["card_on_file_status"] == "declined_expired"

    # Order 2: Account ID lookup first, then phone lookup
    _SYNTHESIZED_ACCOUNTS.clear()
    acc_id2 = find_account("A550188")
    assert acc_id2 is not None
    assert acc_id2["card_on_file_status"] == "declined_expired"
    acc_ph2 = find_account("416-555-0188")
    assert acc_ph2 is not None
    assert acc_ph2["card_on_file_status"] == "active"

