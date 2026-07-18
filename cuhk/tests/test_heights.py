import pandas as pd

from pipeline import heights


def row(**kw):
    return pd.Series(kw)


def test_height_tag_parsed():
    assert heights.estimate_height(row(height="15")) == 15.0
    assert heights.estimate_height(row(height="12.5 m")) == 12.5


def test_levels_fallback():
    assert heights.estimate_height(row(height=None, **{"building:levels": "4"})) == 12.0


def test_default_when_missing():
    assert heights.estimate_height(row(height=None, **{"building:levels": None})) == 8.0


def test_garbage_falls_back():
    assert heights.estimate_height(row(height="unknown", **{"building:levels": "x"})) == 8.0
