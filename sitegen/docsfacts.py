"""Per-agent facts for the docs: agentseam's matrix joined with the engine's routes, claims and ledger."""

from typing import Any

import agentseam.matrix
import agentseam.tier_table

from . import engine
from .pageparts import PageError

PLUGIN, SYNC, NONE = "plugin", "sync", "none"


def agent_slug(agent: str) -> str:
    """The URL slug of an agent page."""
    return agent.replace("_", "-")


def _check_joins(docs: dict[str, Any], clients: list[str]) -> None:
    """plugin_agents names every engine client once, each mapped to a matrix row."""
    joins = docs["plugin_agents"]
    if sorted(joins) != sorted(clients):
        raise PageError(
            f"docs.yaml plugin_agents: {sorted(joins)} != engine {sorted(clients)}"
        )
    for client, agent in joins.items():
        if agent not in agentseam.matrix.MATRIX:
            raise PageError(
                f"docs.yaml plugin_agents: {client} -> {agent} is no agentseam agent"
            )


def _ledger(docs: dict[str, Any]) -> list[dict[str, Any]]:
    """The engine's witness ledger, each row with the route its surface proves."""
    routes = docs["surface_routes"]
    rows = []
    for row in engine.witness_ledger():
        if row["surface"] not in routes:
            raise PageError(
                f"witness ledger surface {row['surface']!r} has no route in docs.yaml"
            )
        if row["agent"] not in agentseam.matrix.MATRIX:
            raise PageError(
                f"witness ledger agent {row['agent']!r} is no agentseam agent"
            )
        rows.append({**row, "route": routes[row["surface"]]})
    return rows


def _no_route(row: dict[str, Any]) -> str:
    """Why an agent with neither route has none: a docs.yaml no_route key."""
    if row["tier"] == agentseam.matrix.TIER_NONE:
        return "none"
    if row["tier"] == agentseam.matrix.TIER_UNADAPTED:
        return "unadapted"
    if str(row.get("config") or "").startswith("~"):
        return "home_config"
    return "no_block"


def agents(docs: dict[str, Any], clients: dict[str, Any]) -> list[dict[str, Any]]:
    """One record per agentseam matrix row, in agentseam's order, with everything a docs page shows."""
    _check_joins(docs, clients["order"])
    tiers = {row["agent"]: row for row in agentseam.tier_table.rows()}
    syncs = set(engine.sync_agents())
    stops = set(engine.stop_agents())
    names = engine.sync_names()
    claims = {row["agent"]: row for row in engine.ask_claims()}
    timeouts = engine.hook_timeouts()
    ledger = _ledger(docs)
    out = []
    for agent, row in agentseam.matrix.MATRIX.items():
        plugin = [c for c in clients["order"] if docs["plugin_agents"][c] == agent]
        routes = ([PLUGIN] if plugin else []) + ([SYNC] if agent in syncs else [])
        out.append(
            {
                "id": agent,
                "slug": agent_slug(agent),
                "name": row["display"],
                "routes": routes or [NONE],
                "no_route": None if routes else _no_route(row),
                "plugin_clients": plugin,
                "sync_name": names.get(agent, agent) if agent in syncs else None,
                "turn_end": agent in stops,
                "config": row.get("config"),
                "tier": tiers[agent]["tier"],
                "grade": tiers[agent]["grade"],
                "fail_mode": tiers[agent]["fail_mode"],
                "basis": tiers[agent]["basis"],
                "recorded": tiers[agent]["recorded"],
                "events": [
                    {
                        "event": event,
                        "block": bool(cap.get("block")),
                        "rewrite": bool(cap.get("rewrite")),
                        "fail_mode": cap.get("fail_mode")
                        or agentseam.tier_table.NOT_APPLICABLE,
                    }
                    for event, cap in row["events"].items()
                ],
                "notes": row.get("notes") or "",
                "ask": claims.get(agent),
                "timeout": timeouts.get(agent),
                "ledger": [r for r in ledger if r["agent"] == agent],
            }
        )
    return out
