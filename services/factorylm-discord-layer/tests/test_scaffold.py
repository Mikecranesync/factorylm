"""Scaffold tests — verify project structure is importable."""

import importlib


def test_package_importable():
    mod = importlib.import_module("factorylm")
    assert mod is not None


def test_subpackages_importable():
    for name in ("factorylm.setup", "factorylm.relay", "factorylm.bot"):
        mod = importlib.import_module(name)
        assert mod is not None
