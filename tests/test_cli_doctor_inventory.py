from __future__ import annotations

from typer.testing import CliRunner

from allbrain.cli import main


def test_doctor_inventory_prints_static() -> None:
    result = CliRunner().invoke(main.app, ["doctor", "--inventory", "--project", "."])
    assert result.exit_code == 0
    assert "project://resume" in result.stderr
    assert "resume_project" in result.stderr


def test_doctor_inventory_json_emits_json() -> None:
    result = CliRunner().invoke(main.app, ["doctor", "--inventory", "--json", "--project", "."])
    assert result.exit_code == 0
    assert "project://resume" in result.stderr
    assert "resume_project" in result.stderr


def test_doctor_inventory_verify_ok(monkeypatch) -> None:
    report = {
        "ok": True,
        "resources": {"matched": ["project://resume"], "missing": [], "extra": []},
        "prompts": {"matched": ["resume_project"], "missing": [], "extra": []},
    }
    monkeypatch.setattr(
        "allbrain.ops.inventory.verify_inventory_against_server",
        lambda client: report,
    )
    result = CliRunner().invoke(main.app, ["doctor", "--verify", "--project", "."])
    assert result.exit_code == 0
    assert "matches server" in result.stderr


def test_doctor_inventory_verify_reports_missing(monkeypatch) -> None:
    report = {
        "ok": False,
        "resources": {"matched": [], "missing": ["project://resume"], "extra": []},
        "prompts": {"matched": [], "missing": ["resume_project"], "extra": []},
    }
    monkeypatch.setattr(
        "allbrain.ops.inventory.verify_inventory_against_server",
        lambda client: report,
    )
    result = CliRunner().invoke(main.app, ["doctor", "--verify", "--project", "."])
    assert result.exit_code == 1
    assert "missing" in result.stderr
