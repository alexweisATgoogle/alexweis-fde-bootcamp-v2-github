"""Unit tests for suite/overfit_check.py (NUMBER_IN_PROMPT and EVAL_VALUE_IN_FAKES)."""

from __future__ import annotations

import json
from pathlib import Path

from suite.overfit_check import check_app, main


def _make_workspace(tmp_path: Path, prd_text: str = "# PRD\nRefunds up to $50 are allowed within 30 days.\n") -> tuple[Path, Path, Path]:
    prd = tmp_path / "prd.md"
    prd.write_text(prd_text, encoding="utf-8")
    app_dir = tmp_path / "cxas_app"
    (app_dir / "agents" / "router").mkdir(parents=True, exist_ok=True)
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / "fakes.py").write_text(
        "ACCOUNTS = {\n"
        '    "ACC-1001": {"account_id": "ACC-1001", "phone": "2025550143", "first_name": "Jordan"},\n'
        "}\n"
        'VALID_PINS = frozenset({"5903", "5678"})\n'
        'VALID_OTPS = frozenset({"271846"})\n'
        'ALWAYS_WRONG_LOGIN_CODES = frozenset({"8888", "9999"})\n',
        encoding="utf-8",
    )
    return app_dir, lib_dir, prd


def test_structural_numbers_and_prd_numbers_allowed_in_prompt(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<taskflow>\n"
        '  <subtask name="M1 Verify">\n'
        '    <step name="Step 1">\n'
        "      <trigger>Caller speaks en-US, fr-CA, or es-419</trigger>\n"
        "      <action>\n"
        "        1. Ask for the 6-digit 2FA code or 4-digit PIN.\n"
        "        2. Confirm the last 4 digits ({phone_last4}) of the 10-digit phone number.\n"
        "        3. Refunds up to $50 within 30 days are auto-approved (24/7 support at 1-800-555-0100).\n"
        "      </action>\n"
        "    </step>\n"
        "  </subtask>\n"
        "</taskflow>\n",
        encoding="utf-8",
    )

    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    num_findings = [f for f in result["findings"] if f["code"] == "NUMBER_IN_PROMPT"]
    assert num_findings == [], f"Unexpected NUMBER_IN_PROMPT findings: {num_findings}"
    assert result["ok"]


def test_unallowed_number_in_prompt_triggers_error(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"quote\">\n"
        "  <trigger>Caller asks about speed</trigger>\n"
        "  <action>Tell the caller their download speed is 450 Mbps with a 75 GB cap.</action>\n"
        "</step>\n",
        encoding="utf-8",
    )

    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    codes = {f["code"] for f in result["findings"]}
    assert "NUMBER_IN_PROMPT" in codes
    messages = " ".join(f["message"] for f in result["findings"] if f["code"] == "NUMBER_IN_PROMPT")
    assert "450" in messages
    assert "75" in messages


def test_eval_value_in_fakes_flags_bloated_credential_set(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    # 9 entries (> 8 max) in VALID_PINS
    (lib_dir / "fakes.py").write_text(
        'VALID_PINS = frozenset({"1234", "5678", "1111", "0000", "9999", "123456", "654321", "482913", "2468"})\n',
        encoding="utf-8",
    )

    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    fakes_findings = [f for f in result["findings"] if f["code"] == "EVAL_VALUE_IN_FAKES"]
    assert fakes_findings, f"Expected EVAL_VALUE_IN_FAKES in {result['findings']}"


def test_eval_value_in_fakes_flags_eval_literal_not_in_prd(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    evals_dir = tmp_path / "bench" / "dev" / "evaluations" / "sim_special"
    evals_dir.mkdir(parents=True)
    (evals_dir / "sim_special.json").write_text(
        json.dumps(
            {
                "displayName": "sim_special",
                "scenario": {
                    "task": "Caller provides PIN 7391 and account ACC-7788.",
                    "userFacts": ["Customer: Evelyn Vance"],
                },
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "fakes.py").write_text(
        "ACCOUNTS = {\n"
        '    "ACC-7788": {"account_id": "ACC-7788", "phone": "2025550143", "first_name": "Evelyn Vance"},\n'
        "}\n"
        'VALID_PINS = frozenset({"1234", "7391"})\n',
        encoding="utf-8",
    )

    result = check_app(
        app_dir=app_dir,
        lib_dir=lib_dir,
        prd_path=prd,
        eval_dirs=[tmp_path / "bench" / "dev"],
    )
    assert not result["ok"]
    fakes_msgs = " ".join(
        f["message"] for f in result["findings"] if f["code"] == "EVAL_VALUE_IN_FAKES"
    )
    assert "7391" in fakes_msgs
    assert "ACC-7788" in fakes_msgs


def test_canonical_value_in_fakes_fails_on_4242_and_passes_on_7742(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    # Fixture file containing 4242 must fail CANONICAL_VALUE_IN_FAKES
    fixture_file = lib_dir / "fakes.py"
    fixture_file.write_text(
        'SAMPLE_CARD = "4242"\n'
        'VALID_PINS = frozenset({"5903"})\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    canonical_findings = [f for f in result["findings"] if f["code"] == "CANONICAL_VALUE_IN_FAKES"]
    assert canonical_findings, f"Expected CANONICAL_VALUE_IN_FAKES finding: {result['findings']}"
    assert any("4242" in f["message"] and "lib/fakes.py" in f["file"] for f in canonical_findings)
    assert any("lib/fakes.py:1:4242" in f["detail"] for f in canonical_findings)

    # Replacing 4242 with 7742 must pass
    fixture_file.write_text(
        'SAMPLE_CARD = "7742"\n'
        'VALID_PINS = frozenset({"5903"})\n',
        encoding="utf-8",
    )
    result2 = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    canonical_findings2 = [f for f in result2["findings"] if f["code"] == "CANONICAL_VALUE_IN_FAKES"]
    assert canonical_findings2 == []
    assert result2["ok"]


def test_canonical_value_in_fakes_waivable_via_prd(tmp_path: Path) -> None:
    # 4242 mentioned legitimately in PRD is waived
    app_dir, lib_dir, prd = _make_workspace(
        tmp_path,
        prd_text="# PRD\nUse test card 4242 for verification.\n",
    )
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    (lib_dir / "fakes.py").write_text(
        'SAMPLE_CARD = "4242"\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    canonical_findings = [f for f in result["findings"] if f["code"] == "CANONICAL_VALUE_IN_FAKES"]
    assert canonical_findings == []
    assert result["ok"]


def test_canonical_value_in_fixture_json_file(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    # JSON fixture with 4242 fails
    json_fixture = lib_dir / "card_fake_config.json"
    json_fixture.write_text(json.dumps({"card": "4242"}), encoding="utf-8")
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    canonical_findings = [f for f in result["findings"] if f["code"] == "CANONICAL_VALUE_IN_FAKES"]
    assert len(canonical_findings) == 1
    assert "4242" in canonical_findings[0]["message"]

    # Changing to 7742 passes
    json_fixture.write_text(json.dumps({"card": "7742"}), encoding="utf-8")
    result2 = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    canonical_findings2 = [f for f in result2["findings"] if f["code"] == "CANONICAL_VALUE_IN_FAKES"]
    assert canonical_findings2 == []


def test_literal_date_in_fakes_fails_with_hint(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    (lib_dir / "fakes.py").write_text(
        'SCHEDULED_DATE = "2026-10-30"\n'
        'VALID_PINS = frozenset({"5903"})\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    date_findings = [f for f in result["findings"] if f["code"] == "LITERAL_DATE_IN_FAKES"]
    assert date_findings, f"Expected LITERAL_DATE_IN_FAKES in {result['findings']}"
    assert "use relative_date(days)" in date_findings[0]["message"]
    assert "2026-10-30" in date_findings[0]["message"]


def test_literal_date_in_fakes_passes_with_relative_date_and_ignores_comments(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    (lib_dir / "fakes.py").write_text(
        '# Example date comment: 2026-10-30 is ignored by AST\n'
        'SCHEDULED_DATE = relative_date(3)\n'
        'VALID_PINS = frozenset({"5903"})\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    date_findings = [f for f in result["findings"] if f["code"] == "LITERAL_DATE_IN_FAKES"]
    assert date_findings == []
    assert result["ok"]


def test_localized_sibling_key_fails_on_reply_dict_with_lang_suffix(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    (lib_dir / "services.py").write_text(
        'def get_account_reply():\n'
        '    return {\n'
        '        "status": "ok",\n'
        '        "summary_en": "Your balance is zero.",\n'
        '        "summary_fr": "Votre solde est de zero.",\n'
        '    }\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    sibling_findings = [f for f in result["findings"] if f["code"] == "LOCALIZED_SIBLING_KEY"]
    assert len(sibling_findings) == 2
    keys = {f["value"] for f in sibling_findings}
    assert keys == {"summary_en", "summary_fr"}


def test_localized_sibling_key_passes_on_resolved_key_and_ignores_comments(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    (lib_dir / "services.py").write_text(
        '# Example comment: do NOT use summary_en or summary_fr here\n'
        'def get_account_reply():\n'
        '    return {\n'
        '        "status": "ok",\n'
        '        "spoken_summary": "Your balance is zero.",\n'
        '    }\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    sibling_findings = [f for f in result["findings"] if f["code"] == "LOCALIZED_SIBLING_KEY"]
    assert sibling_findings == []
    assert result["ok"]


def test_agent_action_too_long_fails_when_exceeding_120_chars(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    long_action = "x" * 121
    (lib_dir / "services.py").write_text(
        f'agent_action = "{long_action}"\n'
        'def get_error_reply():\n'
        f'    return {{"status": "error", "agent_action": "{long_action}"}}\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    assert not result["ok"]
    action_findings = [f for f in result["findings"] if f["code"] == "AGENT_ACTION_TOO_LONG"]
    assert len(action_findings) == 2
    assert all("> 120 max" in f["message"] for f in action_findings)


def test_agent_action_length_passes_at_or_below_120_and_ignores_comments(tmp_path: Path) -> None:
    app_dir, lib_dir, prd = _make_workspace(tmp_path)
    (app_dir / "agents" / "router" / "instruction.txt").write_text(
        "<step name=\"greet\"><trigger>Start</trigger><action>Say hello.</action></step>\n",
        encoding="utf-8",
    )
    comment_action = "c" * 150
    ok_action = "a" * 120
    (lib_dir / "services.py").write_text(
        f'# agent_action: {comment_action}\n'
        f'agent_action = "{ok_action}"\n'
        'def get_error_reply():\n'
        f'    return {{"status": "error", "agent_action": "Explain the error."}}\n',
        encoding="utf-8",
    )
    result = check_app(app_dir=app_dir, lib_dir=lib_dir, prd_path=prd)
    action_findings = [f for f in result["findings"] if f["code"] == "AGENT_ACTION_TOO_LONG"]
    assert action_findings == []
    assert result["ok"]


def test_overfit_check_self_test() -> None:
    assert main(["--self-test"]) == 0
