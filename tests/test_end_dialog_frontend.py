"""Feature 4: End-of-dialog popup — frontend asset verification.

Verifies that the required functions, elements, and CSS classes exist in the
frontend files. These are static checks, not browser tests.
"""

from __future__ import annotations

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _read(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


# ── app.js — showEndDialog / hideEndDialog ──────────────────────────────

def test_show_end_dialog_function_exists():
    js = _read("app.js")
    assert "function showEndDialog(" in js


def test_hide_end_dialog_function_exists():
    js = _read("app.js")
    assert "function hideEndDialog(" in js


def test_show_end_dialog_handles_accepted_outcome():
    js = _read("app.js")
    assert "'accepted'" in js or '"accepted"' in js


def test_show_end_dialog_adds_success_class():
    js = _read("app.js")
    assert "'-success'" in js or '"-success"' in js


def test_show_end_dialog_adds_failure_class():
    js = _read("app.js")
    assert "'-failure'" in js or '"-failure"' in js


def test_hide_end_dialog_adds_hidden_class():
    js = _read("app.js")
    assert "'-hidden'" in js or '"-hidden"' in js


def test_end_btn_click_listener_wired():
    js = _read("app.js")
    assert "end-btn" in js
    assert "hideEndDialog" in js


# ── index.html — end-dialog element ─────────────────────────────────────

def test_end_dialog_element_exists_in_html():
    html = _read("index.html")
    assert 'id="end-dialog"' in html


def test_end_dialog_has_hidden_class_by_default():
    html = _read("index.html")
    assert "end-dialog" in html
    assert "-hidden" in html


# ── styles.css — end-dialog classes ─────────────────────────────────────

def test_end_dialog_css_class_defined():
    css = _read("styles.css")
    assert ".end-dialog" in css


def test_end_dialog_hidden_css_defined():
    css = _read("styles.css")
    assert ".end-dialog.-hidden" in css


def test_end_card_success_css_defined():
    css = _read("styles.css")
    assert ".-success" in css


def test_end_card_failure_css_defined():
    css = _read("styles.css")
    assert ".-failure" in css
