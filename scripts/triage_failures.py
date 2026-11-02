#!/usr/bin/env python3
"""Failure Triage CLI for GECX / CXAS evaluations.

Triages non-passing evaluation slots into actionable root-cause buckets:
  - `defect:<DEF-id>`: Matches an entry in docs/defects.md by eval name or label.
  - `offscript`: Simulator or platform judge breakdown:
      * Simulator spoke the agent's turn
      * Simulator invented facts absent from the persona
      * Judge score -1.0 ("metric not valid")
      * Status or outcome is OUTCOME_UNSPECIFIED
  - `code`: Everything else (deterministic agent logic, routing, tool call, prompt defect).

Usage:
  python3 scripts/triage_failures.py <run_dir_or_json> [--defects docs/defects.md]
  python3 scripts/triage_failures.py --run <run_dir_or_json> [--defects docs/defects.md]
  python3 scripts/triage_failures.py --self-test
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

OFFSCRIPT_PHRASES = (
    "simulator spoke",
    "spoke the agent's turn",
    "user spoke as the agent",
    "user spoke as agent",
    "spoke as agent",
    "invented facts absent from the persona",
    "facts absent from the persona",
    "absent from the persona",
    "invented facts",
    "metric not valid",
    "metric is not valid",
)


def parse_defects(path: Path | str | None) -> list[dict[str, Any]]:
    """Parse defects from a markdown file (DEF-xx headings, Found by, Label)."""
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        return []

    defects: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(DEF-\w+):\s*(.*)$", line)
        if m:
            current = {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "found_by": set(),
                "labels": set(),
            }
            defects.append(current)
            continue
        if current is None:
            continue
        if re.match(r"^-\s*\*\*(?:Found by|Found By)\*\*:", line) or line.startswith("- Found by:"):
            val = line.split(":", 1)[1]
            found = re.findall(r"`([^`]+)`", val) or re.findall(r"[A-Za-z0-9_-]+", val)
            current["found_by"].update(f.strip() for f in found if f.strip())
        elif re.match(r"^-\s*\*\*(?:Label)\*\*:", line) or line.startswith("- Label:"):
            val = line.split(":", 1)[1]
            labels = re.findall(r"[A-Za-z0-9_-]+", val.lower())
            current["labels"].update(l.strip() for l in labels if l.strip())

    return defects


def normalize_eval_id(raw_id: str) -> str:
    """Normalize eval ID by stripping path segments, sim__/golden__ prefixes, and extensions."""
    s = raw_id.strip()
    s = s.rsplit("/", 1)[-1]
    s = re.sub(r"\.(?:json|yaml|yml)$", "", s)
    s = re.sub(r"^(?:sim__|golden__)", "", s)
    return s


def matches_defect(eval_identifier: str, defects: list[dict[str, Any]]) -> str | None:
    """Return DEF-id if eval matches a defect entry, else None."""
    norm = normalize_eval_id(eval_identifier)
    for d in defects:
        for fb in d["found_by"]:
            if normalize_eval_id(fb) == norm or fb in eval_identifier or eval_identifier in fb:
                return d["id"]
        if norm in normalize_eval_id(d["title"]):
            return d["id"]
    return None


def is_offscript(explanation: str, outcome: str, score: float | None) -> bool:
    """Heuristic check for simulator or judge breakdown."""
    if outcome in ("OUTCOME_UNSPECIFIED", "0", 0):
        return True
    if score is not None and score == -1.0:
        return True
    text = (explanation or "").lower()
    return any(phrase in text for phrase in OFFSCRIPT_PHRASES)


def classify_failing_slot(
    eval_id: str,
    explanation: str,
    outcome: str,
    score: float | None,
    defects: list[dict[str, Any]],
) -> str:
    """Classify a failing slot into 'defect:<id>', 'offscript', or 'code'."""
    def_id = matches_defect(eval_id, defects)
    if def_id:
        return f"defect:{def_id}"
    if is_offscript(explanation, outcome, score):
        return "offscript"
    return "code"


def extract_failing_slots_from_result(
    res: dict[str, Any],
    slot_num: int,
    defects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract rows for any failing metrics/expectations in an evaluation result."""
    eval_name = str(
        res.get("display_name")
        or res.get("displayName")
        or res.get("ve_id")
        or res.get("evaluation")
        or "unknown_eval"
    )
    eval_short = eval_name.rsplit("/", 1)[-1]

    status = str(res.get("evaluation_status") or res.get("classification") or res.get("status") or "")
    scenario = res.get("scenario_result") or res.get("raw", {}).get("scenario_result") or {}

    rows: list[dict[str, Any]] = []

    # Check expectation results
    exp_results = scenario.get("evaluation_expectation_results") or []
    for exp in exp_results:
        exp_outcome = str(exp.get("outcome") or "")
        exp_score = exp.get("score")
        if exp_score is not None:
            try:
                exp_score = float(exp_score)
            except (ValueError, TypeError):
                exp_score = None

        is_fail = (
            exp_outcome in ("FAIL", "2", "OUTCOME_UNSPECIFIED", "0")
            or (exp_score is not None and exp_score <= 0.0)
        )
        if is_fail:
            metric = f"expectation: {exp.get('prompt') or 'unnamed_expectation'}"
            expl = str(exp.get("explanation") or "")
            bucket = classify_failing_slot(eval_short, expl, exp_outcome, exp_score, defects)
            rows.append({
                "eval": eval_short,
                "slot": slot_num,
                "metric": metric,
                "explanation": expl,
                "bucket": bucket,
            })

    # Check user goal
    goal = scenario.get("user_goal_satisfaction_result")
    if isinstance(goal, dict):
        g_score = goal.get("score")
        try:
            g_score = float(g_score) if g_score is not None else None
        except (ValueError, TypeError):
            g_score = None
        if g_score is not None and g_score <= 0.0:
            expl = str(goal.get("explanation") or "")
            bucket = classify_failing_slot(eval_short, expl, "FAIL", g_score, defects)
            rows.append({
                "eval": eval_short,
                "slot": slot_num,
                "metric": "user_goal",
                "explanation": expl,
                "bucket": bucket,
            })

    # Check hallucination
    halluc = scenario.get("hallucination_result")
    h_list = halluc if isinstance(halluc, list) else ([halluc] if isinstance(halluc, dict) else [])
    for h in h_list:
        if isinstance(h, dict):
            h_score = h.get("score")
            try:
                h_score = float(h_score) if h_score is not None else None
            except (ValueError, TypeError):
                h_score = None
            if h_score is not None and h_score <= 0.0:
                expl = str(h.get("explanation") or "")
                bucket = classify_failing_slot(eval_short, expl, "FAIL", h_score, defects)
                rows.append({
                    "eval": eval_short,
                    "slot": slot_num,
                    "metric": "hallucination",
                    "explanation": expl,
                    "bucket": bucket,
                })
                break

    # If no sub-metric failure rows were generated but the overall result failed
    if not rows and (status.upper() in ("FAIL", "2", "OUTCOME_UNSPECIFIED", "0") or res.get("passed") is False):
        expl = str(res.get("classification_reason") or res.get("error") or res.get("missing") or status)
        bucket = classify_failing_slot(eval_short, expl, status, None, defects)
        rows.append({
            "eval": eval_short,
            "slot": slot_num,
            "metric": "overall_status",
            "explanation": expl,
            "bucket": bucket,
        })

    return rows


def load_raw_run(target_path: Path | str) -> list[tuple[dict[str, Any], int]]:
    """Load results paired with their slot number from a raw directory or JSON file."""
    p = Path(target_path)
    if not p.exists():
        raise FileNotFoundError(f"Run path does not exist: {p}")

    files: list[Path] = []
    if p.is_dir():
        files = sorted(p.glob("*.json"))
    elif p.is_file():
        files = [p]

    results_with_slots: list[tuple[dict[str, Any], int]] = []
    eval_slot_counter: dict[str, int] = defaultdict(int)

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue

        raw_list = []
        if isinstance(data, dict):
            if "results" in data and isinstance(data["results"], list):
                raw_list = data["results"]
            elif "records" in data and isinstance(data["records"], list):
                raw_list = data["records"]
            else:
                raw_list = [data]
        elif isinstance(data, list):
            raw_list = data

        for item in raw_list:
            if not isinstance(item, dict):
                continue
            e_name = str(
                item.get("display_name")
                or item.get("displayName")
                or item.get("ve_id")
                or item.get("evaluation")
                or "unknown"
            )
            slot = item.get("slot")
            if slot is None:
                eval_slot_counter[e_name] += 1
                slot = eval_slot_counter[e_name]
            else:
                try:
                    slot = int(slot)
                except (ValueError, TypeError):
                    eval_slot_counter[e_name] += 1
                    slot = eval_slot_counter[e_name]
            results_with_slots.append((item, slot))

    return results_with_slots


def triage_run(
    target_path: Path | str,
    defects_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Triage all failing slots in a run and return row dictionaries."""
    defects = parse_defects(defects_path)
    records = load_raw_run(target_path)

    all_rows: list[dict[str, Any]] = []
    for res, slot_num in records:
        failing_rows = extract_failing_slots_from_result(res, slot_num, defects)
        all_rows.extend(failing_rows)

    return all_rows


def render_markdown_table(rows: list[dict[str, Any]]) -> str:
    """Render rows into a formatted markdown table."""
    headers = ["Eval", "Slot", "Failing Metric/Expectation", "Judge Explanation", "Bucket"]
    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join(['---'] * len(headers))} |",
    ]

    if not rows:
        return "\n".join(lines) + "\n"

    for r in rows:
        eval_id = str(r.get("eval", "")).replace("|", "\\|")
        slot = str(r.get("slot", ""))
        metric = str(r.get("metric", "")).replace("|", "\\|").replace("\n", " ")
        expl = str(r.get("explanation", ""))[:200].replace("|", "\\|").replace("\n", " ").strip()
        bucket = str(r.get("bucket", ""))
        lines.append(f"| {eval_id} | {slot} | {metric} | {expl} | `{bucket}` |")

    return "\n".join(lines) + "\n"


def self_test() -> int:
    """Self-test building synthetic run and checking code, defect, offscript buckets."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        raw_dir = tmp_dir / "test_raw"
        raw_dir.mkdir()
        defects_file = tmp_dir / "defects.md"

        defects_file.write_text(
            "### DEF-01: Known simulator issue on ticket status\n"
            "- **Found by**: `VE-02`, `sim__ticket_status`\n"
            "- **Label**: `simulator`\n",
            encoding="utf-8",
        )

        sample_run = {
            "results": [
                # 1. Code failure: tool not called
                {
                    "displayName": "sim__pay_bill",
                    "slot": 1,
                    "evaluation_status": "FAIL",
                    "scenario_result": {
                        "evaluation_expectation_results": [
                            {
                                "prompt": "Agent processes card payment",
                                "outcome": "FAIL",
                                "score": 0.0,
                                "explanation": "Agent failed to call pay_bill tool before ending call.",
                            }
                        ]
                    },
                },
                # 2. Defect failure: matches DEF-01
                {
                    "displayName": "sim__ticket_status",
                    "slot": 1,
                    "evaluation_status": "FAIL",
                    "scenario_result": {
                        "evaluation_expectation_results": [
                            {
                                "prompt": "Check status of open ticket",
                                "outcome": "FAIL",
                                "score": 0.0,
                                "explanation": "Ticket details were not provided to caller.",
                            }
                        ]
                    },
                },
                # 3. Off-script failure: simulator spoke the agent's turn & OUTCOME_UNSPECIFIED
                {
                    "displayName": "sim__reset_password",
                    "slot": 1,
                    "evaluation_status": "OUTCOME_UNSPECIFIED",
                    "scenario_result": {
                        "evaluation_expectation_results": [
                            {
                                "prompt": "Reset customer credentials",
                                "outcome": "OUTCOME_UNSPECIFIED",
                                "score": -1.0,
                                "explanation": "Metric not valid: simulator spoke the agent's turn and invented facts absent from the persona.",
                            }
                        ]
                    },
                },
            ]
        }

        (raw_dir / "run_01.json").write_text(json.dumps(sample_run), encoding="utf-8")

        rows = triage_run(raw_dir, defects_file)
        assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}: {rows}"

        buckets = {r["eval"]: r["bucket"] for r in rows}
        assert buckets.get("sim__pay_bill") == "code", f"Expected code, got {buckets.get('sim__pay_bill')}"
        assert buckets.get("sim__ticket_status") == "defect:DEF-01", f"Expected defect:DEF-01, got {buckets.get('sim__ticket_status')}"
        assert buckets.get("sim__reset_password") == "offscript", f"Expected offscript, got {buckets.get('sim__reset_password')}"

        table = render_markdown_table(rows)
        assert "| Eval | Slot | Failing Metric/Expectation | Judge Explanation | Bucket |" in table
        assert "`code`" in table
        assert "`defect:DEF-01`" in table
        assert "`offscript`" in table

    print("OK (triage_failures self-test)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_pos", nargs="?", help="Path to raw run directory or run JSON file")
    parser.add_argument("--run", dest="run_flag", help="Path to raw run directory or run JSON file")
    parser.add_argument("--defects", help="Path to defects.md (default: docs/defects.md if exists)")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-tests and exit")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    run_path = args.run_pos or args.run_flag
    if not run_path:
        parser.error("A run directory or JSON file is required (pass as positional arg or with --run)")

    defects_path = args.defects
    if not defects_path:
        default_defects = REPO_ROOT / "docs" / "defects.md"
        if default_defects.is_file():
            defects_path = str(default_defects)

    rows = triage_run(run_path, defects_path)
    print(render_markdown_table(rows), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
