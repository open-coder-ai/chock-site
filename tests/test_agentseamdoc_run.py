"""`agentseamdoc run` accepts agentseam from PyPI or from git, and refuses anything else."""

from sitegen import agentseamdoc, engine

DATA = agentseamdoc.DATA
REF = agentseamdoc.pinned(DATA)


def _install(monkeypatch, spec, commit, version="0.4.1") -> None:
    monkeypatch.setattr(engine, "agentseam_chock_spec", lambda: spec)
    monkeypatch.setattr(engine, "agentseam_commit", lambda: commit)
    monkeypatch.setattr(engine, "agentseam_meta", lambda: {"version": version})


def test_a_commit_pin_accepts_the_snapshot_commit(monkeypatch) -> None:
    _install(monkeypatch, ("commit", REF), REF)
    assert agentseamdoc._installed_refusal(DATA, REF) == ""


def test_a_commit_pin_refuses_another_commit(monkeypatch) -> None:
    _install(monkeypatch, ("commit", REF), "0" * 40)
    assert "installed agentseam is 0000" in agentseamdoc._installed_refusal(DATA, REF)


def test_a_commit_pin_refuses_a_pypi_install(monkeypatch) -> None:
    _install(monkeypatch, ("commit", REF), "")
    assert "not from git" in agentseamdoc._installed_refusal(DATA, REF)


def test_a_version_pin_accepts_pypi(monkeypatch) -> None:
    version = agentseamdoc.pinned_version(DATA)
    _install(monkeypatch, ("version", version), "", version)
    assert agentseamdoc._installed_refusal(DATA, REF) == ""


def test_a_version_pin_accepts_git_at_the_snapshot_commit(monkeypatch) -> None:
    version = agentseamdoc.pinned_version(DATA)
    _install(monkeypatch, ("version", version), REF, version)
    assert agentseamdoc._installed_refusal(DATA, REF) == ""


def test_a_version_pin_refuses_git_at_another_commit(monkeypatch) -> None:
    version = agentseamdoc.pinned_version(DATA)
    _install(monkeypatch, ("version", version), "0" * 40, version)
    assert "installed agentseam is 0000" in agentseamdoc._installed_refusal(DATA, REF)


def test_a_version_pin_refuses_another_installed_version(monkeypatch) -> None:
    version = agentseamdoc.pinned_version(DATA)
    _install(monkeypatch, ("version", version), "", "0.4.2")
    assert "version 0.4.2" in agentseamdoc._installed_refusal(DATA, REF)


def test_a_version_pin_refuses_another_chock_version(monkeypatch) -> None:
    _install(monkeypatch, ("version", "0.4.2"), "", "0.4.2")
    assert "chock requires 0.4.2" in agentseamdoc._installed_refusal(DATA, REF)


def test_a_version_pin_refuses_another_snapshot_version(monkeypatch) -> None:
    _install(monkeypatch, ("version", "0.4.1"), "")
    monkeypatch.setattr(agentseamdoc, "pinned_version", lambda data: "0.4.0")
    assert "snapshot is version 0.4.0" in agentseamdoc._installed_refusal(DATA, REF)


def test_any_other_pin_is_refused(monkeypatch) -> None:
    _install(monkeypatch, "", REF)
    assert "does not pin agentseam" in agentseamdoc._installed_refusal(DATA, REF)


def test_run_exits_2_with_the_refusal(monkeypatch, capsys) -> None:
    _install(monkeypatch, ("commit", REF), "")
    assert agentseamdoc.main(["run", "--check"]) == 2
    assert "not from git" in capsys.readouterr().err
