"""The builder's agent picker: witness status, per-client labels and apply steps (BV-S1)."""

from pathlib import Path
from typing import Any

import yaml

from . import engine
from .model import Policy
from .pageparts import PageError, data_fill

WITNESS_YAML = "witness.yaml"
WITNESS_STATES = ("witnessed", "untested")
# The client whose labels the engine computes; the others come from the catalog's label blocks.
ENGINE_CLIENT = "claude-code"


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


def check_quiz_agents(quiz: dict[str, Any], clients: list[str]) -> None:
    """The quiz's agent question offers exactly the picker's clients, in the same order."""
    question = next(q for q in quiz["questions"] if q["id"] == "agent")
    ids = [option["id"] for option in question["options"]]
    if ids != clients:
        raise PageError(f"quiz.yaml: agent options {ids} != witness.yaml {clients}")


def has_client_grades(policies: list[Policy], clients: list[str]) -> bool:
    """True when every policy's registry label block grades every client (chock-catalog#244)."""
    return all(set(clients) <= set(p.client_labels) for p in policies)


def client_labels(
    policies: list[Policy], client: str, graded: bool, words: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Each policy's own label on `client`: the catalog's grade, or the Claude Code label without one."""
    out = {}
    for policy in policies:
        if client == ENGINE_CLIENT or not graded:
            keyword, says = policy.keyword, policy.says
        else:
            label = policy.client_labels[client]
            keyword, says = label["keyword"], label["says"]
        if keyword not in words:
            raise PageError(f"{policy.id}: {client} label {keyword!r} has no word")
        out[policy.id] = {"keyword": keyword, "says": says}
    return out


def builder_clients(
    data_dir: Path,
    site_data: dict[str, Any],
    policies: list[Policy],
    words: dict[str, str],
) -> dict[str, Any]:
    """The site.json `builder_clients` block: picker order, witness state, labels and steps per client."""
    config = site_data["builder_clients"]
    texts = config["texts"]
    witness = load_witness(data_dir, engine.client_ids())
    graded = has_client_grades(policies, engine.client_ids())
    clients = {}
    for client, state in witness["clients"].items():
        name = engine.client_name(client)
        clients[client] = {
            "name": name,
            "witness": state,
            "untested_label": data_fill(texts["untested_label"], {"__NAME__": name}),
            "untested_line": data_fill(texts["untested_line"], {"__NAME__": name}),
            "steps_heading": data_fill(texts[f"steps_{state}"], {"__NAME__": name}),
            "report": data_fill(witness["report"], {"__CLIENT__": client}),
            "steps": engine.client_steps(client),
            "labels": client_labels(policies, client, graded, words),
        }
    return {
        "default": witness["default"],
        "order": list(witness["clients"]),
        "graded": graded,
        "bundle_version": config["bundle_version"],
        "commands": config["commands"],
        "texts": texts,
        "meanings": {
            key: site_data["label_meanings"][word] for key, word in words.items()
        },
        "clients": clients,
    }
