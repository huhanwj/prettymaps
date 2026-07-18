import json

import pytest
import requests

from pipeline import overpass


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self.payload


def test_query_caches_result(tmp_path, monkeypatch):
    calls = []

    def fake_post(url, data, timeout, headers):
        calls.append(url)
        return FakeResponse({"elements": []})

    monkeypatch.setattr(requests, "post", fake_post)
    ov = overpass.OverpassClient(cache_dir=tmp_path)
    ov.query('[out:json];node(1);out;')
    ov.query('[out:json];node(1);out;')  # 第二次应命中缓存
    assert len(calls) == 1


def test_query_retries_on_failure(tmp_path, monkeypatch):
    attempts = {"n": 0}

    def flaky_post(url, data, timeout, headers):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise requests.ConnectionError("boom")
        return FakeResponse({"ok": True})

    monkeypatch.setattr(requests, "post", flaky_post)
    monkeypatch.setattr(overpass.time, "sleep", lambda s: None)
    ov = overpass.OverpassClient(cache_dir=tmp_path)
    assert ov.query("q") == {"ok": True}
    assert attempts["n"] == 3


def test_query_raises_after_max_retries(tmp_path, monkeypatch):
    def always_fail(url, data, timeout, headers):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", always_fail)
    monkeypatch.setattr(overpass.time, "sleep", lambda s: None)
    ov = overpass.OverpassClient(cache_dir=tmp_path, max_retries=2)
    with pytest.raises(RuntimeError, match="Overpass"):
        ov.query("q")
