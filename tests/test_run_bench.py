"""Unit tests for scripts/run_bench.py: the daily full-run cap comes from gate_thresholds.json."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from scripts import run_bench

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = "projects/test-proj/locations/us/apps/a1"


def _thresholds(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "gate_thresholds.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _full_runs_today(runs_dir: Path, count: int) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y%m%d")
    for n in range(count):
        (runs_dir / f"run_{today}T00000{n}Z.json").write_text(json.dumps({"is_full_run": True}), encoding="utf-8")


def test_cap_comes_from_the_thresholds_file_when_no_flag_is_given(tmp_path: Path) -> None:
    thresholds = _thresholds(tmp_path, {"promotion": {"daily_full_run_cap": 6}})
    assert run_bench.resolve_max_full_runs(None, thresholds) == 6


def test_explicit_flag_wins_over_the_thresholds_file(tmp_path: Path) -> None:
    thresholds = _thresholds(tmp_path, {"promotion": {"daily_full_run_cap": 6}})
    assert run_bench.resolve_max_full_runs(3, thresholds) == 3


@pytest.mark.parametrize("payload", [{}, {"promotion": {}}, {"promotion": {"daily_full_run_cap": "many"}}, []])
def test_missing_or_unusable_key_falls_back_to_the_builtin_default(tmp_path: Path, payload: object) -> None:
    assert run_bench.resolve_max_full_runs(None, _thresholds(tmp_path, payload)) == run_bench.DEFAULT_MAX_FULL_RUNS


def test_missing_file_falls_back_to_the_builtin_default(tmp_path: Path) -> None:
    assert run_bench.resolve_max_full_runs(None, tmp_path / "missing.json") == run_bench.DEFAULT_MAX_FULL_RUNS


def test_the_kit_thresholds_file_is_the_default_source() -> None:
    # One source of truth: the cap the kit ships in gate_thresholds.json is what run_bench enforces.
    shipped = json.loads((REPO_ROOT / "gate_thresholds.json").read_text(encoding="utf-8"))
    assert run_bench.resolve_max_full_runs(None) == shipped["promotion"]["daily_full_run_cap"]


def test_env_override_still_wins_in_check_daily_full_run_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir = tmp_path / "runs"
    _full_runs_today(runs_dir, 6)
    cap = run_bench.resolve_max_full_runs(None, _thresholds(tmp_path, {"promotion": {"daily_full_run_cap": 6}}))

    monkeypatch.delenv("MAX_FULL_RUNS", raising=False)
    assert run_bench.check_daily_full_run_cap(runs_dir, max_full_runs=cap) == (False, 6)
    monkeypatch.setenv("MAX_FULL_RUNS", "7")
    assert run_bench.check_daily_full_run_cap(runs_dir, max_full_runs=cap) == (True, 6)


def test_main_refuses_a_full_run_at_the_thresholds_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real wiring: a full run with no --max-full-runs stops at daily_full_run_cap (before
    any cloud call), and an explicit --max-full-runs above the count is honoured instead."""
    bench_dir = tmp_path / "bench"
    _full_runs_today(bench_dir / "runs", 6)
    thresholds = _thresholds(tmp_path, {"promotion": {"daily_full_run_cap": 6}})
    monkeypatch.delenv("MAX_FULL_RUNS", raising=False)

    code = run_bench.main(["--app", APP, "--bench-dir", str(bench_dir), "--thresholds", str(thresholds)])
    assert code == 1
    assert "daily full-run cap reached (6/6" in capsys.readouterr().err

    # 7 > 6 full runs today: the cap no longer stops the run, so main gets past the cap check
    # and reaches the cloud client, which the unit test replaces with a sentinel error.
    def _no_cloud(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("no cloud in unit tests")

    monkeypatch.setattr(run_bench, "_make_cloud", _no_cloud)
    with pytest.raises((RuntimeError, ImportError)):
        run_bench.main([
            "--app", APP, "--bench-dir", str(bench_dir), "--thresholds", str(thresholds), "--max-full-runs", "7",
        ])
