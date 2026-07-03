from __future__ import annotations

from types import SimpleNamespace

from allbrain.server.lifecycle_middleware import _client_info, _result_outcome, _tool_request


def test_client_info_extracts_dict_client_info() -> None:
    message = {"clientInfo": {"name": "codex", "version": "1.2.3"}}

    assert _client_info(message) == ("codex", "1.2.3")


def test_client_info_extracts_object_client_info() -> None:
    message = SimpleNamespace(params=SimpleNamespace(client_info=SimpleNamespace(name="cli", version="2.0")))

    assert _client_info(message) == ("cli", "2.0")


def test_tool_request_normalizes_non_dict_arguments() -> None:
    message = SimpleNamespace(params=SimpleNamespace(name="save_event", arguments=["not", "dict"]))

    assert _tool_request(message) == ("save_event", {})


def test_result_outcome_handles_error_flags_and_structured_content() -> None:
    assert _result_outcome(SimpleNamespace(is_error=True)) == (False, "MCP tool result marked as error")
    assert _result_outcome(SimpleNamespace(structured_content={"ok": False, "error": "bad"})) == (False, "bad")
    assert _result_outcome(SimpleNamespace(structuredContent={"ok": True})) == (True, None)
    assert _result_outcome(SimpleNamespace()) == (True, None)
