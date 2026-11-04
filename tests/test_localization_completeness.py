from __future__ import annotations

import re
from typing import Any
import pytest

from lib.fakes import SPOKEN_LINES
from lib.services import (
    check_login_code_impl,
    check_secret_pin_impl,
    handover_to_person_impl,
    lookup_account_impl,
    send_login_code_impl,
    submit_request_impl,
)

SUPPORTED_LOCALES = ["en-US", "fr-CA", "es-US"]
SIBLING_KEY_RE = re.compile(r"_(?:en|fr|es|de|pt|it)(?:[-_][a-z0-9]{2,4})?$", re.IGNORECASE)


def _check_no_sibling_keys(obj: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and SIBLING_KEY_RE.search(k.lower()):
                findings.append(f"{path}.{k}" if path else str(k))
            findings.extend(_check_no_sibling_keys(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            findings.extend(_check_no_sibling_keys(item, f"{path}[{i}]"))
    return findings


def test_spoken_lines_all_supported_locales_present() -> None:
    for key, table in SPOKEN_LINES.items():
        for loc in SUPPORTED_LOCALES:
            assert loc in table, f"Missing locale {loc} in SPOKEN_LINES[{key}]"
            assert not table[loc].startswith("[translate:"), f"Untranslated line in SPOKEN_LINES[{key}][{loc}]"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_all_tools_reply_contract_and_localization(locale: str) -> None:
    base_state: dict[str, Any] = {
        "account_id": "A1001",
        "phone_last4": "0186",
        "auth_status": "pass",
        "logged_in": True,
        "language": locale,
    }

    test_calls = [
        ("lookup_account", lookup_account_impl, {"phone_or_account": "2025550186"}, {}),
        ("send_login_code", send_login_code_impl, {}, {"auth_status": "none"}),
        ("check_login_code", check_login_code_impl, {"code": "271846"}, {"auth_status": "code_sent"}),
        ("check_secret_pin", check_secret_pin_impl, {"pin": "5903"}, {"auth_status": "none"}),
        ("submit_request", submit_request_impl, {"summary": "Need statement copy"}, {}),
        ("handover_to_person", handover_to_person_impl, {"reason": "support"}, {}),
    ]

    for name, fn, kwargs, extra_state in test_calls:
        state = {**base_state, **extra_state, "language": locale}
        reply = fn(**kwargs, state=state, language=locale)
        assert reply["status"] == "ok", f"{name} failed with {reply}"
        assert "spoken_summary" in reply or "spoken_message" in reply, f"{name} missing spoken_summary: {reply}"
        summary = reply.get("spoken_summary") or reply.get("spoken_message")
        assert isinstance(summary, str) and len(summary) > 0

        action = reply.get("agent_action")
        if action:
            assert len(action) <= 120, f"{name} agent_action > 120 chars: {action}"

        sibling_keys = _check_no_sibling_keys(reply)
        assert not sibling_keys, f"{name} reply has localized sibling keys: {sibling_keys}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_error_replies_contract(locale: str) -> None:
    state: dict[str, Any] = {"language": locale}
    err_reply = lookup_account_impl(phone_or_account="000", state=state, language=locale)
    assert err_reply["status"] == "error"
    action = err_reply.get("agent_action")
    if action:
        assert len(action) <= 120, f"agent_action > 120 chars: {action}"
    assert not _check_no_sibling_keys(err_reply)


def test_french_error_replies_localized() -> None:
    state: dict[str, Any] = {"language": "fr-CA"}
    # NOT_FOUND
    res_nf = lookup_account_impl(phone_or_account="000", state=state, language="fr-CA")
    assert res_nf["status"] == "error"
    assert "compte" in res_nf["error_message"].lower() or "numéro" in res_nf["error_message"].lower()
    assert "demander" in res_nf["agent_action"].lower()

    # INVALID_INPUT
    res_ii = lookup_account_impl(phone_or_account="", state=state, language="fr-CA")
    assert res_ii["status"] == "error"
    assert "numéro" in res_ii["error_message"].lower()

