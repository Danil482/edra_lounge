"""SEED_WITH_NAMES toggle: anonymized by default, real names only when opted in."""

from backend.seed_from_eval import _choose_profile_name, _names_enabled


def test_names_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SEED_WITH_NAMES", raising=False)
    assert _names_enabled() is False


def test_names_enabled_truthy(monkeypatch):
    for val in ("1", "true", "TRUE", "Yes", "yes"):
        monkeypatch.setenv("SEED_WITH_NAMES", val)
        assert _names_enabled() is True


def test_names_disabled_falsy(monkeypatch):
    for val in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("SEED_WITH_NAMES", val)
        assert _names_enabled() is False


def test_choose_name_anonymized_when_off():
    assert _choose_profile_name("Vinki Lee", "Marketing Investor", 619, with_names=False) == "Marketing Investor #619"


def test_choose_name_real_when_on():
    assert _choose_profile_name("Vinki Lee", "Marketing Investor", 619, with_names=True) == "Vinki Lee"


def test_choose_name_falls_back_when_no_name():
    assert _choose_profile_name(None, "Marketing Investor", 619, with_names=True) == "Marketing Investor #619"
    assert _choose_profile_name("  ", "Marketing Investor", 619, with_names=True) == "Marketing Investor #619"


def test_choose_name_strips_whitespace():
    assert _choose_profile_name("  Vinki Lee  ", "X", 1, with_names=True) == "Vinki Lee"
