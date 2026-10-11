"""The builder's agent picker: witness status, per-client labels and apply steps (BV-S1)."""

from pathlib import Path
from typing import Any

import yaml

from . import engine
from .model import Policy
from .pageparts import PageError, data_fill

WITNESS_YAML = "witness.yaml"
WITNESS_STATES = ("witnessed", "untested")
EVIDENCE_YAML = "evidence.yaml"
EVIDENCE_ISSUES = "https://github.com/open-coder-ai/agentseam/issues/"
# The client whose labels the engine computes; the others come from the catalog's label blocks.
ENGINE_CLIENT = "claude-code"
# The keyword of a policy the catalog does not grade on the chosen client.
UNGRADED = "ungraded"


def load_witness(data_dir: Path, clients: list[str]) -> dict[str, Any]:
    """data/witness.yaml, checked: every engine client exactly once, each witnessed or untested."""
    data = yaml.safe_load((data_dir / WITNESS_YAML).read_text(encoding="utf-8"))
    states = data["clients"]
    if sorted(states) != sorted(clients):
        raise PageError(
            f"{WITNESS_YAML}: clients {sorted(states)} != engine {sorted(clients)}"
        )
    for client, state in states.items():
        if state not in WITNESS_STATES:
            raise PageError(
                f"{WITNESS_YAML}: {client} is {state!r}, not one of {WITNESS_STATES}"
            )
    if data["default"] not in states:
        raise PageError(f"{WITNESS_YAML}: default {data['default']!r} is not a client")
    return data


def load_evidence(data_dir: Path, witness: dict[str, Any]) -> dict[str, Any]:
    """data/evidence.yaml, checked: each row an untested agent with a positive issue number."""
    data = yaml.safe_load((data_dir / EVIDENCE_YAML).read_text(encoding="utf-8"))
    if data["issue_url"] != EVIDENCE_ISSUES + "__NUMBER__":
        raise PageError(
            f"{EVIDENCE_YAML}: issue_url is not {EVIDENCE_ISSUES}__NUMBER__"
        )
    for client, number in (data["issues"] or {}).items():
        state = witness["clients"].get(client)
        if state != "untested":
            raise PageError(
                f"{EVIDENCE_YAML}: {client} is {state or 'not an agent'}, not untested"
            )
        if type(number) is not int or number < 1:
            raise PageError(
                f"{EVIDENCE_YAML}: {client} issue {number!r} is not a number"
            )
    return data


def evidence_notice(
    evidence: dict[str, Any], client: str, name: str
) -> dict[str, str] | None:
    """An untested agent's evidence notice: label, line, issue link; None without a row."""
    number = (evidence["issues"] or {}).get(client)
    if number is None:
        return None
    subs = {"__NAME__": name, "__NUMBER__": str(number)}
    return {key: data_fill(text, subs) for key, text in evidence["texts"].items()} | {
        "url": data_fill(evidence["issue_url"], subs)
    }


def quiz_agent_options(quiz: dict[str, Any], block: dict[str, Any]) -> None:
    """Fill the quiz's agent question from the picker: same agents, order, names and witness state."""
    question = next(q for q in quiz["questions"] if q["id"] == "agent")
    if question.get("options"):
        raise PageError(
            "quiz.yaml: the agent question takes its options from witness.yaml"
        )
    subs = question["subs"]
    question["options"] = [
        {
            "id": client,
            "label": block["clients"][client]["name"],
            "sub": subs[block["clients"][client]["witness"]],
            **({"default": True} if client == block["default"] else {}),
        }
        for client in block["order"]
    ]


def drop_engine_untested(
    rules: list[dict[str, Any]], block: dict[str, Any]
) -> list[dict[str, Any]]:
    """The warning rules without the engine's own "untested" note: witness.yaml says that, once."""
    prefix = block["engine_untested_prefix"]
    kept = [
        r for r in rules if not (r["kind"] == "client" and r["says"].startswith(prefix))
    ]
    if len(rules) - len(kept) != 1:
        raise PageError(f"engine warnings: expected one rule starting {prefix!r}")
    return kept


def graded_clients(policies: list[Policy], clients: list[str]) -> list[str]:
    """The clients the catalog grades on every policy (chock-catalog#244); the engine's always."""
    return [
        client
        for client in clients
        if client == ENGINE_CLIENT or all(client in p.client_labels for p in policies)
    ]


def client_labels(
    policies: list[Policy], client: str, words: dict[str, str], ungraded_says: str
) -> dict[str, dict[str, str]]:
    """Each policy's own label on `client`: the catalog's grade, or "not graded" without one."""
    out = {}
    for policy in policies:
        if client == ENGINE_CLIENT:
            keyword, says = policy.keyword, policy.says
        elif client in policy.client_labels:
            label = policy.client_labels[client]
            keyword, says = label["keyword"], label["says"]
        else:
            keyword, says = UNGRADED, ungraded_says
        if keyword != UNGRADED and keyword not in words:
            raise PageError(f"{policy.id}: {client} label {keyword!r} has no word")
        out[policy.id] = {"keyword": keyword, "says": says}
    return out


def _per_client(config: dict[str, Any], key: str, clients: list[str]) -> dict[str, Any]:
    """A site.json builder_clients map keyed by agent; it names every agent exactly once."""
    table = config[key]
    if sorted(table) != sorted(clients):
        raise PageError(
            f"site.json builder_clients.{key}: {sorted(table)} != {clients}"
        )
    return table


def remove_steps(steps: list[dict[str, str]], client: str) -> list[dict[str, str]]:
    """The site's remove steps for a client, its engine tokens filled in one pass."""
    tokens = engine.client_tokens(client)
    return [{kind: data_fill(text, tokens) for kind, text in s.items()} for s in steps]


def builder_clients(
    data_dir: Path,
    site_data: dict[str, Any],
    policies: list[Policy],
    words: dict[str, str],
) -> dict[str, Any]:
    """The site.json `builder_clients` block: picker order, witness state, labels and steps per client."""
    config = site_data["builder_clients"]
    texts = config["texts"]
    meanings = site_data["label_meanings_raw"]
    witness = load_witness(data_dir, engine.client_ids())
    evidence = load_evidence(data_dir, witness)
    graded = graded_clients(policies, engine.client_ids())
    repos = _per_client(config, "plugin_repos", engine.client_ids())
    removes = _per_client(config, "remove", engine.client_ids())
    clients = {}
    for client, state in witness["clients"].items():
        name = engine.client_name(client)
        named = {"__NAME__": name}
        clients[client] = {
            "name": name,
            "witness": state,
            "graded": client in graded,
            "untested_label": data_fill(texts["untested_label"], named),
            "untested_line": data_fill(texts["untested_line"], named),
            "steps_heading": data_fill(texts[f"steps_{state}"], named),
            "ungraded_note": data_fill(texts["ungraded_note"], named),
            "report": data_fill(witness["report"], {"__CLIENT__": client}),
            "evidence": evidence_notice(evidence, client, name),
            "steps": engine.client_steps(client),
            "remove": remove_steps(removes[client], client),
            "plugin_repo": repos[client],
            "build_link": data_fill(texts["build_link"], named),
            "labels": client_labels(
                policies, client, words, data_fill(texts["ungraded_says"], named)
            ),
            "meanings": {
                key: data_fill(meanings[word], {"__AGENT__": name})
                for key, word in words.items()
            }
            | {UNGRADED: data_fill(texts["ungraded_meaning"], named)},
        }
    return {
        "default": witness["default"],
        "order": list(witness["clients"]),
        "graded": graded,
        "ungraded": UNGRADED,
        "engine_untested_prefix": config["engine_untested_prefix"],
        "bundle_version": config["bundle_version"],
        "commands": config["commands"],
        "texts": texts,
        "clients": clients,
    }
