"""Unit tests for scripts/kickstart.py: what a fresh scaffold must (not) contain."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
from types import ModuleType

import pytest
import yaml

from scripts.kickstart import TEST_FILES, kickstart

# Canonical sample values (docs/DESIGN_RULES.md rule 45, CANONICAL_FAKES_BLOCKLIST in
# suite/overfit_check.py): every model and judge has seen them, so a scaffold that uses
# them measures recall instead of the agent. The long values are forbidden anywhere in a
# line; 1234 only as a standalone token, because it is a substring of 12345, of
# +442071234567 and of git short hashes.
FORBIDDEN_SUBSTRINGS = ("123456", "4242", "H3Z 2Y7", "jordan@example.com")
FORBIDDEN_TOKENS = (re.compile(r"(?<!\w)1234(?!\w)"),)


@pytest.fixture(scope="module")
def scaffold(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One untouched kickstart scaffold for the whole module (kickstart + bundle take a second)."""
    target = tmp_path_factory.mktemp("kickstart") / "agent"
    kickstart(
        target_dir=target,
        agent_name="scaffold-check",
        project_id="test-proj",
        location="us",
        languages=["en-US", "fr-CA", "es-US"],
    )
    return target


def _rendered_files(target: Path) -> list[Path]:
    """lib/, cxas_app/, evals/ and the agent tests kickstart renders from its templates.

    Not the kit's own tooling tests that kickstart copies verbatim (tests/test_overfit_check.py
    and friends): a detector's test has to name the values it detects.
    """
    files = [
        path
        for folder in ("lib", "cxas_app", "evals")
        for path in sorted((target / folder).rglob("*"))
        if path.is_file() and path.suffix != ".pyc"
    ]
    files.extend(target / "tests" / name for name in TEST_FILES)
    return files


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_scaffold_has_no_canonical_sample_values(scaffold: Path) -> None:
    hits: list[str] = []
    for path in _rendered_files(scaffold):
        assert path.is_file(), f"kickstart did not write {path}"
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(value in line for value in FORBIDDEN_SUBSTRINGS) or any(
                token.search(line) for token in FORBIDDEN_TOKENS
            ):
                hits.append(f"{path.relative_to(scaffold)}:{lineno}: {line.strip()}")
    assert not hits, "canonical sample values in a fresh scaffold:\n" + "\n".join(hits)


def test_fresh_scaffold_simulation_login_codes_are_accepted_by_the_fakes(scaffold: Path) -> None:
    """The login code a simulation hands the simulated caller must be one lib/fakes.py accepts
    on every attempt, or the sim fails on a retry for a reason unrelated to the agent."""
    fakes = _load_module(scaffold / "lib" / "fakes.py", "_kickstart_check_fakes")
    valid_codes = {str(code) for code in fakes.VALID_OTPS | fakes.VALID_PINS}
    simulations = yaml.safe_load(
        (scaffold / "evals" / "simulations" / "simulations.yaml").read_text(encoding="utf-8")
    )["simulations"]

    login_codes = {
        str(fact["value"])
        for sim in simulations
        for fact in sim.get("user_facts", [])
        if fact.get("name") == "login_code"
    }
    assert login_codes, "the starter simulations should exercise a login code"
    assert login_codes <= valid_codes, f"simulation login codes {login_codes} not all in {valid_codes}"
