from pathlib import Path
import re

from lib.fakes import ACCOUNTS

APP_DIR = Path(__file__).resolve().parent.parent / "cxas_app"
FORBIDDEN_NAMES = (
    *(acc.get("first_name", "") for acc in ACCOUNTS if acc.get("first_name")),
    "Jordan",
    "Alex",
    "Marie",
    "Carlos",
    "Smith",
    "Rivera",
)
FORBIDDEN_IDS = (
    *(acc.get("account_id", "") for acc in ACCOUNTS if acc.get("account_id")),
    "A1001",
    "A1002",
    "ACC-1001",
    "ACC-1002",
)
_ALLOWED_PROMPT_PATTERNS = (
    re.compile(r"<[^>]+>"),
    re.compile(r"\{[^}]+\}"),
    re.compile(r"\b\d+-digit\b", re.IGNORECASE),
    re.compile(r"\b(?:\w+_)?last[ -]?4(?:\s+digits)?\b", re.IGNORECASE),
    re.compile(r"\b2FA\b", re.IGNORECASE),
    re.compile(r"\b[a-z]{2}-[A-Z]{2}(?:-[A-Za-z0-9]+)?\b"),
    re.compile(r"\b[a-z]{2}-419\b", re.IGNORECASE),
    re.compile(r"\bstep[_\s-]*\d+\b", re.IGNORECASE),
    re.compile(r"\bM\d+\b"),
    re.compile(r"\b1-800-[0-9-]+\b"),
    re.compile(r"\b24/7\b"),
    re.compile(r"\b24\b"),
    re.compile(r"\b[1-4]\b"),
    re.compile(r"(?m)^\s*\d+\.\s"),
)


def _strip_allowed(text: str, prd_digits: set[str] | None = None) -> str:
    cleaned = text
    for pat in _ALLOWED_PROMPT_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    for num in prd_digits or ():
        cleaned = re.sub(rf"\b{re.escape(str(num))}\b", " ", cleaned)
    return cleaned


def test_prompts_contain_no_literals_or_defect_ids() -> None:
    prompt_files = [
        APP_DIR / "global_instruction.txt",
        *sorted((APP_DIR / "agents").rglob("instruction.txt")),
    ]
    assert len(prompt_files) >= 3
    for path in prompt_files:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b\d{4,}\b", text), f"{path} contains a 4+ digit number"
        assert not re.findall(r"\b\d+\b", _strip_allowed(text)), f"{path} contains unallowed digits"
        assert not re.search(r"\b(?:DEF|VE|HE|BUG)-\d+\b", text), f"{path} contains a tracker ID"
        for name in FORBIDDEN_NAMES:
            assert not re.search(rf"\b{re.escape(name)}\b", text), f"{path} contains fake name {name}"
        for acc_id in FORBIDDEN_IDS:
            assert acc_id not in text, f"{path} contains fake account ID {acc_id}"


def test_router_and_specialist_subtask_structure_and_handover_pairing() -> None:
    router_txt = (APP_DIR / "agents" / "router" / "instruction.txt").read_text(encoding="utf-8")
    specialist_txt = (APP_DIR / "agents" / "specialist" / "instruction.txt").read_text(encoding="utf-8")
    global_txt = (APP_DIR / "global_instruction.txt").read_text(encoding="utf-8")

    router_subtasks = re.findall(r'<subtask name="([^"]+)">', router_txt)
    assert router_subtasks and all(name.startswith("M1 ") for name in router_subtasks)
    assert "first_name" not in router_txt

    specialist_subtasks = re.findall(r'<subtask name="([^"]+)">', specialist_txt)
    assert specialist_subtasks and all(name.startswith("M2 ") for name in specialist_subtasks)
    assert 'step name="Caller Offers Code First"' in specialist_txt
    assert 'step name="Code Not Received"' in specialist_txt
    assert "{@TOOL: check_secret_pin}" in specialist_txt

    for txt in (global_txt, router_txt, specialist_txt):
        assert "{@TOOL: handover_to_person}" in txt
        assert "{@TOOL: end_session}" in txt
        assert "handoff_message" in txt
