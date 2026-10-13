"""Per-agent facts for the docs: S-ALL's agent routes, plus agentseam's events and the engine's claims and ledger."""

from typing import Any

from . import engine
from .pageparts import PageError

PLUGIN, SYNC, NONE = "plugin", "sync", "none"


def agent_slug(agent: str) -> str:
    """The URL slug of an agent page."""
    return agent.replace("_", "-")


def ledger(docs: dict[str, Any]) -> list[dict[str, Any]]:
    """The engine's witness ledger, each row with the route its surface proves."""
    routes = docs["surface_routes"]
    agents = engine.matrix_agents()
    rows = []
    for row in engine.witness_ledger():
        if row["surface"] not in routes:
            raise PageError(
                f"witness ledger surface {row['surface']!r} has no route in docs.yaml"
            )
        if row["agent"] not in agents:
            raise PageError(
                f"witness ledger agent {row['agent']!r} is no agentseam agent"
            )
        rows.append({**row, "route": routes[row["surface"]]})
    return rows


def agents(docs: dict[str, Any], agent_routes: dict[str, Any]) -> list[dict[str, Any]]:
    """One record per agentseam matrix row, in agentseam's order, with everything a docs page shows."""
    stops = set(engine.stop_agents())
    claims = {row["agent"]: row for row in engine.ask_claims()}
    timeouts = engine.hook_timeouts()
    rows = ledger(docs)
    out = []
    for route in agent_routes["agents"]:
        agent = route["agent"]
        matrix = engine.matrix_row(agent)
        tier = engine.tier_row(agent)
        routes = ([PLUGIN] if route["plugin"] else []) + (
            [SYNC] if route["sync"] else []
        )
        out.append(
            {
                "id": agent,
                "slug": agent_slug(agent),
                "name": route["name"],
                "routes": routes or [NONE],
                "plugin": route["plugin"],
                "sync": route["sync"],
                "reason": route["reason"],
                "note": route["note"],
                "evidence": route["evidence"],
                "turn_end": agent in stops,
                "config": matrix.get("config"),
                "tier": tier["tier"],
                "grade": tier["grade"],
                "fail_mode": tier["fail_mode"],
                "basis": tier["basis"],
                "recorded": tier["recorded"],
                "events": [
                    {
                        "event": event,
                        "block": bool(cap.get("block")),
                        "rewrite": bool(cap.get("rewrite")),
                        "fail_mode": cap.get("fail_mode") or engine.NOT_APPLICABLE,
                    }
                    for event, cap in matrix["events"].items()
                ],
                "notes": matrix.get("notes") or "",
                "ask": claims.get(agent),
                "timeout": timeouts.get(agent),
                "ledger": [r for r in rows if r["agent"] == agent],
            }
        )
    return out
