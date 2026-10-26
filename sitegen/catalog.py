"""Read registry.yaml and each manifest into Policy records."""

import re
import subprocess
from pathlib import Path

import yaml

from .engine import POLICY_ID_RE
from .model import Example, Latest, Policy
from .paths import safe_join

REGISTRY = "registry.yaml"
MANIFEST = "manifest.yaml"
EVALS = "evals/suite.yaml"
LIFECYCLE_HIDDEN = {"deprecated", "retired"}
# A raw catalog field at the start of a sentence: "trigger:", "avoid:", "apply:".
FIELD_LABEL_RE = re.compile(r"[a-z][a-z_-]*: ")
# A sentence that opens with a short label, such as "Hunk-local:" or "Enforced counterparts:".
LABEL_RE = re.compile(r"[A-Za-z][\w-]*(?: [\w-]+){0,2}: ")
TRIGGER_FIELD = "trigger:"
MISSES_MARKERS = ("Misses:", "Not caught here:")
EXPECT_WORDS = {"block": "Refused", "ask": "Asks", "warn": "Warns", "allow": "Allowed"}
WHERE_MAP = (
    ("shell command", "command"),
    ("file writes", "write"),
    ("turn end", "turn-end"),
    ("advisory", "text"),
)
CATALOG_TREE = "https://github.com/open-coder-ai/chock-catalog/tree/"


class CatalogError(Exception):
    """A catalog checkout that cannot be read, is at the wrong commit, or names an unsafe id or path."""


def check_policy_id(policy_id: object) -> str:
    """A registry id, refused unless it matches the engine's policy-id grammar (engine.POLICY_ID_RE)."""
    if not isinstance(policy_id, str) or not POLICY_ID_RE.fullmatch(policy_id):
        raise CatalogError(
            f"{REGISTRY}: policy id {policy_id!r} is not a valid policy id "
            f"(must match {POLICY_ID_RE.pattern}); it would reach a shell line and a path"
        )
    return policy_id


def policy_dir(catalog: Path, row: dict) -> Path:
    """The folder a registry row's `path` names, refused unless it stays inside the catalog."""
    return safe_join(catalog, row.get("path"), f"{REGISTRY}: path of {row.get('id')!r}")


def catalog_head(catalog: Path) -> str:
    """The HEAD sha of the catalog checkout."""
    result = subprocess.run(
        ["git", "-C", str(catalog), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"{catalog}: not a git checkout ({result.stderr.strip()})"
        raise CatalogError(msg)
    return result.stdout.strip()


def load_hidden(data_dir: Path) -> set[str]:
    """Policy ids from data/hidden.yaml that are never shown."""
    data = yaml.safe_load((data_dir / "hidden.yaml").read_text(encoding="utf-8")) or {}
    return set(data.get("hidden") or [])


def _collapse(text: object) -> str:
    return " ".join(str(text or "").split())


def extract_misses(description: str) -> str | None:
    """Text after the first misses marker, through the next period that ends a sentence."""
    starts = [
        (i, len(marker))
        for marker in MISSES_MARKERS
        if (i := description.find(marker)) != -1
    ]
    if not starts:
        return None
    start, width = min(starts)
    rest = description[start + width :]
    end = re.search(r"\.(?=\s|$)", rest)
    return rest[: end.end() if end else len(rest)].strip()


def where_tags(says: str) -> list[str]:
    """Tags derived from a label's `says` text (plan 5.4)."""
    return [tag for needle, tag in WHERE_MAP if needle in says]


def first_sentence(text: str) -> str:
    """The description's first sentence, used on list rows and meta tags."""
    end = re.search(r"\.(?=\s|$)", text)
    return text[: end.end()] if end else text


def lead_sentences(text: str, min_chars: int) -> str:
    """The description's opening sentences, as many as reach `min_chars` (a page's meta description)."""
    lead = ""
    rest = text
    while rest and len(lead) < min_chars:
        sentence = first_sentence(rest)
        lead = f"{lead} {sentence}".strip()
        rest = rest[len(sentence) :].lstrip()
    return lead


def _sentences(text: str) -> list[str]:
    """The description split into sentences, the way first_sentence ends one."""
    sentences = []
    rest = text
    while rest:
        sentence = first_sentence(rest)
        sentences.append(sentence)
        rest = rest[len(sentence) :].lstrip()
    return sentences


def prose_lead(text: str, min_chars: int) -> str:
    """The prose after the description's leading `field:` sentences; "" if the next one is a label too."""
    sentences = _sentences(text)
    while sentences and FIELD_LABEL_RE.match(sentences[0]):
        sentences.pop(0)
    if not sentences or LABEL_RE.match(sentences[0]):
        return ""
    return lead_sentences(" ".join(sentences), min_chars)


def trigger_field(text: str) -> str:
    """The text of the description's `trigger:` field, or "" if it has none."""
    for sentence in _sentences(text):
        if sentence.startswith(TRIGGER_FIELD):
            return sentence[len(TRIGGER_FIELD) :].strip()
    return ""


def _examples(path: Path) -> list[Example]:
    """The first refused and first allowed execute cases in evals/suite.yaml (5.5)."""
    suite_file = path / EVALS
    if not suite_file.is_file():
        return []
    suite = yaml.safe_load(suite_file.read_text(encoding="utf-8")) or {}
    cases = (suite.get("suite") or {}).get("cases") or []
    refused = allowed = None
    for case in cases:
        execute = case.get("execute") or {}
        expect = str(execute.get("expect") or "")
        if expect == "allow" and allowed is None:
            allowed = case
        elif expect in ("block", "ask", "warn") and refused is None:
            refused = case
    examples = []
    for case in (refused, allowed):
        if case is None:
            continue
        execute = case.get("execute") or {}
        command = execute.get("command")
        examples.append(
            Example(
                word=EXPECT_WORDS[str(execute.get("expect"))],
                prompt=_collapse(case.get("prompt")),
                command=str(command) if command else None,
            )
        )
    return examples


# Keys of the registry's label block that are not an agent's grade.
LABEL_EXTRAS = ("misses", "status")


def _client_labels(row: dict) -> dict[str, dict[str, str]]:
    """The registry's per-agent label block (L1), without its `misses` and `status` entries."""
    block = row.get("label") or {}
    return {
        client: {"keyword": str(v["keyword"]), "says": str(v["says"])}
        for client, v in block.items()
        if client not in LABEL_EXTRAS and isinstance(v, dict) and "keyword" in v
    }


def _label_status(row: dict) -> str | None:
    """The registry's `label.status` keyword (BV-C3), or None when the key is absent."""
    status = (row.get("label") or {}).get("status")
    if isinstance(status, dict) and status.get("keyword"):
        return str(status["keyword"])
    return None


def _latest_entry(changelog: list[dict], version: str) -> Latest:
    """The entry whose version equals the manifest's, else the newest by date (plan 5.1)."""
    entry = next((e for e in changelog if str(e.get("version")) == version), None)
    if entry is None and changelog:
        entry = max(changelog, key=lambda e: str(e.get("date") or ""))
    entry = entry or {}
    changes = entry.get("changes") or [""]
    return Latest(
        version=str(entry.get("version", "")),
        date=str(entry.get("date", "")),
        change=_collapse(changes[0]),
    )


def _fill_groups(text: str, found: re.Match) -> str:
    """One-pass fill of __GROUP__ tokens in `text` from the match's named groups."""
    return re.sub(r"__([A-Z]+)__", lambda m: found[m.group(1)], text)


def plain_change(change: str, rewrites: list[dict[str, str]]) -> str:
    """The changelog line in plain words when a data rewrite matches it, else as written."""
    for rule in rewrites:
        found = re.search(rule["match"], change)
        if found:
            return _fill_groups(rule["text"], found)
    return change


def registry_ids(catalog: Path) -> list[str]:
    """Every policy id in registry.yaml, shown or not."""
    registry = yaml.safe_load((catalog / REGISTRY).read_text(encoding="utf-8")) or {}
    return [check_policy_id(row.get("id")) for row in registry.get("policies", [])]


def load_policies(catalog: Path, hidden: set[str], catalog_ref: str) -> list[Policy]:
    """Every registry policy that is not hidden or retired, sorted by id."""
    registry = yaml.safe_load((catalog / REGISTRY).read_text(encoding="utf-8")) or {}
    policies = []
    for row in registry.get("policies", []):
        policy_id = check_policy_id(row.get("id"))
        if policy_id in hidden:
            continue
        folder = policy_dir(catalog, row)
        manifest = yaml.safe_load((folder / MANIFEST).read_text(encoding="utf-8"))
        status = (manifest.get("lifecycle") or {}).get("status")
        if status in LIFECYCLE_HIDDEN:
            continue
        version = str(manifest.get("version") or row["version"])
        description = _collapse(manifest.get("description") or row.get("description"))
        policies.append(
            Policy(
                id=policy_id,
                path=str(row["path"]),
                name=_collapse(manifest.get("name") or policy_id),
                version=str(row["version"]),
                description=description,
                eval_cases=int(row.get("eval_cases") or 0),
                eval_executed=int(row.get("eval_executed") or 0),
                misses=extract_misses(description),
                latest=_latest_entry(manifest.get("changelog") or [], version),
                source_url=f"{CATALOG_TREE}{catalog_ref}/{row['path']}",
                enforces=str(row.get("enforces") or ""),
                examples=_examples(folder),
                client_labels=_client_labels(row),
                status=_label_status(row),
            )
        )
    return sorted(policies, key=lambda p: p.id)


def apply_labels(policies: list[Policy], labels: dict, words: dict[str, str]) -> None:
    """Set each policy's keyword, displayed word, `says` and `where` from engine labels."""
    for policy in policies:
        label = labels[policy.id]
        policy.keyword = label.keyword
        policy.word = words[label.keyword]
        policy.says = label.says
        policy.where = where_tags(label.says)


def apply_groups(policies: list[Policy], presets: list) -> None:
    """Set each policy's `groups` to the preset ids that list it, in presets.yaml order."""
    for policy in policies:
        policy.groups = [preset.id for preset in presets if policy.id in preset.members]
