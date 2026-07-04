"""Test CLI flags for install, onboard, uninstall commands."""

from typer.testing import CliRunner

from allbrain.cli.main import app

runner = CliRunner()


def test_install_codex_flag() -> None:
    result = runner.invoke(app, ["install", "--codex", "--dry-run"])
    assert result.exit_code == 0
    assert "Would update" in result.stdout
    assert "codex" in result.stdout.lower()


def test_install_multiple_flags() -> None:
    result = runner.invoke(app, ["install", "--codex", "--claude", "--dry-run"])
    assert result.exit_code == 0
    assert "codex" in result.stdout.lower()
    assert "claude" in result.stdout.lower()


def test_install_positional_and_flag() -> None:
    result = runner.invoke(app, ["install", "opencode", "--codex", "--dry-run"])
    assert result.exit_code == 0
    assert "opencode" in result.stdout.lower()
    assert "codex" in result.stdout.lower()


def test_install_help_shows_flags() -> None:
    result = runner.invoke(app, ["install", "--help"])
    assert result.exit_code == 0
    assert "--codex" in result.stdout
    assert "--claude" in result.stdout
    assert "--opencode" in result.stdout


def test_onboard_codex_flag() -> None:
    result = runner.invoke(app, ["onboard", "--codex", "--help"])
    assert result.exit_code == 0
    assert "--codex" in result.stdout


def test_uninstall_codex_flag() -> None:
    result = runner.invoke(app, ["uninstall", "--codex", "--dry-run"])
    assert result.exit_code == 0
    assert "codex" in result.stdout.lower()


def test_uninstall_help_shows_flags() -> None:
    result = runner.invoke(app, ["uninstall", "--help"])
    assert result.exit_code == 0
    assert "--codex" in result.stdout
    assert "--claude" in result.stdout


if __name__ == "__main__":
    test_install_codex_flag()
    test_install_multiple_flags()
    test_install_positional_and_flag()
    test_install_help_shows_flags()
    test_onboard_codex_flag()
    test_uninstall_codex_flag()
    test_uninstall_help_shows_flags()
    print("All CLI flag tests passed!")
