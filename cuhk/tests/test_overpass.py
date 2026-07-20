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


def test_use_cache_false_bypasses_read_and_write(tmp_path, monkeypatch):
    import json

    ql = "[out:json];node(42);out;"
    old_payload = {"version": 1}
    new_payload = {"version": 2}

    def fake_post_old(url, data, timeout, headers):
        return FakeResponse(old_payload)

    monkeypatch.setattr(requests, "post", fake_post_old)
    ov = overpass.OverpassClient(cache_dir=tmp_path)
    assert ov.query(ql) == old_payload

    def fake_post_new(url, data, timeout, headers):
        return FakeResponse(new_payload)

    monkeypatch.setattr(requests, "post", fake_post_new)
    result = ov.query(ql, use_cache=False)
    assert result == new_payload

    cached = json.loads(ov._cache_path(ql).read_text(encoding="utf-8"))
    assert cached == old_payload


def test_cache_key_includes_endpoint(tmp_path, monkeypatch):
    calls = []

    def fake_post(url, data, timeout, headers):
        calls.append(url)
        return FakeResponse({"endpoint": url})

    monkeypatch.setattr(requests, "post", fake_post)
    ov_a = overpass.OverpassClient(
        cache_dir=tmp_path, endpoint="https://a.test/api/interpreter"
    )
    ov_b = overpass.OverpassClient(
        cache_dir=tmp_path, endpoint="https://b.test/api/interpreter"
    )
    ql = "[out:json];node(1);out;"
    ov_a.query(ql)
    ov_b.query(ql)
    assert len(calls) == 2
    assert calls[0] == "https://a.test/api/interpreter"
    assert calls[1] == "https://b.test/api/interpreter"
