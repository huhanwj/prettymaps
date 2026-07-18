"""Overpass API 客户端：POST 查询、磁盘缓存、重试、端点可配。

端点优先级：构造参数 > 环境变量 CUHK_OVERPASS_URL > 默认 overpass-api.de。
注意：本机实测 Nominatim 不可达，正则全局查询会超时——查询一律带 bbox/ID。
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "cuhk-campus-map (github fork of marceloprates/prettymaps)"


class OverpassClient:
    def __init__(self, cache_dir, endpoint=None, max_retries=3, timeout=90):
        self.cache_dir = Path(cache_dir)
        (self.cache_dir / "overpass").mkdir(parents=True, exist_ok=True)
        self.endpoint = (
            endpoint
            or os.environ.get("CUHK_OVERPASS_URL")
            or DEFAULT_ENDPOINT
        )
        self.max_retries = max_retries
        self.timeout = timeout

    def _cache_path(self, ql):
        key = hashlib.sha1(ql.encode("utf-8")).hexdigest()
        return self.cache_dir / "overpass" / f"{key}.json"

    def query(self, ql, use_cache=True):
        """执行 Overpass QL 查询，返回解析后的 dict。失败重试 max_retries 次。"""
        cache_path = self._cache_path(ql)
        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    self.endpoint,
                    data={"data": ql},
                    timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                payload = resp.json()
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
                return payload
            except (requests.RequestException, ValueError) as e:
                last_err = e
                time.sleep(2 * attempt)
        raise RuntimeError(
            f"Overpass 查询失败（{self.max_retries} 次重试后）：{last_err}\n"
            f"可尝试设置环境变量 CUHK_OVERPASS_URL 切换镜像端点。"
        )
