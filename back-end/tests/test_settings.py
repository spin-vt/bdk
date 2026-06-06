"""Regression test for the IN_PRODUCTION parsing fix.

`os.getenv("IN_PRODUCTION")` returned a raw string, and a non-empty string like
"0" is truthy in Python — so the dev value IN_PRODUCTION=0 read as True and the
app issued production `Secure` cookies in dev (which browsers may drop over plain
http://localhost). Settings now parses it as a real boolean; this pins that the
compose values map correctly: prod "1" -> True, test "" -> False, dev "0" ->
False.
"""

import importlib

import utils.settings


def _reload_with(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("IN_PRODUCTION", raising=False)
    else:
        monkeypatch.setenv("IN_PRODUCTION", raw)
    importlib.reload(utils.settings)
    return utils.settings.IN_PRODUCTION


def test_in_production_parsing(monkeypatch):
    truthy = ["1", "true", "True", "TRUE", "yes", "on"]
    falsy = ["0", "", "false", "False", "no", "off", None]
    try:
        for raw in truthy:
            assert _reload_with(monkeypatch, raw) is True, f"{raw!r} should be production"
        for raw in falsy:
            assert _reload_with(monkeypatch, raw) is False, f"{raw!r} should NOT be production"
    finally:
        # Restore the suite default ("" -> False) so later tests see a stable module.
        _reload_with(monkeypatch, "")
