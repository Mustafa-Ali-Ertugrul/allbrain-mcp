from __future__ import annotations

import importlib.util
from pathlib import Path


def _installer_module():
    script = Path(__file__).parents[1] / "scripts" / "install_mcp_clients.py"
    spec = importlib.util.spec_from_file_location("install_mcp_clients", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portable_server_has_no_machine_specific_paths(tmp_path: Path) -> None:
    installer = _installer_module()

    server = installer.allbrain_server(tmp_path, tmp_path, "codex", Path(".allbrain.db"), portable=True)

    assert server["cwd"] == "."
    assert server["args"] == [
        "run",
        "--project",
        ".",
        "allbrain",
        "start",
        "--project",
        ".",
        "--agent",
        "codex",
        "--db-path",
        ".allbrain.db",
    ]
    assert str(Path.home()) not in repr(server)


def test_global_server_uses_resolved_paths(tmp_path: Path) -> None:
    installer = _installer_module()
    database = tmp_path / "shared.db"

    server = installer.allbrain_server(tmp_path, tmp_path, "zed", database)

    assert server["cwd"] == str(tmp_path)
    assert server["args"][2] == str(tmp_path)
    assert server["args"][6] == str(tmp_path)
    assert server["args"][-1] == str(database)
