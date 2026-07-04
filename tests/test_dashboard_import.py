"""Smoke test: dashboard_server module imports and basic types."""

from allbrain.ui.dashboard_server import _HTML_PAGE, DashboardHandler


def test_dashboard_html_is_valid() -> None:
    assert "<!DOCTYPE html>" in _HTML_PAGE
    assert "AllBrain Dashboard" in _HTML_PAGE
    assert "/api/overview" in _HTML_PAGE
    assert "/api/events" in _HTML_PAGE
    assert "/api/graph" in _HTML_PAGE


def test_dashboard_handler_class() -> None:
    assert issubclass(DashboardHandler, object)
    assert hasattr(DashboardHandler, "do_GET")
