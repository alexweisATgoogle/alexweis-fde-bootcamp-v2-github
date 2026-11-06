import lib.speech as speech
from lib.speech import (
    clean_agent_speech,
    clean_speech,
    enforce_handover_utterance,
    enforce_outage_utterance,
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


def test_enforce_handover_utterance_threshold_guarantee() -> None:
    # 1. English empty text
    st_en = {"dispute_limit_exceeded": True, "language": "en-US"}
    res_empty_en = enforce_handover_utterance("", st_en)
    assert "Disputes exceeding the automated limit require review by a specialist." in res_empty_en
    assert "billing specialist now" in res_empty_en

    # 2. French empty text
    st_fr = {"dispute_limit_exceeded": True, "language": "fr-CA"}
    res_empty_fr = enforce_handover_utterance("", st_fr)
    assert "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste." in res_empty_fr
    assert "spécialiste de la facturation maintenant" in res_empty_fr

    # 3. S1-only input in English (appends S2)
    s1_en = "Disputes exceeding the automated limit require review by a specialist."
    res_s1_en = enforce_handover_utterance(s1_en, st_en)
    assert res_s1_en.startswith(s1_en)
    assert "billing specialist now" in res_s1_en

    # 4. S2-only input in English (prepends S1)
    s2_en = "I will transfer you to a billing specialist now."
    res_s2_en = enforce_handover_utterance(s2_en, st_en)
    assert "Disputes exceeding the automated limit require review by a specialist." in res_s2_en
    assert res_s2_en.endswith(s2_en)

    # 5. Full 2 sentences already present
    full_en = f"{s1_en} {s2_en}"
    assert enforce_handover_utterance(full_en, st_en) == full_en

    # 6. Handover reason = refund_threshold_exceeded or dispute_limit_exceeded
    st_reason = {"handoff_reason": "refund_threshold_exceeded", "language": "en-US"}
    assert "Disputes exceeding the automated limit" in enforce_handover_utterance("", st_reason)

    st_reason2 = {"handoff_reason": "dispute_limit_exceeded", "language": "fr-CA"}
    assert "dépassant la limite automatisée" in enforce_handover_utterance("", st_reason2)


def test_adv_iter12_1_outage_credit_guard() -> None:
    txt = "I have approved a credit of $5.70 on your account. Your reference is SUB-9912. Note that there is an active outage in your area."
    st = {"outage_announce_pending": True, "language": "en-US"}
    res = enforce_outage_utterance(txt, st)
    assert res == txt
    assert st["outage_announce_pending"] is False


def test_adv_iter12_4_handover_utterance_with_adverbs() -> None:
    txt = "Disputes exceeding the automated limit require review by a specialist. I will connect you with a representative right away."
    st = {"dispute_limit_exceeded": True, "language": "en-US"}
    res = enforce_handover_utterance(txt, st)
    assert "Disputes exceeding the automated limit require review by a specialist." in res
    assert "representative right away" not in res
    assert "billing specialist now" in res

    txt_fr = "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste. Je vous transfère à un représentant tout de suite."
    st_fr = {"dispute_limit_exceeded": True, "language": "fr-CA"}
    res_fr = enforce_handover_utterance(txt_fr, st_fr)
    assert "spécialiste de la facturation maintenant" in res_fr


def test_enforce_outage_negative_or_clear() -> None:
    # State has outage_active False
    txt1 = "I checked your account and there is no active outage in your area."
    st1 = {"outage_active": False, "outage_status": "clear", "language": "en-US"}
    assert enforce_outage_utterance(txt1, st1) == txt1

    # Text explicitly indicates no outage
    txt2 = "There is no active outage in your area right now."
    st2 = {"language": "en-US"}
    assert enforce_outage_utterance(txt2, st2) == txt2

    txt3 = "Je confirme qu'il n'y a aucune panne active dans votre secteur."
    st3 = {"language": "fr-CA"}
    assert enforce_outage_utterance(txt3, st3) == txt3


def test_adv_iter13_3_near_future_french_transfer_strip() -> None:
    st_fr = {"dispute_limit_exceeded": True, "language": "fr-CA"}
    txt_fr = "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste. Je vais vous transférer à un représentant immédiatement."
    res_fr = enforce_handover_utterance(txt_fr, st_fr)
    assert "représentant" not in res_fr
    assert "spécialiste de la facturation maintenant" in res_fr

    txt_fr2 = "Les contestations dépassant la limite automatisée nécessitent l'examen d'un spécialiste. Je vais vous mettre en contact avec un représentant."
    res_fr2 = enforce_handover_utterance(txt_fr2, st_fr)
    assert "mettre en contact avec" not in res_fr2
    assert "spécialiste de la facturation maintenant" in res_fr2


def test_adv_iter13_4_service_qualified_outage_expansion() -> None:
    from lib.fakes import spoken_line

    st_en = {"outage_announce_pending": True, "language": "en-US"}
    txt_en = "I see there is an active internet outage in your area. We are investigating."
    res_en = enforce_outage_utterance(txt_en, st_en)
    assert res_en == spoken_line("outage_active", "en-US")
    assert st_en["outage_announce_pending"] is False

    st_fr = {"outage_announce_pending": True, "language": "fr-CA"}
    txt_fr = "Je constate qu'il y a une panne réseau active dans votre secteur."
    res_fr = enforce_outage_utterance(txt_fr, st_fr)
    assert res_fr == spoken_line("outage_active", "fr-CA")
    assert st_fr["outage_announce_pending"] is False
