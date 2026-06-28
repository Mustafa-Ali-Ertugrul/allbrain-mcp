from pathlib import Path

import pytest

from allbrain.server.app import (
    create_task_impl,
    list_events_impl,
    save_event_impl,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

from .test_server import make_context


def test_emoji_in_type_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="🔥", payload={})
    assert not result.ok


def test_emoji_in_source_accepted(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={"k": "v"}, source="🤖agent")
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    user_event = next(e for e in events if e.type == "file_modified")
    assert user_event.source == "🤖agent"


def test_arabic_cjk_in_payload(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    payload = {"text": "مرحبا世界"}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    stored = next(e for e in events if e.type == "file_modified")
    assert stored.payload.get("text") == "مرحبا世界"


def test_null_byte_in_source_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, source="agent\x00evil")
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_goal_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test\x00malicious")
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_task_hint_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, task_hint="hint\x00evil")
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_payload_value_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={"k": "ok\x00bad"})
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_payload_key_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={"\x00k": "val"})
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_nested_payload_value_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={"a": {"b": "ok\x00"}})
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_null_byte_in_payload_list_value_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={"items": ["ok", "bad\x00"]})
    assert not result.ok
    assert "null byte" in (result.error or "").lower()


def test_clean_payload_without_null_bytes_accepted(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    payload = {"a": 1, "b": "normal", "c": [1, 2], "d": {"x": "y"}}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    stored = next(e for e in events if e.type == "file_modified")
    assert stored.payload == payload


def test_control_chars_in_goal(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="hello\t\nworld")
    assert result.ok


def test_unicode_in_task_hint(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = save_event_impl(context, type="file_modified", payload={}, task_hint="你好世界")
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    user_event = next(e for e in events if e.type == "file_modified")
    assert user_event.task_hint == "你好世界"


def test_surrogate_pair_emoji(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    payload = {"k": "𝕏"}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    stored = next(e for e in events if e.type == "file_modified")
    assert stored.payload.get("k") == "𝕏"


def test_mixed_encoding_payload(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    payload = {"a": "ASCII", "b": "中文", "c": "🚀"}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert result.ok
    events = context.repository.list_events(project_path=context.project_path)
    stored = next(e for e in events if e.type == "file_modified")
    assert stored.payload == payload


def test_oversized_unicode_payload_rejected(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    payload = {"text": "🚀" * 100000}
    result = save_event_impl(context, type="file_modified", payload=payload)
    assert not result.ok


def test_unicode_in_type_rejected_different_scripts(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    for script in ["中文", "Ελληνικά", "Русский"]:
        result = save_event_impl(context, type=script, payload={})
        assert not result.ok, f"expected rejection for type={script}"


def test_controlled_chars_in_related_files(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    result = create_task_impl(context, goal="test", related_files=["file.py"])
    assert result.ok
