from lib.fakes import (
    ALWAYS_WRONG_LOGIN_CODES,
    SPOKEN_LINES,
    find_account,
    login_code_accepted,
    normalize_identifier,
    normalize_identifier,
    normalize_code,
    only_digits,
    read_count,
    relative_date,
    resolve_locale,
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
