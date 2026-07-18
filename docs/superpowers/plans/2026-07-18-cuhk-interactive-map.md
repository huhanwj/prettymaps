# CUHK 交互式网页地图 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个面向 CUHK 新生的交互式网页地图：prettymaps 插画风、中英双语 POI 标注+弹窗、等高线+山体阴影+3D 建筑表现山城高差，纯静态本地运行。

**Architecture:** 两段式。Python 数据管线（`cuhk/scripts/`）离线跑一次：Overpass 抓 OSM（relation 7802779 校园边界 +800m 缓冲）、S3 下载 SRTM 生成山体阴影与等高线、手工 pois.yml 解析坐标，产出 GeoJSON/PNG 到 `cuhk/site/data/`；前端（`cuhk/site/`）用本地 vendor 的 MapLibre GL JS 渲染，POI 用 HTML marker（浏览器字体，无需 glyph PBF）。

**Tech Stack:** Python 3.11（osmnx 2.0.7 / geopandas / shapely / numpy / matplotlib / scipy / pyyaml / pytest，**全部已装，零新依赖**）、MapLibre GL JS 4.7.1（vendor 本地）。

**已验证的外部依赖（2026-07-18 本机实测）：**
- ✅ `https://overpass-api.de/api/interpreter` 可达（正则全局查询会超时 → 一律用 relation ID + bbox + 精确名查询）
- ❌ Nominatim 被墙 → **禁止** `ox.geocode*`，边界用 Overpass 直查 `relation(7802779)`
- ✅ `https://s3.amazonaws.com/elevation-tiles-prod/skadi/N22/N22E114.hgt.gz` 返回 200
- ✅ jsdelivr 可达 → 一次性 vendor `maplibre-gl@4.7.1`
- CUHK 校园边界 = OSM relation **7802779**（outer 6 ways + inner 1 way，lon 114.1989–114.2149，lat 22.4118–22.4283）

**与 spec 的一处偏差（有意简化）：** spec §7 建筑高度回退"按类别默认值（书院 15m/教学 12m/其他 8m）"——OSM 没有可靠的楼宇类别标签，实现为 `height` 标签 → `building:levels × 3` → 默认 8m。视觉差异可忽略。

---

## 目录结构（最终形态）

```
cuhk/
├── README.md                      # 快速开始（任务 14）
├── data/
│   ├── pois.yml                   # 手工 POI 表（任务 8）
│   └── boundary_fallback.geojson  # 校园边界备份（任务 3，真实数据生成后提交）
├── cache/                         # gitignore：Overpass/osmnx/SRTM 缓存
├── scripts/
│   ├── build_data.py              # 管线编排入口（任务 10）
│   └── pipeline/
│       ├── __init__.py            # 空文件（任务 1）
│       ├── overpass.py            # Overpass 客户端：缓存/重试/可配端点（任务 2）
│       ├── boundary.py            # 边界抓取+组装+buffer（任务 3）
│       ├── layers.py              # OSM 图层抓取+道路分级+裁剪（任务 4）
│       ├── sea.py                 # 海面多边形（任务 5）
│       ├── elevation.py           # SRTM 下载/解析/hillshade/等高线（任务 6）
│       ├── heights.py             # 建筑高度估算（任务 7）
│       ├── pois.py                # pois.yml 解析+模糊匹配（任务 8）
│       └── validate.py            # 产出校验（任务 9）
├── site/
│   ├── index.html                 # 页面+CSS（任务 13）
│   ├── app.js                     # 地图初始化+marker+交互（任务 13）
│   ├── style.json                 # 矢量样式（任务 12）
│   ├── vendor/maplibre-gl.{js,css}# 任务 11
│   ├── data/                      # gitignore：管线产出
│   └── start.bat / start.sh       # 任务 14
└── tests/
    ├── conftest.py                # sys.path + 合成 fixtures（任务 1）
    ├── test_overpass.py           # 任务 2
    ├── test_boundary.py           # 任务 3
    ├── test_layers.py             # 任务 4
    ├── test_sea.py                # 任务 5
    ├── test_elevation.py          # 任务 6
    ├── test_heights.py            # 任务 7
    ├── test_pois.py               # 任务 8
    └── test_validate.py           # 任务 9
```

约定：所有命令在仓库根目录 `J:\work\prettymaps` 下执行；pytest 统一用 `python -m pytest cuhk/tests -v`。shell 命令按 **Git Bash** 写法；PowerShell 下设置环境变量的等价写法为 `$env:VAR='值'`（如 `$env:PYTHONPATH='cuhk/scripts'`）。

---

## 任务 1：项目脚手架

**Files:**
- Create: `cuhk/scripts/pipeline/__init__.py`
- Create: `cuhk/tests/conftest.py`
- Create: `cuhk/tests/test_scaffold.py`
- Modify: `.gitignore`

- [ ] **Step 1: 创建目录与空文件**

```bash
mkdir -p cuhk/scripts/pipeline cuhk/tests cuhk/data cuhk/cache cuhk/site/vendor cuhk/site/data cuhk/screenshots
```

创建空的 `cuhk/scripts/pipeline/__init__.py`（内容为空）。

- [ ] **Step 2: 更新 .gitignore**

在 `.gitignore` 末尾追加：

```gitignore

# CUHK project
cuhk/cache/
cuhk/site/data/
```

- [ ] **Step 3: 写 conftest.py（sys.path 引导 + 共享 fixtures）**

`cuhk/tests/conftest.py`：

```python
import pathlib
import sys

import pytest
from shapely.geometry import LineString, Polygon, box

# 让测试可以 import cuhk/scripts/pipeline 下的模块
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

HK_BBOX = (113.8, 22.1, 114.5, 22.6)  # (min_lon, min_lat, max_lon, max_lat)


@pytest.fixture
def campus_square():
    """合成'校园'多边形：约 1km 见方，位于 CUHK 真实位置。"""
    return box(114.200, 22.415, 114.210, 22.425)


@pytest.fixture
def synthetic_relation():
    """合成 Overpass relation JSON：两条 outer way 拼成正方形 + 一条 inner way 挖洞。"""
    def way(wid, coords, role):
        return {
            "type": "way",
            "id": wid,
            "role": role,
            "geometry": [{"lat": lat, "lon": lon} for lon, lat in coords],
        }

    outer1 = [(114.200, 22.415), (114.210, 22.415), (114.210, 22.425)]
    outer2 = [(114.210, 22.425), (114.200, 22.425), (114.200, 22.415)]
    inner = [(114.204, 22.419), (114.206, 22.419), (114.206, 22.421), (114.204, 22.421), (114.204, 22.419)]
    return {
        "elements": [
            {
                "type": "relation",
                "id": 7802779,
                "members": [
                    way(101, outer1, "outer"),
                    way(102, outer2, "outer"),
                    way(103, inner, "inner"),
                ],
            }
        ]
    }
```

- [ ] **Step 4: 写冒烟测试并运行通过**

`cuhk/tests/test_scaffold.py`：

```python
def test_pipeline_importable():
    import pipeline  # noqa: F401

def test_fixtures(campus_square, synthetic_relation):
    assert campus_square.area > 0
    assert synthetic_relation["elements"][0]["id"] == 7802779
```

Run: `python -m pytest cuhk/tests/test_scaffold.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/ .gitignore
git commit -m "cuhk: project scaffold (dirs, conftest, gitignore)"
```

---

## 任务 2：Overpass 客户端（overpass.py）

**Files:**
- Create: `cuhk/scripts/pipeline/overpass.py`
- Test: `cuhk/tests/test_overpass.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_overpass.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_overpass.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.overpass'`

- [ ] **Step 3: 实现 overpass.py**

`cuhk/scripts/pipeline/overpass.py`：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_overpass.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/overpass.py cuhk/tests/test_overpass.py
git commit -m "cuhk: Overpass client with cache/retry/configurable endpoint"
```

---

## 任务 3：校园边界（boundary.py）

**Files:**
- Create: `cuhk/scripts/pipeline/boundary.py`
- Create: `cuhk/data/boundary_fallback.geojson`（由 Step 5 生成后提交）
- Test: `cuhk/tests/test_boundary.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_boundary.py`：

```python
from pipeline import boundary


def test_assemble_multipolygon_with_hole(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    # 外正方形面积 0.01*0.01，内洞 0.002*0.002
    assert abs(geom.area - (0.01 * 0.01 - 0.002 * 0.002)) < 1e-12


def test_buffer_polygon_meters(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    buffered = boundary.buffer_polygon_meters(geom, 800)
    # buffer 后面积必须变大，且仍然合法
    assert buffered.area > geom.area
    assert buffered.is_valid
    # CRS 必须是经纬度
    assert abs(buffered.bounds[0] - 114.2) < 0.05
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_boundary.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.boundary'`

- [ ] **Step 3: 实现 boundary.py**

`cuhk/scripts/pipeline/boundary.py`：

```python
"""CUHK 校园边界：Overpass 直查 relation 7802779，组装多边形，米制 buffer。

Nominatim 在本机不可达，因此不用 osmnx geocoder；一律走 OverpassClient。
"""

import json
from pathlib import Path

import geopandas as gp
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

CUHK_RELATION_ID = 7802779
FALLBACK_PATH = Path(__file__).resolve().parents[2] / "data" / "boundary_fallback.geojson"


def assemble_multipolygon(relation):
    """把 Overpass `out geom` 的 relation JSON 组装成 shapely 多边形（含洞）。"""
    outers, inners = [], []
    for member in relation["members"]:
        if member["type"] != "way" or "geometry" not in member:
            continue
        coords = [(p["lon"], p["lat"]) for p in member["geometry"]]
        if member["role"] == "outer":
            outers.append(coords)
        elif member["role"] == "inner":
            inners.append(coords)

    outer_rings = list(polygonize(outers))
    if not outer_rings:
        raise ValueError("relation 的 outer ways 无法拼成闭合多边形")
    shell = unary_union(outer_rings)

    holes = []
    for ring in polygonize(inners):
        holes.append(list(ring.exterior.coords))

    # shell 可能是 Polygon 或 MultiPolygon；洞统一扣掉
    result = shell
    for hole in holes:
        result = result.difference(Polygon(hole))
    return result


def buffer_polygon_meters(geom, meters):
    """在投影坐标系（自动选 UTM）下 buffer，返回 EPSG:4326 多边形。"""
    gdf = gp.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
    projected = gdf.to_crs(gdf.estimate_utm_crs())
    projected["geometry"] = projected.geometry.buffer(meters)
    return projected.to_crs("EPSG:4326").geometry.iloc[0]


def fetch_campus_boundary(client, buffer_m=800):
    """主流程：Overpass 取 relation → 组装 → buffer → GeoDataFrame(4326)。
    失败时回退到 cuhk/data/boundary_fallback.geojson。"""
    ql = f"[out:json][timeout:60];relation({CUHK_RELATION_ID});out geom;"
    try:
        payload = client.query(ql)
        geom = assemble_multipolygon(payload["elements"][0])
    except Exception as e:
        if not FALLBACK_PATH.exists():
            raise RuntimeError(
                f"Overpass 取边界失败且无 fallback 文件：{e}"
            ) from e
        print(f"[boundary] Overpass 失败（{e}），使用 fallback 文件")
        return gp.read_file(FALLBACK_PATH)

    campus = gp.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
    if buffer_m:
        buffered = buffer_polygon_meters(geom, buffer_m)
        campus = gp.GeoDataFrame(geometry=[buffered], crs="EPSG:4326")
    return campus
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_boundary.py -v`
Expected: 2 passed

- [ ] **Step 5: 生成并提交 fallback 边界（真实数据）**

运行这段一次性脚本：

```bash
PYTHONPATH=cuhk/scripts python -c "
from pipeline.overpass import OverpassClient
from pipeline import boundary
client = OverpassClient(cache_dir='cuhk/cache')
campus = boundary.fetch_campus_boundary(client, buffer_m=0)
campus.to_file('cuhk/data/boundary_fallback.geojson', driver='GeoJSON')
print('fallback saved, bounds:', campus.total_bounds)
"
```

Expected: 打印 `fallback saved, bounds: [114.19... 22.41... 114.21... 22.42...]`
注意：fallback 保存**未 buffer** 的原始边界（buffer 在 fetch 时做）。

- [ ] **Step 6: Commit**

```bash
git add cuhk/scripts/pipeline/boundary.py cuhk/tests/test_boundary.py cuhk/data/boundary_fallback.geojson
git commit -m "cuhk: campus boundary fetch (relation 7802779) + fallback geojson"
```

---

## 任务 4：OSM 图层抓取（layers.py）

**Files:**
- Create: `cuhk/scripts/pipeline/layers.py`
- Test: `cuhk/tests/test_layers.py`

图层定义沿用 prettymaps `default.json` 的 tag 组合，新增步道/楼梯与铁路：

| layer | tags | 输出 class 规则 |
|---|---|---|
| buildings | `{"building": True}` | — |
| roads | `{"highway": True}` | 见 `classify_roads` |
| railway | `{"railway": ["rail", "light_rail"]}` | — |
| water | `{"natural": ["water", "bay"]}` | — |
| waterway | `{"waterway": ["river", "stream", "drain"]}` | — |
| forest | `{"landuse": "forest"}` | — |
| green | `{"landuse": ["grass", "orchard", "meadow"], "natural": ["wood", "wetland"], "leisure": ["garden", "golf_course", "park", "pitch", "sports_centre", "track"]}` | — |
| beach | `{"natural": "beach"}` | — |
| parking | `{"amenity": "parking"}` | — |

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_layers.py`：

```python
import geopandas as gp
import pandas as pd
from shapely.geometry import LineString, Point, Polygon, box

from pipeline import layers


def test_road_classification():
    gdf = gp.GeoDataFrame(
        {
            "highway": ["primary", "residential", "footway", "steps", "service", "path"],
            "geometry": [LineString([(0, 0), (1, 1)])] * 6,
        },
        crs="EPSG:4326",
    )
    out = layers.classify_roads(gdf)
    assert list(out["road_class"]) == [
        "major", "minor", "path", "steps", "minor", "path",
    ]


def test_clip_to_boundary():
    gdf = gp.GeoDataFrame(
        {"geometry": [box(0, 0, 2, 2), box(10, 10, 11, 11)]}, crs="EPSG:4326"
    )
    boundary = gp.GeoDataFrame({"geometry": [box(1, 1, 3, 3)]}, crs="EPSG:4326")
    out = layers.clip_to_boundary(gdf, boundary)
    assert len(out) == 1
    assert abs(out.geometry.iloc[0].area - 1.0) < 1e-9


def test_layer_tags_complete():
    for name, spec in layers.LAYER_TAGS.items():
        assert spec, f"{name} tags 为空"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_layers.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.layers'`

- [ ] **Step 3: 实现 layers.py**

`cuhk/scripts/pipeline/layers.py`：

```python
"""OSM 图层抓取：tag 组合（沿用 prettymaps default preset）+ 道路分级 + 边界裁剪。

osmnx 自带 HTTP 缓存，cache_folder 指到 cuhk/cache/osmnx，重复跑不重抓。
"""

import geopandas as gp
import osmnx as ox
import pandas as pd

ox.settings.use_cache = True
ox.settings.cache_folder = None  # 由 fetch_all_layers 按 cache_dir 设置

LAYER_TAGS = {
    "buildings": {"building": True},
    "roads": {"highway": True},
    "railway": {"railway": ["rail", "light_rail"]},
    "water": {"natural": ["water", "bay"]},
    "waterway": {"waterway": ["river", "stream", "drain"]},
    "forest": {"landuse": "forest"},
    "green": {
        "landuse": ["grass", "orchard", "meadow"],
        "natural": ["wood", "wetland"],
        "leisure": [
            "garden", "golf_course", "park", "pitch", "sports_centre", "track",
        ],
    },
    "beach": {"natural": "beach"},
    "parking": {"amenity": "parking"},
}

ROAD_CLASS = {
    "motorway": "major", "trunk": "major", "primary": "major",
    "secondary": "medium", "tertiary": "medium",
    "residential": "minor", "unclassified": "minor", "service": "minor",
    "living_street": "minor",
    "pedestrian": "path", "footway": "path", "path": "path",
    "track": "path", "cycleway": "path",
    "steps": "steps",
}


def classify_roads(gdf):
    """按 highway 标签给道路分级：major/medium/minor/path/steps。
    highway 列可能是 list（双向不同值），取第一个能匹配上的。"""
    def to_class(value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v in ROAD_CLASS:
                return ROAD_CLASS[v]
        return "minor"

    gdf = gdf.copy()
    gdf["road_class"] = gdf["highway"].map(to_class)
    return gdf


def clip_to_boundary(gdf, boundary_gdf):
    """要素与边界求交，丢掉空几何。"""
    if gdf.empty:
        return gdf
    boundary = boundary_gdf.geometry.union_all()
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.intersection(boundary)
    gdf = gdf[~gdf.geometry.is_empty]
    return gdf.reset_index(drop=True)


def fetch_all_layers(boundary_gdf, cache_dir):
    """抓取全部图层，返回 {layer_name: GeoDataFrame}（已裁剪到边界）。"""
    ox.settings.cache_folder = str(cache_dir / "osmnx")
    polygon = boundary_gdf.geometry.union_all()
    out = {}
    for name, tags in LAYER_TAGS.items():
        try:
            gdf = ox.features_from_polygon(polygon, tags=tags)
        except Exception as e:
            print(f"[layers] {name} 抓取失败：{e}")
            gdf = gp.GeoDataFrame(geometry=[], crs="EPSG:4326")
        # 只保留面（水/绿地）或线（道路/铁路/水道）或混合；osmnx 会混入点
        if name in ("roads", "railway", "waterway") and not gdf.empty:
            gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]
        elif not gdf.empty:
            gdf = gdf[
                gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon", "LineString"])
            ]
        if name == "roads" and not gdf.empty:
            gdf = classify_roads(gdf)
        out[name] = clip_to_boundary(gdf, boundary_gdf)
        print(f"[layers] {name}: {len(out[name])} 要素")
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_layers.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/layers.py cuhk/tests/test_layers.py
git commit -m "cuhk: OSM layer fetch + road classification + boundary clip"
```

---

## 任务 5：海面多边形（sea.py）

**Files:**
- Create: `cuhk/scripts/pipeline/sea.py`
- Test: `cuhk/tests/test_sea.py`

原理（移植自 prettymaps `fetch.py`）：bbox 矩形 减去 海岸线 buffer → 候选面 → 排除与车行道网相交的候选 → 剩下的就是海。CUHK 东临吐露港，海面必须出现。

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_sea.py`：

```python
import geopandas as gp
from shapely.geometry import LineString, box

from pipeline import sea


def test_sea_candidates_split_by_coastline():
    bbox = box(0, 0, 10, 10)
    # 一条南北向海岸线把 bbox 切成东西两半
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    assert len(candidates) == 2
    areas = sorted([g.area for g in candidates])
    assert abs(sum(areas) - 100) < 1.0  # buffer 极窄，总面积≈bbox


def test_filter_land_side_by_roads():
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    # 车行道路只在西半边（陆侧）
    roads = gp.GeoDataFrame(
        {"geometry": [LineString([(2, 2), (2, 8)])]}, crs="EPSG:4326"
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    # 东半边（不与道路相交）是海
    assert len(sea_gdf) == 1
    assert sea_gdf.geometry.iloc[0].bounds[0] > 5  # minx 在海岸线以东
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_sea.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.sea'`

- [ ] **Step 3: 实现 sea.py**

`cuhk/scripts/pipeline/sea.py`：

```python
"""海面多边形：bbox - 海岸线 → 候选面 → 排除与车行道相交的一侧。

移植自 prettymaps fetch.py 的 sea 逻辑（简化：不区分桥梁，车行网相交即陆侧）。
"""

import geopandas as gp
import osmnx as ox
from shapely.geometry import MultiPolygon, box
from shapely.ops import unary_union


def sea_candidates(bbox_polygon, coastline_gdf):
    """bbox 减海岸线 buffer，返回候选多边形列表。"""
    coastline = unary_union(list(coastline_gdf.geometry))
    diff = bbox_polygon.difference(coastline.buffer(1e-9))
    if diff.is_empty:
        return []
    if diff.geom_type == "Polygon":
        return [diff]
    return list(diff.geoms)


def pick_sea_side(candidates, roads_gdf, crs="EPSG:4326"):
    """排除与车行道路网相交的候选面，剩下的合并为海面 GeoDataFrame。"""
    sea_parts = [
        c for c in candidates if not roads_gdf.geometry.intersects(c).any()
    ]
    if not sea_parts:
        return gp.GeoDataFrame(geometry=[], crs=crs)
    merged = unary_union(MultiPolygon(sea_parts)).buffer(1e-8)
    return gp.GeoDataFrame(geometry=[merged], crs=crs)


def fetch_sea(boundary_gdf):
    """主流程：以边界的外接矩形为 bbox 抓海岸线和车行网，返回海面 gdf。"""
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    bbox_polygon = box(minx, miny, maxx, maxy)

    coastline = ox.features_from_polygon(bbox_polygon, tags={"natural": "coastline"})
    coastline = coastline[coastline.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    if coastline.empty:
        print("[sea] 范围内无海岸线，返回空海面")
        return gp.GeoDataFrame(geometry=[], crs="EPSG:4326")

    candidates = sea_candidates(bbox_polygon, coastline)
    graph = ox.graph_from_polygon(
        bbox_polygon, network_type="drive", truncate_by_edge=True
    )
    roads = ox.graph_to_gdfs(graph, nodes=False)
    sea_gdf = pick_sea_side(candidates, roads, crs="EPSG:4326")
    # 海面充满整个矩形画框（不止 buffer 内），交给前端直接展示
    print(f"[sea] 海面面积 {sea_gdf.to_crs(sea_gdf.estimate_utm_crs()).area.sum():.0f} m²")
    return sea_gdf
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_sea.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/sea.py cuhk/tests/test_sea.py
git commit -m "cuhk: sea polygon from coastline (ported from prettymaps)"
```

---

## 任务 6：高程模块（elevation.py）

**Files:**
- Create: `cuhk/scripts/pipeline/elevation.py`
- Test: `cuhk/tests/test_elevation.py`

SRTM 数据来源：`https://s3.amazonaws.com/elevation-tiles-prod/skadi/N22/N22E114.hgt.gz`（已实测可达）。`.hgt` 是裸 int16 大端栅格，numpy 直接读，**不需要 rasterio/elevation 包**。瓦片命名：`N22E114` = 西南角 (lat 22, lon 114)，覆盖 22–23°N / 114–115°E，第 0 行是北边缘。

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_elevation.py`：

```python
import numpy as np
import pytest

from pipeline import elevation


def test_tile_bounds():
    assert elevation.tile_bounds("N22E114") == (114.0, 22.0, 115.0, 23.0)


def test_read_hgt_roundtrip(tmp_path):
    dem = (np.arange(1201 * 1201) % 30000).astype(">i2").reshape(1201, 1201)
    path = tmp_path / "tile.hgt"
    dem.tofile(path)
    out = elevation.read_hgt(path)
    assert out.shape == (1201, 1201)
    assert out[0, 1] == 1


def test_read_hgt_rejects_bad_size(tmp_path):
    (tmp_path / "bad.hgt").write_bytes(b"\x00" * 100)
    with pytest.raises(ValueError, match="HGT"):
        elevation.read_hgt(tmp_path / "bad.hgt")


def test_fill_voids():
    dem = np.full((5, 5), 100.0)
    dem[2, 2] = np.nan
    filled = elevation.fill_voids(dem)
    assert filled[2, 2] == pytest.approx(100.0)


def test_contours_of_tilted_plane():
    # 沿 x 方向每度上升 1000m 的斜面 → 等高线是等间距竖直线
    lons = np.linspace(114.0, 114.1, 101)
    lats = np.linspace(22.0, 22.1, 101)
    dem = np.tile((lons - 114.0) * 10000, (101, 1))  # 0..1000m
    gdf = elevation.contour_lines(dem, lons, lats, interval=100)
    # 100..900m 必定出现（1000m 恰好在数据边缘，是否出线是实现细节，不断言）
    assert set(range(100, 1000, 100)) <= set(gdf["ele"])
    # 100m 等高线应在 lon≈114.01 附近且南北走向
    line = gdf[gdf["ele"] == 100].geometry.iloc[0]
    xs, ys = line.xy
    assert abs(np.mean(xs) - 114.01) < 0.002
    assert max(xs) - min(xs) < 0.002  # 竖直


def test_hillshade_rgba_shape():
    dem = np.random.default_rng(0).normal(100, 10, (50, 50))
    rgba = elevation.hillshade_rgba(dem, cellsize_m=30)
    assert rgba.shape == (50, 50, 4)
    assert rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # 有阴影
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_elevation.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.elevation'`

- [ ] **Step 3: 实现 elevation.py**

`cuhk/scripts/pipeline/elevation.py`：

```python
"""SRTM 高程：下载/解析 .hgt、山体阴影 PNG、等高线 GeoJSON。

无 rasterio 依赖：.hgt 用 numpy 读，hillshade 用 matplotlib LightSource，
等高线用 matplotlib contour（经纬度网格直接出地理坐标）。
"""

import gzip
import io
import json
import urllib.request
from pathlib import Path

import geopandas as gp
import matplotlib

matplotlib.use("Agg")  # 管线无界面运行
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter
from shapely.geometry import LineString

SKADI_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}/{tile}.hgt.gz"
TILE = "N22E114"  # CUHK 所在 SRTM 瓦片
VOID = -32768


def tile_bounds(tile):
    """'N22E114' -> (west, south, east, north)，瓦片覆盖 1°×1°。"""
    lat = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    lon = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    north = lat + 1 if lat >= 0 else lat
    south = north - 1
    east = lon + 1 if lon >= 0 else lon
    west = east - 1
    return (float(west), float(south), float(east), float(north))


def download_hgt(tile, dest_dir):
    """从 skadi S3 下载并解压 .hgt，返回本地路径。已存在则跳过。"""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{tile}.hgt"
    if out.exists():
        return out
    url = SKADI_URL.format(ns=tile[:3], tile=tile)
    print(f"[elevation] 下载 {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        payload = resp.read()
    out.write_bytes(gzip.decompress(payload))
    return out


def read_hgt(path):
    """读 .hgt 为 (n, n) float32 数组，第 0 行是北边缘。void 置 nan。"""
    raw = np.fromfile(path, dtype=">i2")
    n = int(round(np.sqrt(raw.size)))
    if n * n != raw.size or n not in (1201, 3601):
        raise ValueError(f"非法 HGT 文件大小：{path} ({raw.size} cells)")
    dem = raw.reshape(n, n).astype(np.float32)
    dem[dem == VOID] = np.nan
    return dem


def fill_voids(dem):
    """nan 用全局均值填充（SRTM 水域常为 void/0，CUHK 山地无大空洞）。"""
    if not np.isnan(dem).any():
        return dem
    fill = np.nanmean(dem)
    return np.where(np.isnan(dem), fill, dem)


def crop_to_bounds(dem, tile, west, south, east, north):
    """把整瓦片裁到目标范围，返回 (dem_crop, lons, lats)（1° 瓦片内）。"""
    tw, ts, te, tn = tile_bounds(tile)
    n = dem.shape[0]
    col = lambda lon: int(round((lon - tw) / (te - tw) * (n - 1)))
    row = lambda lat: int(round((tn - lat) / (tn - ts) * (n - 1)))
    c0, c1 = sorted((col(west), col(east)))
    r0, r1 = sorted((row(north), row(south)))
    c0, r0 = max(c0, 0), max(r0, 0)
    c1, r1 = min(c1, n - 1), min(r1, n - 1)
    lons = np.linspace(tw + c0 / (n - 1), tw + c1 / (n - 1), c1 - c0 + 1)
    lats = np.linspace(tn - r0 / (n - 1), tn - r1 / (n - 1), r1 - r0 + 1)
    return dem[r0 : r1 + 1, c0 : c1 + 1], lons, lats


def cellsize_m(lons, lats):
    """经纬度步长换算成米（等距圆柱近似）。"""
    mean_lat = np.deg2rad(np.mean(lats))
    dx = np.abs(lons[1] - lons[0]) * 111320 * np.cos(mean_lat)
    dy = np.abs(lats[1] - lats[0]) * 110540
    return dx, dy


def hillshade_rgba(dem, cellsize_m=30, azdeg=315, altdeg=45, vert_exag=1.5):
    """山体阴影 → RGBA：黑色阴影，alpha 随坡度阴影增强（海面已被置 0 → 无阴影）。"""
    ls = LightSource(azdeg=azdeg, altdeg=altdeg)
    shade = ls.hillshade(dem, vert_exag=vert_exag, dx=cellsize_m, dy=cellsize_m)
    rgba = np.zeros((*shade.shape, 4), dtype=np.uint8)
    rgba[..., 3] = ((1 - shade) * 255 * 0.85).astype(np.uint8)
    return rgba


def contour_lines(dem, lons, lats, interval=10, min_ele=None):
    """等高线 → GeoDataFrame(LineString, 属性 ele)。经纬度网格直接出地理坐标。"""
    lo = float(np.nanmin(dem))
    hi = float(np.nanmax(dem))
    start = max(interval, int(np.ceil(lo / interval)) * interval)
    if min_ele is not None:
        start = max(start, min_ele)
    levels = list(range(int(start), int(hi) + 1, interval))
    X, Y = np.meshgrid(lons, lats)
    cs = plt.contour(X, Y, dem, levels=levels)
    rows = []
    for level, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            if len(seg) >= 2:
                rows.append({"ele": int(level), "geometry": LineString(seg)})
    plt.close("all")
    return gp.GeoDataFrame(rows, crs="EPSG:4326")


def build_elevation_products(boundary_gdf, cache_dir, out_dir, interval=10):
    """主流程：下载瓦片 → 裁剪到边界 bbox(含 5% 余量) → 填洞/平滑 →
    写出 hillshade.png + hillshade.json（四角坐标）+ contours.geojson。"""
    hgt = download_hgt(TILE, Path(cache_dir) / "srtm")
    dem = read_hgt(hgt)

    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    dem, lons, lats = crop_to_bounds(
        dem, TILE, minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y
    )
    dem = fill_voids(dem)
    dem = np.clip(dem, 0, None)  # 海面置 0
    dem = gaussian_filter(dem, sigma=2)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgba = hillshade_rgba(dem, cellsize_m=cellsize_m(lons, lats)[0])
    plt.imsave(out_dir / "hillshade.png", rgba)
    coords = [
        [float(lons[0]), float(lats[0])],   # NW
        [float(lons[-1]), float(lats[0])],  # NE
        [float(lons[-1]), float(lats[-1])], # SE
        [float(lons[0]), float(lats[-1])],  # SW
    ]
    (out_dir / "hillshade.json").write_text(
        json.dumps({"coordinates": coords}), encoding="utf-8"
    )

    contours = contour_lines(dem, lons, lats, interval=interval, min_ele=10)
    contours.to_file(out_dir / "contours.geojson", driver="GeoJSON")
    print(f"[elevation] hillshade {rgba.shape[:2]}, 等高线 {len(contours)} 条")
    return contours
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_elevation.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/elevation.py cuhk/tests/test_elevation.py
git commit -m "cuhk: SRTM download/parse, hillshade PNG, contour GeoJSON"
```

---

## 任务 7：建筑高度估算（heights.py）

**Files:**
- Create: `cuhk/scripts/pipeline/heights.py`
- Test: `cuhk/tests/test_heights.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_heights.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_heights.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.heights'`

- [ ] **Step 3: 实现 heights.py**

`cuhk/scripts/pipeline/heights.py`：

```python
"""建筑高度估算：height 标签 → building:levels × 3 → 默认 8m。

（spec 原本按楼宇类别给默认值；OSM 无可靠类别标签，简化为统一 8m。）
"""

import re

DEFAULT_HEIGHT = 8.0
METERS_PER_LEVEL = 3.0


def _parse_number(value):
    """从 '15' / '12.5 m' / '12,5' 中提取数字；失败返回 None。"""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", str(value))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def estimate_height(row):
    """单行建筑的高度（米）。优先级：height 标签 > levels×3 > 默认。"""
    h = _parse_number(row.get("height"))
    if h is not None and 1 <= h <= 300:
        return h
    levels = _parse_number(row.get("building:levels"))
    if levels is not None and 0 < levels <= 100:
        return levels * METERS_PER_LEVEL
    return DEFAULT_HEIGHT


def add_heights(buildings_gdf):
    """给建筑图层加两列：h（高度）和 c（0/1 交替配色索引，用于红/棕撞色）。"""
    gdf = buildings_gdf.copy()
    gdf["h"] = gdf.apply(estimate_height, axis=1)
    gdf["c"] = range(len(gdf))
    gdf["c"] = gdf["c"] % 2
    return gdf
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_heights.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/heights.py cuhk/tests/test_heights.py
git commit -m "cuhk: building height estimation + alternating color index"
```

---

## 任务 8：POI 模块（pois.py + pois.yml）

**Files:**
- Create: `cuhk/scripts/pipeline/pois.py`
- Create: `cuhk/data/pois.yml`
- Test: `cuhk/tests/test_pois.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_pois.py`：

```python
import geopandas as gp
import pytest
from shapely.geometry import Point, Polygon, box

from pipeline import pois


@pytest.fixture
def features():
    return gp.GeoDataFrame(
        {
            "name": ["University Library", None, "New Asia College"],
            "name:en": ["University Library", None, "New Asia College"],
            "name:zh": ["大學圖書館", None, "新亞書院"],
            "geometry": [
                box(114.2070, 22.4195, 114.2080, 22.4205),
                box(114.2000, 22.4100, 114.2010, 22.4110),
                box(114.2090, 22.4210, 114.2100, 22.4220),
            ],
        },
        crs="EPSG:4326",
    )


def test_load_pois_validates_schema(tmp_path):
    yml = tmp_path / "pois.yml"
    yml.write_text(
        "pois:\n  - id: x\n    name_zh: 测试\n    name_en: Test\n"
        "    category: study\n    desc: d\n    lon: 114.2\n    lat: 22.4\n",
        encoding="utf-8",
    )
    entries = pois.load_pois(yml)
    assert entries[0]["id"] == "x"

    bad = tmp_path / "bad.yml"
    bad.write_text("pois:\n  - id: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="字段"):
        pois.load_pois(bad)


def test_resolve_lonlat_passthrough(features):
    entries = [
        {"id": "dot", "name_zh": "点", "name_en": "Dot", "category": "landmark",
         "desc": "", "lon": 114.205, "lat": 22.418}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features)
    assert len(gdf) == 1 and unmatched == []
    assert gdf.geometry.iloc[0].x == pytest.approx(114.205)


def test_resolve_fuzzy_match_zh(features):
    entries = [
        {"id": "na", "name_zh": "新亚书院", "name_en": "New Asia College",
         "category": "life", "desc": "", "osm_name": "New Asia College"}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features)
    assert unmatched == []
    # 匹配到新亚书院要素的质心
    assert gdf.geometry.iloc[0].x == pytest.approx(114.2095)


def test_unmatched_reported(features):
    entries = [
        {"id": "ghost", "name_zh": "不存在", "name_en": "Ghost Place",
         "category": "study", "desc": "", "osm_name": "Zzz Nonexistent Qqq"}
    ]
    _, unmatched = pois.resolve_pois(entries, features)
    assert unmatched == ["ghost"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_pois.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.pois'`

- [ ] **Step 3: 实现 pois.py**

`cuhk/scripts/pipeline/pois.py`：

```python
"""POI 解析：pois.yml → pois.geojson。

定位二选一：lon/lat 直接给点；osm_name 与抓取的命名要素做模糊匹配取质心。
匹配失败的条目全量报错（不静默丢弃）。
"""

import difflib

import geopandas as gp
import osmnx as ox
import pandas as pd
import yaml
from shapely.geometry import Point

REQUIRED_FIELDS = {"id", "name_zh", "name_en", "category", "desc"}
CATEGORIES = {"study", "life", "sports", "transport", "landmark"}
MATCH_THRESHOLD = 0.55

NAME_TAGS = {
    "amenity": True, "building": True, "leisure": True, "tourism": True,
    "railway": True, "shop": True, "office": True, "historic": True,
    "man_made": True, "natural": True,
}


def load_pois(path):
    """加载并校验 pois.yml，返回条目列表。"""
    with open(path, encoding="utf-8") as f:
        entries = yaml.safe_load(f)["pois"]
    ids = set()
    for e in entries:
        missing = REQUIRED_FIELDS - set(e)
        if missing:
            raise ValueError(f"POI {e.get('id', '?')} 缺字段：{missing}")
        if e["category"] not in CATEGORIES:
            raise ValueError(f"POI {e['id']} 类别非法：{e['category']}")
        if not (("lon" in e and "lat" in e) or "osm_name" in e):
            raise ValueError(f"POI {e['id']} 必须给 lon/lat 或 osm_name")
        if e["id"] in ids:
            raise ValueError(f"POI id 重复：{e['id']}")
        ids.add(e["id"])
    return entries


def fetch_named_features(boundary_gdf):
    """抓边界内所有带名字的要素（一次大请求，osmnx 缓存）。"""
    polygon = boundary_gdf.geometry.union_all()
    gdf = ox.features_from_polygon(polygon, tags=NAME_TAGS)
    if gdf.empty:
        return gdf
    has_name = pd.Series(False, index=gdf.index)
    for col in ("name", "name:en", "name:zh"):
        if col in gdf.columns:
            has_name |= gdf[col].notna()
    return gdf[has_name]


def _similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _match_feature(osm_name, features):
    """在要素的 name/name:en/name:zh 中找最佳匹配，返回 (row, score)。"""
    best_row, best_score = None, 0.0
    for _, row in features.iterrows():
        candidates = [
            str(row[c]) for c in ("name", "name:en", "name:zh")
            if c in row and pd.notna(row[c])
        ]
        score = max((_similarity(osm_name, c) for c in candidates), default=0.0)
        if score > best_score:
            best_row, best_score = row, score
    return best_row, best_score


def resolve_pois(entries, features):
    """条目 → 点要素。返回 (GeoDataFrame, unmatched_id_list)。"""
    rows, unmatched = [], []
    for e in entries:
        if "lon" in e and "lat" in e:
            point = Point(e["lon"], e["lat"])
        else:
            row, score = _match_feature(e["osm_name"], features)
            if row is None or score < MATCH_THRESHOLD:
                unmatched.append(e["id"])
                continue
            point = row.geometry.representative_point()
        rows.append({
            "id": e["id"],
            "name_zh": e["name_zh"],
            "name_en": e["name_en"],
            "category": e["category"],
            "desc": e["desc"],
            "geometry": point,
        })
    return gp.GeoDataFrame(rows, crs="EPSG:4326"), unmatched
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_pois.py -v`
Expected: 4 passed

- [ ] **Step 5: 编写 pois.yml（42 条初始数据）**

`cuhk/data/pois.yml`（osm_name 为最佳猜测，Step 6 会用真实数据核对修正）：

```yaml
# CUHK 迎新地图 POI 表
# 定位：osm_name（与 OSM 要素模糊匹配）或 lon/lat 直接给坐标，二选一
# category: study 学习 / life 生活 / sports 体育 / transport 交通 / landmark 地标
pois:
  # ===== 书院（life） =====
  - {id: chung-chi,    name_zh: 崇基学院,   name_en: Chung Chi College,    category: life, desc: 1951年创校，历史最悠久的成员书院，未圆湖所在地。, osm_name: Chung Chi College}
  - {id: new-asia,     name_zh: 新亚书院,   name_en: New Asia College,     category: life, desc: 1949年创立，以弘扬中国文化为宗旨，"天人合一"所在地。, osm_name: New Asia College}
  - {id: united,       name_zh: 联合书院,   name_en: United College,       category: life, desc: 1956年由五家书院合并组成，坐拥吐露港景致。, osm_name: United College}
  - {id: shaw,         name_zh: 逸夫书院,   name_en: Shaw College,         category: life, desc: 1986年创立，位于校园西北部的山坡上。, osm_name: Shaw College}
  - {id: morningside,  name_zh: 晨兴书院,   name_en: Morningside College,  category: life, desc: 2006年创立的全宿制书院。, osm_name: Morningside College}
  - {id: sh-ho,        name_zh: 善衡书院,   name_en: S.H. Ho College,      category: life, desc: 2006年创立，以"家"为理念的全宿制书院。, osm_name: S.H. Ho College}
  - {id: cw-chu,       name_zh: 敬文书院,   name_en: C.W. Chu College,     category: life, desc: 2007年创立的小型全宿共膳书院。, osm_name: C.W. Chu College}
  - {id: wu-yee-sun,   name_zh: 伍宜孙书院, name_en: Wu Yee Sun College,   category: life, desc: 2007年创立，邻近大学站与科学园。, osm_name: Wu Yee Sun College}
  - {id: lee-woo-sing, name_zh: 和声书院,   name_en: Lee Woo Sing College, category: life, desc: 2007年创立，位于校园北部山坡。, osm_name: Lee Woo Sing College}
  # ===== 学习（study） =====
  - {id: ul,           name_zh: 大学图书馆, name_en: University Library,   category: study, desc: 中大总图书馆，百万大道旁的学术地标。, osm_name: University Library}
  - {id: moore-lib,    name_zh: 牟路思怡图书馆, name_en: Elisabeth Luce Moore Library, category: study, desc: 崇基学院图书馆。, osm_name: Elisabeth Luce Moore Library}
  - {id: chien-mu-lib, name_zh: 钱穆图书馆, name_en: Ch'ien Mu Library,    category: study, desc: 新亚书院图书馆，以创校校长命名。, osm_name: Ch'ien Mu Library}
  - {id: wu-chung-lib, name_zh: 胡忠图书馆, name_en: Wu Chung Library,     category: study, desc: 联合书院多媒体图书馆。, osm_name: Wu Chung Library}
  - {id: yia,          name_zh: 李兆基楼,   name_en: Yasumoto International Academic Park, category: study, desc: 中央校园主要教学楼之一，国际学术园。, osm_name: Yasumoto International Academic Park}
  - {id: cyt,          name_zh: 郑裕彤楼,   name_en: Cheng Yu Tung Building, category: study, desc: 商学院教学楼，俯瞰大学站。, osm_name: Cheng Yu Tung Building}
  - {id: shb,          name_zh: 何善衡工程学大楼, name_en: Ho Sin Hang Engineering Building, category: study, desc: 工程学院主楼。, osm_name: Ho Sin Hang Engineering Building}
  - {id: science-centre, name_zh: 科学馆,   name_en: Science Centre,       category: study, desc: 理学院教学与实验大楼。, osm_name: Science Centre}
  - {id: mmw,          name_zh: 蒙民伟楼,   name_en: William M.W. Mong Engineering Building, category: study, desc: 工程学院大楼，邻近大学站。, osm_name: William M.W. Mong Engineering Building}
  - {id: elb,          name_zh: 伍何曼原楼, name_en: Esther Lee Building,  category: study, desc: 中央校园综合教学楼。, osm_name: Esther Lee Building}
  - {id: fkh,          name_zh: 冯景禧楼,   name_en: Fung King Hey Building, category: study, desc: 位于大学道的教学楼。, osm_name: Fung King Hey Building}
  - {id: lsk,          name_zh: 梁銶琚楼,   name_en: Leung Kau Kui Building, category: study, desc: 中央校园教学楼。, osm_name: Leung Kau Kui Building}
  # ===== 餐饮/生活（life） =====
  - {id: franklin,     name_zh: 范克廉楼,   name_en: Benjamin Franklin Centre, category: life, desc: 学生活动中心，餐厅与泳池所在地。, osm_name: Benjamin Franklin Centre}
  - {id: orchid-lodge, name_zh: 兰苑,       name_en: Orchid Lodge,         category: life, desc: 崇基校园内的中式餐厅。, osm_name: Orchid Lodge}
  - {id: cc-canteen,   name_zh: 众志堂,     name_en: Chung Chi College Canteen, category: life, desc: 崇基学生膳堂。, osm_name: Chung Chi College Canteen}
  - {id: na-canteen,   name_zh: 新亚学生膳堂, name_en: New Asia College Canteen, category: life, desc: 新亚书院餐厅。, osm_name: New Asia College Canteen}
  - {id: uc-canteen,   name_zh: 联合学生膳堂, name_en: United College Canteen, category: life, desc: 联合书院餐厅。, osm_name: United College Canteen}
  # ===== 体育（sports） =====
  - {id: sports-centre, name_zh: 大学体育中心, name_en: University Sports Centre, category: sports, desc: 室内体育馆与健身设施。, osm_name: University Sports Centre}
  - {id: haddon-cave,  name_zh: 夏鼎基运动场, name_en: Sir Philip Haddon-Cave Sports Field, category: sports, desc: 临海田径运动场。, osm_name: Sir Philip Haddon-Cave Sports Field}
  - {id: swimming-pool, name_zh: 大学游泳池, name_en: University Swimming Pool, category: sports, desc: 范克廉楼旁的室外泳池。, osm_name: University Swimming Pool}
  # ===== 交通（transport） =====
  - {id: university-station, name_zh: 港铁大学站, name_en: University Station, category: transport, desc: 东铁线车站，进出校园的门户。, osm_name: University}
  - {id: bus-terminus, name_zh: 大学站巴士总站, name_en: University Station Bus Terminus, category: transport, desc: 校外巴士与专线小巴总站。, osm_name: University Station Bus Terminus}
  - {id: shuttle-central, name_zh: 校巴站（本部）, name_en: Central Avenue Shuttle Stop, category: transport, desc: 校内穿梭巴士主要站点。, lon: 114.2072, lat: 22.4197}
  # ===== 地标（landmark） =====
  - {id: harmony,      name_zh: 天人合一,   name_en: Pavilion of Harmony,  category: landmark, desc: 新亚书院标志性景点，海天一色的打卡圣地。, osm_name: Pavilion of Harmony}
  - {id: mall,         name_zh: 百万大道,   name_en: University Mall,      category: landmark, desc: 贯穿中央校园的大道，毕业照必拍地。, osm_name: University Mall}
  - {id: beacon,       name_zh: 烽火台,     name_en: The Beacon,           category: landmark, desc: 大学道上的雕塑地标，俗称"仲门"。, osm_name: The Beacon}
  - {id: uadmin,       name_zh: 大学行政楼, name_en: University Administration Building, category: landmark, desc: 中央校园行政中枢。, osm_name: University Administration Building}
  - {id: chapel,       name_zh: 崇基学院礼拜堂, name_en: Chung Chi College Chapel, category: landmark, desc: 崇基校园的礼拜堂与钟楼。, osm_name: Chung Chi College Chapel}
  - {id: shaw-hall,    name_zh: 邵逸夫堂,   name_en: Sir Run Run Shaw Hall, category: landmark, desc: 大学礼堂，大型典礼与演出场地。, osm_name: Sir Run Run Shaw Hall}
  - {id: lake,         name_zh: 未圆湖,     name_en: Lake Ad Excellentiam, category: landmark, desc: 崇基校园的湖泊，"未圆"寓意学无止境。, osm_name: Lake Ad Excellentiam}
  - {id: pier,         name_zh: 马料水码头, name_en: Ma Liu Shui Pier,     category: transport, desc: 通往塔门等离岛的渡轮码头。, osm_name: Ma Liu Shui Pier}
  - {id: science-park, name_zh: 香港科学园, name_en: Hong Kong Science Park, category: landmark, desc: 校园北侧的创科园区，实习机会集中地。, osm_name: Hong Kong Science Park}
  - {id: promenade,    name_zh: 白石角海滨长廊, name_en: Pak Shek Kok Promenade, category: landmark, desc: 吐露港海滨散步与骑行路线。, osm_name: Pak Shek Kok Promenade}
```

- [ ] **Step 6: 用真实数据核对 osm_name**

先跑一次命名要素转储（一条命令）：

```bash
PYTHONPATH=cuhk/scripts python -c "
import geopandas as gp
from pipeline import pois
b = gp.read_file('cuhk/data/boundary_fallback.geojson')
from pipeline import boundary
b = gp.GeoDataFrame(geometry=[boundary.buffer_polygon_meters(b.geometry.iloc[0], 800)], crs='EPSG:4326')
f = pois.fetch_named_features(b)
cols = [c for c in ('name','name:en','name:zh') if c in f.columns]
f[cols].drop_duplicates().to_csv('cuhk/cache/names_dump.csv', index=False)
print(len(f), 'named features -> cuhk/cache/names_dump.csv')
"
```

打开 `cuhk/cache/names_dump.csv`，逐条核对 pois.yml 的 `osm_name` 是否在真实数据中存在（或近似存在）：
- 拼写不一致 → 把 `osm_name` 改成数据里的真实写法（如 `University` → `University Station`）
- 要素根本没有名字（校巴站、部分食堂很可能如此）→ 从转储里找附近要素估算坐标，改用 `lon`/`lat`

再跑解析自检（应输出 unmatched 为空）：

```bash
PYTHONPATH=cuhk/scripts python -c "
import geopandas as gp
from pipeline import pois, boundary
b = gp.read_file('cuhk/data/boundary_fallback.geojson')
b = gp.GeoDataFrame(geometry=[boundary.buffer_polygon_meters(b.geometry.iloc[0], 800)], crs='EPSG:4326')
f = pois.fetch_named_features(b)
entries = pois.load_pois('cuhk/data/pois.yml')
gdf, unmatched = pois.resolve_pois(entries, f)
print('resolved:', len(gdf), 'unmatched:', unmatched)
assert not unmatched, unmatched
"
```

反复修正直到 unmatched 为空。

- [ ] **Step 7: Commit**

```bash
git add cuhk/scripts/pipeline/pois.py cuhk/tests/test_pois.py cuhk/data/pois.yml
git commit -m "cuhk: POI module + 42 curated bilingual POIs"
```

---

## 任务 9：产出校验（validate.py）

**Files:**
- Create: `cuhk/scripts/pipeline/validate.py`
- Test: `cuhk/tests/test_validate.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_validate.py`：

```python
import geopandas as gp
import pytest
from shapely.geometry import LineString, Point, box

from pipeline import validate


def good_gdfs():
    g = lambda geoms: gp.GeoDataFrame({"geometry": geoms}, crs="EPSG:4326")
    return {
        "buildings": g([box(114.20, 22.41, 114.201, 22.411)] * 301),
        "roads": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 51),
        "green": g([box(114.20, 22.41, 114.202, 22.412)] * 21),
        "railway": g([LineString([(114.2, 22.41), (114.21, 22.42)])]),
        "sea": g([box(114.22, 22.41, 114.23, 22.42)]),
        "contours": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 6),
    }


def good_pois():
    return gp.GeoDataFrame(
        {"geometry": [Point(114.2, 22.41)] * 31}, crs="EPSG:4326"
    )


def test_valid_passes():
    report = validate.validate(good_gdfs(), good_pois())
    assert any("OK" in line for line in report)


def test_empty_buildings_fails():
    gdfs = good_gdfs()
    gdfs["buildings"] = gdfs["buildings"].iloc[:0]
    with pytest.raises(RuntimeError, match="buildings"):
        validate.validate(gdfs, good_pois())


def test_out_of_hk_fails():
    gdfs = good_gdfs()
    gdfs["sea"] = gp.GeoDataFrame(
        {"geometry": [box(10.0, 10.0, 11.0, 11.0)]}, crs="EPSG:4326"
    )
    with pytest.raises(RuntimeError, match="香港"):
        validate.validate(gdfs, good_pois())


def test_too_few_pois_fails():
    with pytest.raises(RuntimeError, match="POI"):
        validate.validate(good_gdfs(), good_pois().iloc[:5])
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_validate.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.validate'`

- [ ] **Step 3: 实现 validate.py**

`cuhk/scripts/pipeline/validate.py`：

```python
"""管线产出校验：图层数量下限、香港范围检查、POI 数量下限。

失败即 raise（build 中止），报告行同时返回供打印。
"""

HK_BBOX = (113.8, 22.1, 114.5, 22.6)  # (min_lon, min_lat, max_lon, max_lat)

REQUIRED_MIN = {
    "buildings": 300,
    "roads": 50,
    "green": 20,
    "railway": 1,
    "sea": 1,
    "contours": 5,
}
MIN_POIS = 30


def _check_bounds(name, gdf, problems):
    if gdf.empty:
        return
    minx, miny, maxx, maxy = gdf.total_bounds
    lon0, lat0, lon1, lat1 = HK_BBOX
    if not (lon0 <= minx and maxx <= lon1 and lat0 <= miny and maxy <= lat1):
        problems.append(f"{name} 范围越出香港：{gdf.total_bounds}")


def validate(gdfs, pois_gdf):
    """gdfs: {layer: GeoDataFrame}；pois_gdf: GeoDataFrame。返回报告行列表。"""
    problems, report = [], []

    for layer, min_count in REQUIRED_MIN.items():
        gdf = gdfs.get(layer)
        n = 0 if gdf is None else len(gdf)
        if n < min_count:
            problems.append(f"{layer} 只有 {n} 个要素（要求 ≥{min_count}）")
        else:
            report.append(f"OK {layer}: {n} 个要素")

    for name, gdf in gdfs.items():
        if gdf is not None:
            _check_bounds(name, gdf, problems)

    if len(pois_gdf) < MIN_POIS:
        problems.append(f"POI 只有 {len(pois_gdf)} 条（要求 ≥{MIN_POIS}）")
    else:
        report.append(f"OK POI: {len(pois_gdf)} 条")

    if problems:
        raise RuntimeError("校验失败：\n" + "\n".join(problems))
    report.append("全部校验通过")
    return report
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_validate.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/validate.py cuhk/tests/test_validate.py
git commit -m "cuhk: output validation (counts, HK bounds, POI minimum)"
```

---

## 任务 10：管线编排（build_data.py）+ 真实运行

**Files:**
- Create: `cuhk/scripts/build_data.py`

- [ ] **Step 1: 实现 build_data.py**

`cuhk/scripts/build_data.py`：

```python
"""CUHK 地图数据管线编排。

用法：python cuhk/scripts/build_data.py [--out cuhk/site/data] [--allow-unmatched]
跑一次产出全部前端数据；OSM/SRTM 缓存于 cuhk/cache，重复跑很快。
"""

import argparse
import sys
from pathlib import Path

import geopandas as gp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import (  # noqa: E402
    boundary,
    elevation,
    heights,
    layers,
    pois,
    sea,
    validate,
)
from pipeline.overpass import OverpassClient  # noqa: E402

REPO_CUHK = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="CUHK 地图数据管线")
    parser.add_argument("--out", default=str(REPO_CUHK / "site" / "data"))
    parser.add_argument("--cache", default=str(REPO_CUHK / "cache"))
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help="POI 匹配失败仅警告不中止（调试用）",
    )
    args = parser.parse_args()

    out_dir, cache_dir = Path(args.out), Path(args.cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OverpassClient(cache_dir=cache_dir)

    # ① 边界（校园 + 800m 缓冲）
    print("== ① 边界 ==")
    campus = boundary.fetch_campus_boundary(client, buffer_m=800)
    campus.to_file(out_dir / "boundary.geojson", driver="GeoJSON")

    # ② 图层
    print("== ② OSM 图层 ==")
    gdfs = layers.fetch_all_layers(campus, cache_dir)

    # ③ 海面
    print("== ③ 海面 ==")
    gdfs["sea"] = sea.fetch_sea(campus)

    # ④ 高程（hillshade + 等高线）
    print("== ④ 高程 ==")
    gdfs["contours"] = elevation.build_elevation_products(
        campus, cache_dir, out_dir, interval=10
    )

    # ⑤ 建筑高度 + 配色索引
    gdfs["buildings"] = heights.add_heights(gdfs["buildings"])

    # ⑥ POI
    print("== ⑥ POI ==")
    entries = pois.load_pois(REPO_CUHK / "data" / "pois.yml")
    features = pois.fetch_named_features(campus)
    pois_gdf, unmatched = pois.resolve_pois(entries, features)
    if unmatched:
        msg = f"以下 POI 未匹配到 OSM 要素：{unmatched}（核对 pois.yml 的 osm_name 或改 lon/lat）"
        if args.allow_unmatched:
            print("WARNING:", msg)
        else:
            raise SystemExit(msg)

    # ⑦ 校验
    print("== ⑦ 校验 ==")
    for line in validate.validate(gdfs, pois_gdf):
        print(" ", line)

    # ⑧ 写出（所有图层都要落盘——style.json 静态引用全部 12 个文件，
    #    空图层写成空 FeatureCollection，避免前端 404）
    print("== ⑧ 写出 ==")
    import json

    keep = {
        "buildings": ["h", "c", "geometry"],
        "roads": ["road_class", "geometry"],
        "railway": ["geometry"],
        "water": ["geometry"],
        "waterway": ["geometry"],
        "forest": ["geometry"],
        "green": ["geometry"],
        "beach": ["geometry"],
        "parking": ["geometry"],
        "sea": ["geometry"],
        "contours": ["ele", "geometry"],
    }
    EMPTY_FC = {"type": "FeatureCollection", "features": []}
    for name, cols in keep.items():
        gdf = gdfs.get(name)
        path = out_dir / f"{name}.geojson"
        if gdf is None or gdf.empty:
            path.write_text(json.dumps(EMPTY_FC), encoding="utf-8")
            print(f"  {name}.geojson: 空图层")
            continue
        existing = [c for c in cols if c in gdf.columns or c == "geometry"]
        gdf[existing].to_file(path, driver="GeoJSON")
        print(f"  {name}.geojson: {len(gdf)} 要素")
    pois_gdf.to_file(out_dir / "pois.geojson", driver="GeoJSON")
    print(f"  pois.geojson: {len(pois_gdf)} 条")
    print(f"完成 → {out_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 全量测试套件回归**

Run: `python -m pytest cuhk/tests -v`
Expected: 全部 passed（累计约 22 个测试）

- [ ] **Step 3: 真实运行管线（需要网络，约 3–10 分钟）**

Run: `python cuhk/scripts/build_data.py`
Expected:
- `== ⑦ 校验 ==` 全部 OK
- `cuhk/site/data/` 下生成 boundary/buildings/roads/railway/water/waterway/forest/green/beach/parking/sea/contours/pois 共 12 个 geojson + hillshade.png + hillshade.json
- 若 POI 有 unmatched：按任务 8 Step 6 的流程修正 yml 后重跑（缓存使重跑很快）

注意：若 Overpass 偶发超时，直接重跑（客户端有重试+缓存）。若反复失败，设镜像后重试：`$env:CUHK_OVERPASS_URL="https://overpass.private.coffee/api/interpreter"`。

- [ ] **Step 4: Commit**

```bash
git add cuhk/scripts/build_data.py
git commit -m "cuhk: data pipeline orchestrator (end-to-end run verified)"
```

---

## 任务 11：Vendor MapLibre GL JS

**Files:**
- Create: `cuhk/site/vendor/maplibre-gl.js`
- Create: `cuhk/site/vendor/maplibre-gl.css`

- [ ] **Step 1: 下载（一次性，jsdelivr 已实测可达）**

```bash
curl -L -o cuhk/site/vendor/maplibre-gl.js https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js
curl -L -o cuhk/site/vendor/maplibre-gl.css https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css
```

- [ ] **Step 2: 校验文件**

Run: `python -c "import os; [print(f, os.path.getsize('cuhk/site/vendor/'+f)) for f in ('maplibre-gl.js','maplibre-gl.css')]"`
Expected: js ≈ 800KB+，css ≈ 100KB+；文件头非 HTML 错误页（`head -c 100 cuhk/site/vendor/maplibre-gl.js` 应为 `/*!` 或 JS 代码）

- [ ] **Step 3: Commit**

```bash
git add cuhk/site/vendor/
git commit -m "cuhk: vendor maplibre-gl 4.7.1 (offline runtime)"
```

---

## 任务 12：地图样式（style.json）

**Files:**
- Create: `cuhk/site/style.json`

配色取自 prettymaps `default.json` preset。无 symbol 文字层 → 不需要 glyphs。hillshade（image source 坐标动态）与 hatch 图案层由 app.js 在运行时注入。

- [ ] **Step 1: 写 style.json**

`cuhk/site/style.json`（完整内容）：

```json
{
  "version": 8,
  "name": "cuhk-prettymaps",
  "sources": {
    "buildings": { "type": "geojson", "data": "data/buildings.geojson" },
    "roads":     { "type": "geojson", "data": "data/roads.geojson" },
    "railway":   { "type": "geojson", "data": "data/railway.geojson" },
    "water":     { "type": "geojson", "data": "data/water.geojson" },
    "waterway":  { "type": "geojson", "data": "data/waterway.geojson" },
    "forest":    { "type": "geojson", "data": "data/forest.geojson" },
    "green":     { "type": "geojson", "data": "data/green.geojson" },
    "beach":     { "type": "geojson", "data": "data/beach.geojson" },
    "parking":   { "type": "geojson", "data": "data/parking.geojson" },
    "sea":       { "type": "geojson", "data": "data/sea.geojson" },
    "contours":  { "type": "geojson", "data": "data/contours.geojson" },
    "boundary":  { "type": "geojson", "data": "data/boundary.geojson" }
  },
  "layers": [
    {
      "id": "background",
      "type": "background",
      "paint": { "background-color": "#F2F4CB" }
    },
    {
      "id": "sea",
      "type": "fill",
      "source": "sea",
      "paint": { "fill-color": "#a8e1e6" }
    },
    {
      "id": "water",
      "type": "fill",
      "source": "water",
      "paint": { "fill-color": "#a8e1e6", "fill-outline-color": "#2F3737" }
    },
    {
      "id": "green",
      "type": "fill",
      "source": "green",
      "paint": { "fill-color": "#8BB174", "fill-outline-color": "#2F3737" }
    },
    {
      "id": "forest",
      "type": "fill",
      "source": "forest",
      "paint": { "fill-color": "#64B96A", "fill-outline-color": "#2F3737" }
    },
    {
      "id": "beach",
      "type": "fill",
      "source": "beach",
      "paint": { "fill-color": "#FCE19C", "fill-outline-color": "#2F3737" }
    },
    {
      "id": "parking",
      "type": "fill",
      "source": "parking",
      "paint": { "fill-color": "#F2F4CB", "fill-outline-color": "#2F3737" }
    },
    {
      "id": "contours",
      "type": "line",
      "source": "contours",
      "paint": {
        "line-color": "#b8b27a",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 0.4, 16, 1.0],
        "line-opacity": 0.8
      }
    },
    {
      "id": "waterway",
      "type": "line",
      "source": "waterway",
      "paint": { "line-color": "#a8e1e6", "line-width": 2 }
    },
    {
      "id": "roads-path",
      "type": "line",
      "source": "roads",
      "filter": ["in", ["get", "road_class"], ["literal", ["path", "steps"]]],
      "paint": {
        "line-color": "#6b7a7a",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 0.5, 16, 2.0],
        "line-dasharray": [2, 1.5]
      }
    },
    {
      "id": "roads-minor",
      "type": "line",
      "source": "roads",
      "filter": ["in", ["get", "road_class"], ["literal", ["medium", "minor"]]],
      "paint": {
        "line-color": "#475657",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.0, 16, 4.0]
      }
    },
    {
      "id": "roads-major",
      "type": "line",
      "source": "roads",
      "filter": ["==", ["get", "road_class"], "major"],
      "paint": {
        "line-color": "#2F3737",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 16, 6.0]
      }
    },
    {
      "id": "railway",
      "type": "line",
      "source": "railway",
      "paint": {
        "line-color": "#2F3737",
        "line-width": 2,
        "line-dasharray": [3, 3]
      }
    },
    {
      "id": "buildings-2d",
      "type": "fill",
      "source": "buildings",
      "paint": {
        "fill-color": ["match", ["get", "c"], 0, "#FF5E5B", "#433633"],
        "fill-outline-color": "#2F3737"
      }
    },
    {
      "id": "buildings-3d",
      "type": "fill-extrusion",
      "source": "buildings",
      "layout": { "visibility": "none" },
      "paint": {
        "fill-extrusion-color": ["match", ["get", "c"], 0, "#FF5E5B", "#433633"],
        "fill-extrusion-height": ["get", "h"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 0.95
      }
    },
    {
      "id": "boundary",
      "type": "line",
      "source": "boundary",
      "paint": {
        "line-color": "#2F3737",
        "line-width": 1.5,
        "line-dasharray": [4, 3],
        "line-opacity": 0.5
      }
    }
  ]
}
```

- [ ] **Step 2: 校验 JSON 合法**

Run: `python -c "import json; json.load(open('cuhk/site/style.json', encoding='utf-8')); print('style.json OK')"`
Expected: `style.json OK`

- [ ] **Step 3: Commit**

```bash
git add cuhk/site/style.json
git commit -m "cuhk: map style (prettymaps palette, no glyphs needed)"
```

---

## 任务 13：前端页面与交互（index.html + app.js）

**Files:**
- Create: `cuhk/site/index.html`
- Create: `cuhk/site/app.js`

- [ ] **Step 1: 写 index.html**

`cuhk/site/index.html`（完整内容）：

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>香港中文大學校園地圖 · CUHK Campus Map</title>
<link rel="stylesheet" href="vendor/maplibre-gl.css">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK", sans-serif; }
  #map { position: absolute; inset: 0; }

  #topbar {
    position: absolute; top: 0; left: 0; right: 0; z-index: 10;
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; background: rgba(242, 244, 203, 0.92);
    border-bottom: 2px solid #2F3737;
  }
  .title { font-size: 18px; font-weight: 700; color: #2F3737; }
  .title .sub { font-size: 12px; font-weight: 400; color: #475657; margin-left: 10px; }
  #chips { display: flex; gap: 8px; align-items: center; }
  .chip {
    display: flex; align-items: center; gap: 6px; cursor: pointer;
    padding: 4px 12px; border: 1.5px solid #2F3737; border-radius: 999px;
    background: #fff; font-size: 13px; color: #2F3737; user-select: none;
  }
  .chip .swatch { width: 10px; height: 10px; border-radius: 50%; }
  .chip.off { opacity: 0.35; }
  #btn3d {
    cursor: pointer; padding: 4px 14px; border: 1.5px solid #2F3737;
    border-radius: 999px; background: #2F3737; color: #F2F4CB; font-size: 13px;
  }

  .poi-marker { display: flex; align-items: center; gap: 4px; cursor: pointer; }
  .poi-marker .dot {
    width: 11px; height: 11px; border-radius: 50%;
    border: 2px solid #fff; box-shadow: 0 0 2px rgba(0,0,0,0.6); flex: none;
  }
  .poi-marker .lbl { display: none; line-height: 1.15; pointer-events: none; }
  .poi-marker .zh { font-size: 12px; font-weight: 700; color: #2F3737; text-shadow: 0 0 3px #F2F4CB, 0 0 3px #F2F4CB; white-space: nowrap; }
  .poi-marker .en { font-size: 10px; color: #475657; text-shadow: 0 0 3px #F2F4CB, 0 0 3px #F2F4CB; white-space: nowrap; }
  body.z-mid .poi-marker.cat-landmark .lbl,
  body.z-mid .poi-marker.cat-transport .lbl { display: block; }
  body.z-high .poi-marker .lbl { display: block; }
  .poi-marker.hidden { display: none; }

  .cat-study .dot, .chip[data-cat="study"] .swatch { background: #2F3737; }
  .cat-life .dot, .chip[data-cat="life"] .swatch { background: #FF5E5B; }
  .cat-sports .dot, .chip[data-cat="sports"] .swatch { background: #64B96A; }
  .cat-transport .dot, .chip[data-cat="transport"] .swatch { background: #2f6fb5; }
  .cat-landmark .dot, .chip[data-cat="landmark"] .swatch { background: #E8B64C; }

  .maplibregl-popup-content { border: 2px solid #2F3737; border-radius: 6px; }
  .pop .zh { font-size: 15px; font-weight: 700; color: #2F3737; }
  .pop .en { font-size: 12px; color: #475657; margin-bottom: 6px; }
  .pop p { margin: 6px 0 0; font-size: 12.5px; color: #2F3737; }

  #credit {
    position: absolute; bottom: 8px; left: 8px; z-index: 10;
    font-size: 11px; color: #475657; background: rgba(242,244,203,0.85);
    padding: 2px 8px; border-radius: 4px;
  }
  #error-overlay {
    position: absolute; inset: 0; z-index: 100; display: flex;
    align-items: center; justify-content: center; background: #F2F4CB;
    font-size: 16px; color: #2F3737; text-align: center; line-height: 2;
  }
  #error-overlay.hidden { display: none; }
  #error-overlay code { background: #fff; padding: 2px 8px; border: 1px solid #2F3737; }
</style>
</head>
<body>
<div id="map"></div>
<div id="topbar">
  <div class="title">香港中文大學校園地圖<span class="sub">CUHK Campus Map · 迎新特別版</span></div>
  <div id="chips">
    <div class="chip" data-cat="study"><span class="swatch"></span>学习</div>
    <div class="chip" data-cat="life"><span class="swatch"></span>生活</div>
    <div class="chip" data-cat="sports"><span class="swatch"></span>体育</div>
    <div class="chip" data-cat="transport"><span class="swatch"></span>交通</div>
    <div class="chip" data-cat="landmark"><span class="swatch"></span>地标</div>
    <button id="btn3d">3D 视角</button>
  </div>
</div>
<div id="credit">数据 © OpenStreetMap contributors · 风格灵感来自 prettymaps</div>
<div id="error-overlay" class="hidden">
  <div>
    找不到地图数据文件 😢<br>
    请先在仓库根目录运行：<code>python cuhk/scripts/build_data.py</code><br>
    然后用 <code>start.bat</code> 重新打开本页
  </div>
</div>
<script src="vendor/maplibre-gl.js"></script>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 app.js**

`cuhk/site/app.js`（完整内容）：

```javascript
/* CUHK 迎新校园地图：MapLibre 初始化 + POI marker + 分类筛选 + 3D 切换
 * 数据全部来自本地 ./data/（由 cuhk/scripts/build_data.py 生成），零外部请求。
 */

const CUHK_CENTER = [114.2070, 22.4205];

const map = new maplibregl.Map({
  container: "map",
  style: "style.json",
  center: CUHK_CENTER,
  zoom: 14.6,
  minZoom: 12.5,
  maxZoom: 18,
  maxPitch: 65,
  attributionControl: { compact: true },
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

/* ---------- 工具 ---------- */

async function loadJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url}: HTTP ${resp.status}`);
  return resp.json();
}

function showError() {
  document.getElementById("error-overlay").classList.remove("hidden");
}

/* ---------- 点状纹理（prettymaps hatch 风格） ---------- */

function makeDotsImage(color) {
  const size = 12;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(3, 3, 1.6, 0, Math.PI * 2);
  ctx.arc(9, 9, 1.6, 0, Math.PI * 2);
  ctx.fill();
  const img = ctx.getImageData(0, 0, size, size);
  return { width: size, height: size, data: new Uint8Array(img.data.buffer) };
}

function addHatchLayers() {
  if (!map.hasImage("dots-green")) {
    map.addImage("dots-green", makeDotsImage("#A7C497"));
    map.addImage("dots-water", makeDotsImage("#9bc3d4"));
  }
  map.addLayer(
    {
      id: "green-hatch",
      type: "fill",
      source: "green",
      paint: { "fill-pattern": "dots-green" },
    },
    "forest"
  );
  map.addLayer(
    {
      id: "water-hatch",
      type: "fill",
      source: "water",
      paint: { "fill-pattern": "dots-water" },
    },
    "green"
  );
}

/* ---------- 山体阴影（image source，坐标来自 hillshade.json） ---------- */

async function addHillshade() {
  const meta = await loadJSON("data/hillshade.json");
  map.addSource("hillshade", {
    type: "image",
    url: "data/hillshade.png",
    coordinates: meta.coordinates,
  });
  map.addLayer(
    { id: "hillshade", type: "raster", source: "hillshade", paint: { "raster-opacity": 1 } },
    "sea" // 插到 sea 之下：陆上有阴影、海面干净
  );
}

/* ---------- POI markers ---------- */

function popupHTML(props) {
  return `<div class="pop">
    <div class="zh">${props.name_zh}</div>
    <div class="en">${props.name_en}</div>
    <p>${props.desc}</p>
  </div>`;
}

function addPOIMarkers(geojson) {
  for (const feat of geojson.features) {
    const p = feat.properties;
    const el = document.createElement("div");
    el.className = `poi-marker cat-${p.category}`;
    el.innerHTML = `<div class="dot"></div>
      <div class="lbl"><div class="zh">${p.name_zh}</div><div class="en">${p.name_en}</div></div>`;
    const popup = new maplibregl.Popup({ maxWidth: "280px", offset: 12 }).setHTML(popupHTML(p));
    new maplibregl.Marker({ element: el })
      .setLngLat(feat.geometry.coordinates)
      .setPopup(popup)
      .addTo(map);
  }
}

/* ---------- 分类筛选 chips ---------- */

function wireChips() {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const cat = chip.dataset.cat;
      chip.classList.toggle("off");
      const show = !chip.classList.contains("off");
      document
        .querySelectorAll(`.poi-marker.cat-${cat}`)
        .forEach((m) => m.classList.toggle("hidden", !show));
    });
  });
}

/* ---------- 3D 切换 ---------- */

function wire3DButton() {
  const btn = document.getElementById("btn3d");
  let is3d = false;
  btn.addEventListener("click", () => {
    is3d = !is3d;
    map.setLayoutProperty("buildings-3d", "visibility", is3d ? "visible" : "none");
    map.setLayoutProperty("buildings-2d", "visibility", is3d ? "none" : "visible");
    map.easeTo({ pitch: is3d ? 45 : 0, duration: 800 });
    btn.textContent = is3d ? "2D 视角" : "3D 视角";
  });
}

/* ---------- 标注密度随缩放变化 ---------- */

function updateZoomClass() {
  const z = map.getZoom();
  document.body.classList.toggle("z-mid", z >= 14.5);
  document.body.classList.toggle("z-high", z >= 15.5);
}

/* ---------- 启动 ---------- */

map.on("load", async () => {
  try {
    addHatchLayers();
    await addHillshade();
    const pois = await loadJSON("data/pois.geojson");
    addPOIMarkers(pois);
    wireChips();
    wire3DButton();
    updateZoomClass();
    map.on("zoom", updateZoomClass);
  } catch (e) {
    console.error(e);
    showError();
  }
});
```

- [ ] **Step 3: 静态检查**

Run: `python -c "import json; [json.load(open('cuhk/site/'+f, encoding='utf-8')) for f in ()]; print('html/js written')"`
以及用浏览器或 `node --check cuhk/site/app.js`（若装了 node）检查 JS 语法；没有 node 就在任务 15 用浏览器验证。

- [ ] **Step 4: Commit**

```bash
git add cuhk/site/index.html cuhk/site/app.js
git commit -m "cuhk: map page (markers, popups, filters, 3D toggle, error overlay)"
```

---

## 任务 14：启动脚本 + README

**Files:**
- Create: `cuhk/site/start.bat`
- Create: `cuhk/site/start.sh`
- Create: `cuhk/README.md`

- [ ] **Step 1: 写 start.bat（Windows 双击即用）**

`cuhk/site/start.bat`：

```bat
@echo off
rem CUHK 校园地图本地启动：起 http.server 并打开浏览器
cd /d "%~dp0"
start "" http://localhost:8765/
python -m http.server 8765
```

- [ ] **Step 2: 写 start.sh（备用）**

`cuhk/site/start.sh`：

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
(sleep 1; xdg-open http://localhost:8765/ 2>/dev/null || open http://localhost:8765/ 2>/dev/null) &
python -m http.server 8765
```

- [ ] **Step 3: 写 README**

`cuhk/README.md`：

```markdown
# CUHK 校园迎新地图

面向新生的香港中文大学交互式网页地图：prettymaps 插画风、中英双语地点标注、
等高线 + 山体阴影 + 3D 建筑表现山城高差。纯静态、零外部依赖，可离线运行。

## 快速开始

```bash
# 1. 跑数据管线（需要网络抓 OSM/SRTM，约 3-10 分钟，之后有缓存）
python cuhk/scripts/build_data.py

# 2. 启动本地服务并打开地图（Windows）
cuhk\site\start.bat
# 或 macOS/Linux：
bash cuhk/site/start.sh
```

浏览器打开 http://localhost:8765/ 即可。`file://` 直接双击 index.html 无法工作
（浏览器限制 fetch/Web Worker），必须走 http.server。

## 修改内容

- 改地点：编辑 `cuhk/data/pois.yml`（42 条中英双语 POI），重跑管线
- 改样式：编辑 `cuhk/site/style.json`（配色取自 prettymaps default preset），刷新页面即可
- 改交互：编辑 `cuhk/site/app.js`

## 测试

```bash
python -m pytest cuhk/tests -v
```

## 常见问题

- **Overpass 超时**：重跑一次（有缓存）；或设镜像环境变量
  `CUHK_OVERPASS_URL=https://overpass.private.coffee/api/interpreter`
- **POI 匹配失败**：管线会列出未匹配的 id，对照 `cuhk/cache/names_dump.csv`
  （任务 8 流程）修正 `osm_name` 或改用 `lon/lat`

## 数据与许可

地图数据 © OpenStreetMap contributors (ODbL)。视觉风格灵感来自
[prettymaps](https://github.com/marceloprates/prettymaps)。
```

- [ ] **Step 4: 手动冒烟 start.bat**

Run: `cuhk\site\start.bat`（或手动 `cd cuhk/site && python -m http.server 8765`）
Expected: 浏览器打开 http://localhost:8765/ 显示地图（任务 15 做完整检查）

- [ ] **Step 5: Commit**

```bash
git add cuhk/site/start.bat cuhk/site/start.sh cuhk/README.md
git commit -m "cuhk: local launch scripts + README"
```

---

## 任务 15：端到端验证

**Files:**
- Create: `cuhk/screenshots/map-2d.png`
- Create: `cuhk/screenshots/map-3d.png`

- [ ] **Step 1: 全量测试回归**

Run: `python -m pytest cuhk/tests -v`
Expected: 全部 passed

- [ ] **Step 2: 确认数据齐备**

Run: `python -c "import os; d='cuhk/site/data'; print(sorted(os.listdir(d)))"`
Expected: 13 个 `.geojson`（boundary + buildings/roads/railway/water/waterway/forest/green/beach/parking/sea/contours 共 11 层 + pois；空图层为合法空 FeatureCollection）+ `hillshade.png` + `hillshade.json`

- [ ] **Step 3: 浏览器手工 checklist**

打开 http://localhost:8765/ 逐项确认（每项都要实际操作）：

- [ ] 地图加载，奶油底色 + 红/棕建筑 + 绿地/海面与 prettymaps 风格一致
- [ ] 山体阴影可见（山坡有明暗），等高线在山上可见
- [ ] 海面（吐露港）为浅蓝色，不是奶油色
- [ ] 点击 POI（如大学图书馆）弹出 中文名+英文名+简介
- [ ] 5 个分类 chip 点击能开关对应标注
- [ ] 缩小到 14 级：只见地标/交通标注；放大到 16 级：全部标注出现
- [ ] 点 "3D 视角"：建筑拉起、视角倾斜，山城立体感明显；再点恢复 2D
- [ ] 右键拖动可旋转/倾斜，滚轮缩放正常
- [ ] 打开 DevTools Network 面板刷新：**没有任何外部域名请求**（全部 localhost）
- [ ] 删除 `cuhk/site/data/pois.geojson` 后刷新：出现"请先运行 build_data.py"提示（验证后恢复文件）

- [ ] **Step 4: 截图存档**

2D 全景与 3D 视角各截一张，保存为 `cuhk/screenshots/map-2d.png`、`cuhk/screenshots/map-3d.png`。

- [ ] **Step 5: 最终 Commit**

```bash
git add cuhk/screenshots/
git commit -m "cuhk: e2e verified, add screenshots"
```

---

## 计划自审记录

**Spec 覆盖检查：**
- §5 ① 边界 → 任务 3 ✅；② 图层 → 任务 4 ✅；③ 高差 → 任务 6 ✅；④ POI → 任务 8 ✅；⑤ 校验 → 任务 9 ✅
- §6 前端 → 任务 11–13 ✅；start.bat → 任务 14 ✅（§6.2 file:// 限制已说明）
- §7 高差三件套（等高线/阴影/3D 建筑）→ 任务 6 + 12 + 13 ✅；高度回退规则简化已声明偏差 ✅
- §8 POI 交互（chips/弹窗/缩放联动）→ 任务 13 ✅；photo 字段预留 → pois.yml 可加字段，前端暂不渲染 ✅
- §9 错误处理 → 任务 2（Overpass 重试+镜像提示）、任务 7（高度回退）、任务 13（error overlay）✅
- §10 验证 → 任务 9 + 15 ✅
- §11 范围外（路线规划/真 3D 地形/照片/部署/搜索）→ 计划中无任何任务引入 ✅

**类型一致性：** `road_class`（任务 4 产出 ↔ 任务 12 style filter）、`h`/`c`（任务 7 ↔ 12）、`ele`（任务 6 ↔ 12 未用到但保留在 geojson 供调试）、pois 属性 `name_zh/name_en/category/desc`（任务 8 ↔ 13）——已核对一致。图层文件名 `*.geojson`（任务 10 写出 ↔ style.json sources ↔ app.js fetch）一致。
