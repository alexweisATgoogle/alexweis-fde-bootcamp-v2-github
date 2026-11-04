import lib.speech as speech
from lib.speech import (
    clean_agent_speech,
    clean_speech,
    enforce_handover_utterance,
    mask_long_numbers,
    strip_markdown,
)


def test_long_numbers_keep_only_their_last_4_digits() -> None:
    assert mask_long_numbers("Call 2025550186 now") == "Call 0186 now"
    assert mask_long_numbers("It is (202) 555-0186.") == "It is 0186."
    assert mask_long_numbers("Card 7742 8888 9999 7742 is on file") == "Card 7742 is on file"


def test_short_numbers_dates_and_amounts_are_left_alone() -> None:
    text = "Reference R271846, due 2026-10-08 14:30, amount $7,742.56, code 271846."
    assert mask_long_numbers(text) == text


def test_speakable_numbers_are_kept(monkeypatch) -> None:
    monkeypatch.setattr(speech, "SPEAKABLE_NUMBERS", frozenset({"18005550186"}))
    assert mask_long_numbers("Call 1-800-555-0186.") == "Call 1-800-555-0186."


def test_strip_markdown() -> None:
    assert strip_markdown("**Done.** Use `code`.\n## Next") == "Done. Use code.\nNext"
    assert strip_markdown("Press # to finish") == "Press # to finish"


def test_clean_speech_and_caller_last4_preference() -> None:
    assert clean_speech("**Your number is 2025550186.**") == "Your number is 0186."
    params = {"phone_last4": "0186", "caller_provided_phone_last4": "0142"}
    assert (
        clean_agent_speech("Your number ending in 0143 is verified.", params)
        == "Your number ending in 0142 is verified."
    )
    msg = "I'm transferring you to a member of our team now. Thank you for your patience."
    handover_state = {"handover_complete": True, "handoff_message": msg}
    assert enforce_handover_utterance("", handover_state) == msg
    assert enforce_handover_utterance("Hold on.", handover_state) == "Hold on."
    step_line = "I'm transferring you to a billing specialist now."
    assert enforce_handover_utterance(step_line, handover_state) == step_line
    assert enforce_handover_utterance("", {"handover_complete": False, "handoff_message": msg}) == ""


def test_resolve_handover_fallback() -> None:
    from lib.speech import resolve_handover_fallback

    assert "business account" in resolve_handover_fallback("business_handoff", "en-US")
    assert "compte d'affaires" in resolve_handover_fallback("business_handoff", "fr-CA")
    assert "facing challenges" in resolve_handover_fallback("fraud_escalation", "en-US")
    assert "éprouvez des difficultés" in resolve_handover_fallback("fraud_escalation", "fr-CA")
    assert "connect you to a representative" in resolve_handover_fallback("default", "en-US")
    assert "transfère à un représentant" in resolve_handover_fallback("default", "fr-CA")
    assert "specialist" in resolve_handover_fallback("transfer_to_specialist", "en-US")
    assert "sécurité" in resolve_handover_fallback("auth_failure", "fr-CA")

