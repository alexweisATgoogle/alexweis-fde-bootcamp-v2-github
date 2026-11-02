"""Unit tests for scripts/triage_failures.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import triage_failures


def test_triage_failures_self_test():
    """Verify that triage_failures self-test passes cleanly."""
    assert triage_failures.self_test() == 0


def test_triage_failures_classification(tmp_path: Path):
    """Test detailed bucketing for code, defect, and offscript."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    defects_file = tmp_path / "defects.md"

    defects_file.write_text(
        "### DEF-09: Router transfer failure on refund\n"
        "- **Found by**: `VE-15`, `sim__refund_flow`\n"
        "- **Label**: `platform`\n",
        encoding="utf-8",
    )

    data = {
        "results": [
            {
                "displayName": "sim__normal_code_fail",
                "slot": 1,
                "evaluation_status": "FAIL",
                "scenario_result": {
                    "evaluation_expectation_results": [
                        {
                            "prompt": "Offer assistance",
                            "outcome": "FAIL",
                            "score": 0.0,
                            "explanation": "Agent failed to greet customer properly.",
                        }
                    ]
                },
            },
            {
                "displayName": "sim__refund_flow",
                "slot": 2,
                "evaluation_status": "FAIL",
                "scenario_result": {
                    "evaluation_expectation_results": [
                        {
                            "prompt": "Transfer to finance",
                            "outcome": "FAIL",
                            "score": 0.0,
                            "explanation": "Transfer routing not completed.",
                        }
                    ]
                },
            },
            {
                "displayName": "sim__user_spoke_turn",
                "slot": 1,
                "evaluation_status": "FAIL",
                "scenario_result": {
                    "evaluation_expectation_results": [
                        {
                            "prompt": "Customer response",
                            "outcome": "FAIL",
                            "score": 0.0,
                            "explanation": "In this turn, the simulator spoke the agent's turn unexpectedly.",
                        }
                    ]
                },
            },
            {
                "displayName": "sim__metric_not_valid",
                "slot": 1,
                "evaluation_status": "OUTCOME_UNSPECIFIED",
                "scenario_result": {
                    "evaluation_expectation_results": [
                        {
                            "prompt": "Evaluate hallucination",
                            "outcome": "OUTCOME_UNSPECIFIED",
                            "score": -1.0,
                            "explanation": "Metric not valid: OUTCOME_UNSPECIFIED due to audio cutoff.",
                        }
                    ]
                },
            },
        ]
    }

    (raw_dir / "results.json").write_text(json.dumps(data), encoding="utf-8")

    rows = triage_failures.triage_run(raw_dir, defects_file)
    assert len(rows) == 4

    by_eval = {r["eval"]: r for r in rows}
    assert by_eval["sim__normal_code_fail"]["bucket"] == "code"
    assert by_eval["sim__refund_flow"]["bucket"] == "defect:DEF-09"
    assert by_eval["sim__user_spoke_turn"]["bucket"] == "offscript"
    assert by_eval["sim__metric_not_valid"]["bucket"] == "offscript"

    table = triage_failures.render_markdown_table(rows)
    assert "| sim__normal_code_fail | 1 |" in table
    assert "`defect:DEF-09`" in table
    assert "`code`" in table
    assert "`offscript`" in table


def test_triage_empty_run(tmp_path: Path):
    """Empty run produces table headers only."""
    raw_dir = tmp_path / "empty"
    raw_dir.mkdir()
    (raw_dir / "empty.json").write_text(json.dumps({"results": []}), encoding="utf-8")

    rows = triage_failures.triage_run(raw_dir)
    assert len(rows) == 0
    table = triage_failures.render_markdown_table(rows)
    assert "| Eval | Slot | Failing Metric/Expectation | Judge Explanation | Bucket |" in table
