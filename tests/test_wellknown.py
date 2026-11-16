"""S-8 and S-9: /.well-known/security.txt (RFC 9116) and the IndexNow key file."""

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml

from sitegen import docsource, wellknown
from sitegen.__main__ import TEMPLATES
from sitegen.pageparts import PageError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONF = yaml.safe_load((DATA / "well-known.yaml").read_text(encoding="utf-8"))
ENGINE_REF = (ROOT / ".framework-ref").read_text(encoding="utf-8").strip()
FIELD = re.compile(r"([A-Za-z-]+): (\S+)")
# RFC 9116 section 2.5.5: an RFC 3339 date-time; this site writes UTC with a Z.
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def _fields(text: str) -> dict[str, list[str]]:
    """Each field name in a security.txt and its values, every line a field."""
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = FIELD.fullmatch(line)
        assert match, f"not a field line: {line!r}"
        fields.setdefault(match[1], []).append(match[2])
    return fields


def _security_txt(built) -> str:
    return (built.out / ".well-known" / "security.txt").read_text(encoding="utf-8")


def test_security_txt_has_one_https_contact_and_one_future_expires(built) -> None:
    fields = _fields(_security_txt(built))
    assert len(fields["Contact"]) == 1
    assert fields["Contact"][0].startswith("https://")
    assert len(fields["Expires"]) == 1
    expires = dt.datetime.strptime(fields["Expires"][0], STAMP).replace(tzinfo=dt.UTC)
    now = dt.datetime.now(dt.UTC)
    assert now < expires <= now + dt.timedelta(days=366)


def test_security_txt_contact_is_the_engine_security_md_contact(built) -> None:
    """Contact is read from chock's SECURITY.md snapshot, never typed in data."""
    prose = docsource.load(DATA, ENGINE_REF)
    section = CONF["security_txt"]["source_section"]
    assert f"## {section}" in prose["SECURITY.md"]
    (contact,) = _fields(_security_txt(built))["Contact"]
    assert f"<{contact}>" in prose["SECURITY.md"]
    assert "advisories" not in (DATA / "well-known.yaml").read_text(encoding="utf-8")


def test_security_txt_optional_fields(built) -> None:
    fields = _fields(_security_txt(built))
    assert fields["Canonical"] == ["https://chock.sh/.well-known/security.txt"]
    assert fields["Policy"] == [
        f"https://github.com/open-coder-ai/chock/blob/{ENGINE_REF}/SECURITY.md"
    ]
    assert fields["Preferred-Languages"] == ["en"]
    assert set(fields) == {
        "Contact",
        "Expires",
        "Policy",
        "Canonical",
        "Preferred-Languages",
    }


def test_security_txt_is_utf8_text_with_lf_endings(built) -> None:
    raw = (built.out / ".well-known" / "security.txt").read_bytes()
    raw.decode("utf-8")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")


def test_indexnow_key_file_holds_exactly_the_configured_key(built) -> None:
    key = CONF["indexnow"]["key"]
    assert re.fullmatch(r"[a-zA-Z0-9-]{8,128}", key)
    assert (built.out / f"{key}.txt").read_text(encoding="utf-8") == key


def test_expires_is_build_day_midnight_plus_days() -> None:
    assert wellknown.expires(dt.date(2028, 2, 29), 365) == "2029-02-28T00:00:00Z"
    with pytest.raises(PageError, match="expires_days"):
        wellknown.expires(dt.date(2026, 1, 1), 366)


def test_contact_needs_exactly_one_https_link() -> None:
    section = "## Reporting a vulnerability\n\n"
    good = section + "- open <https://example.org/new>\n"
    assert wellknown.contact(good, "Reporting a vulnerability") == (
        "https://example.org/new"
    )
    for text in (
        section + "no link\n",
        section + "<https://a.example/x> and <https://b.example/y>\n",
        section + "<http://plain.example/x>\n",
    ):
        with pytest.raises(PageError, match="need 1"):
            wellknown.contact(text, "Reporting a vulnerability")


def test_security_txt_refuses_a_value_that_would_add_a_field() -> None:
    conf = dict(CONF["security_txt"], preferred_languages="en\nContact: x")
    prose = docsource.load(DATA, ENGINE_REF)
    with pytest.raises(PageError, match="LANGUAGES"):
        wellknown.security_txt(
            conf,
            prose,
            "https://chock.sh",
            "https://github.com/open-coder-ai/chock",
            ENGINE_REF,
            dt.date(2026, 1, 1),
            TEMPLATES,
        )


def test_indexnow_key_refuses_bad_characters() -> None:
    for key in ("short", "a/b/../../../etc", "x" * 129, 12345678):
        with pytest.raises(PageError, match="indexnow.key"):
            wellknown.indexnow_key({"key": key})
