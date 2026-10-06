"""Home page data: the terminal demo cases, the incident table and the cost arithmetic."""

from pathlib import Path

import yaml

from .catalog import EVALS
from .model import DemoCase, Incident, Policy
from .pageparts import PageError


def _blocking_case(catalog: Path, policy: Policy, case_id: str) -> DemoCase:
    """The named eval case of `policy`; it must exist and expect a block."""
    suite_file = catalog / policy.path / EVALS
    if not suite_file.is_file():
        raise PageError(f"demo: {policy.id} has no eval suite")
    suite = yaml.safe_load(suite_file.read_text(encoding="utf-8")) or {}
    cases = (suite.get("suite") or {}).get("cases") or []
    case = next((c for c in cases if str(c.get("id")) == case_id), None)
    if case is None:
        raise PageError(f"demo: {policy.id} has no eval case {case_id}")
    execute = case.get("execute") or {}
    if execute.get("expect") != "block":
        raise PageError(f"demo: {policy.id} {case_id} does not expect a block")
    command = execute.get("command")
    files = {str(k): str(v) for k, v in (execute.get("files") or {}).items()}
    if not command and not files:
        raise PageError(f"demo: {policy.id} {case_id} has no input to show")
    return DemoCase(
        policy=policy.id,
        case=case_id,
        command=str(command) if command else None,
        files=files,
    )


def load_demo(catalog: Path, data_dir: Path, policies: list[Policy]) -> list[DemoCase]:
    """data/demo.yaml resolved against the catalog; a missing or non-block case fails."""
    raw = yaml.safe_load((data_dir / "demo.yaml").read_text(encoding="utf-8")) or {}
    by_id = {p.id: p for p in policies}
    cases = []
    for entry in raw.get("demo") or []:
        policy = by_id.get(entry["policy"])
        if policy is None:
            raise PageError(f"demo: {entry['policy']} is not a visible policy")
        cases.append(_blocking_case(catalog, policy, str(entry["case"])))
    if not cases:
        raise PageError("demo.yaml lists no cases")
    return cases


def load_incidents(
    data_dir: Path, policies: list[Policy]
) -> tuple[dict, list[Incident]]:
    """data/incidents.yaml: its copy and rows; a policy id that is not visible fails."""
    raw = yaml.safe_load((data_dir / "incidents.yaml").read_text(encoding="utf-8"))
    visible = {p.id for p in policies}
    rows = []
    for row in raw["rows"]:
        unknown = [pid for pid in row["policies"] if pid not in visible]
        if unknown or not row["policies"]:
            raise PageError(
                f"incidents.yaml: {row['incident']}: not visible policies {unknown}"
            )
        rows.append(
            Incident(
                incident=row["incident"],
                flaw=row["flaw"],
                policies=list(row["policies"]),
            )
        )
    return raw, rows


def savings(
    findings: float, share: float, minutes: float, rate: float, days: float
) -> tuple[float, float, float]:
    """Hours, money and days saved per release; `share` is a percentage (0-100)."""
    covered = findings * share / 100
    hours = covered * minutes / 60
    return hours, hours * rate, days * share / 100


def fmt_hours(value: float) -> str:
    """One decimal at most, thousands separated, no trailing .0 (matches cost.js)."""
    text = f"{value:,.1f}"
    return text.removesuffix(".0")


def fmt_money(value: float) -> str:
    """Whole dollars rounded half up, thousands separated (matches cost.js)."""
    return f"{int(value + 0.5):,}"
