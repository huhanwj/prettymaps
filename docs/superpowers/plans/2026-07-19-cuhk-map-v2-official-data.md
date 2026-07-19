# CUHK 校园地图 v2（官方数据版）· 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 CUHK 官方地图数据集（`CUHK_MAP_DATA`）校正校园内数据，新增校巴模式、官方步行捷径、建筑分类着色与真 3D 地形，解决 PR #1 的 6 条人工核验意见。

**Architecture:** v1 管线增量。新增 `pipeline/official.py`（下载/解析官方数据集 → 5 个 GeoJSON）、`pipeline/terrain.py`（SRTM → terrain-RGB 瓦片）、`pipeline/building_types.py`（官方点→OSM 面匹配分类）；pois.py 加官方优先解析链；前端加校巴开关/捷径层/setTerrain 联动/建筑分类色。

**Tech Stack:** 同 v1（零新增 Python 依赖）。官方数据集：`https://www.cuhk.edu.hk/english/js/campus/cuhk_location_db.js`（397KB，提交存档到 `cuhk/data/official/cuhk_location_db.js` 保证可复现/离线）。

**已核实的官方数据事实（2026-07-19）：**
- `buildings` 268 条：`bldg_code/bldg_name_en/bldg_name_xb5/lat_lng/campus_id/hostel_type/type`；hostel_type ∈ {''(97), student(38), staff(20), guest(2), others(2)} —— **它是住宿类型不是功能分类**，建筑功能分类需按名称规则推导
- `landmarks` 26 条：含 仲門(Gate of Wisdom) 与 烽火台(The Beacon) 两个**不同**条目、The University Mall（林蔭大道/百萬大道）、Pavilion of Harmony、Lake Ad Excellentiam
- `shuttle_bus_route` 19 条（含 route_color）、`shuttle_bus_route_seg`（route_id→seg_id 有序映射）、`shuttle_bus_seg` 46 段（encoded_line 为 Google encoded polyline）、`shuttle_bus_stops` 51 站（含 University Station 官方坐标 (22.414497479108096, 114.21013355255127)）
- `walking_route` 2 条：University Station → NA College / Shaw College（ecoded_line [原文如此拼写]）
- `colleges` 数组含书院坐标（部分 lat_lng 为空）
- 记录格式：每条一行 `{...}`，key 均双引号；顶层数组 key 无引号；`InfoWindow_Display` 含单引号数组（**不解析该段**）
- 官方地图不给建筑 footprint 配色 → v2 色板为"官方分类 + prettymaps 调和"：college `#E8B64C` / dorm `#F2A65A` / sports `#64B96A` / study `#2f6fb5` / other 红棕交替

---

## 任务 V1：官方数据管线（official.py）

**Files:**
- Create: `cuhk/data/official/cuhk_location_db.js`（下载存档并提交）
- Create: `cuhk/scripts/pipeline/official.py`
- Test: `cuhk/tests/test_official.py`

- [ ] **Step 1: 下载官方数据集存档**

```bash
mkdir -p cuhk/data/official
curl -s -m 30 "https://www.cuhk.edu.hk/english/js/campus/cuhk_location_db.js?20161006" -H "User-Agent: Mozilla/5.0" -o cuhk/data/official/cuhk_location_db.js
python -c "import os; print(os.path.getsize('cuhk/data/official/cuhk_location_db.js'))"  # ≈396929
```

- [ ] **Step 2: 写失败测试**

`cuhk/tests/test_official.py`：

```python
import pytest

from pipeline import official


SAMPLE_JS = """var CUHK_MAP_DATA = {

campus : [
{"id":"1", "campus_en":"Central Campus", "campus_xb5":"中央校園", "lat_lng":"(22.4193, 114.2069)"},
],
buildings : [
{"building_id":"1", "bldg_name_en":"Benjamin Franklin Centre", "bldg_name_xb5":"范克廉樓", "lat_lng":"(22.41841513972474, 114.20518487691879)", "hostel_type":"", "bldg_code":"H1"},
{"building_id":"2", "bldg_name_en":"Brace {Test} \\"Quoted\\"", "bldg_name_xb5":"測試", "lat_lng":"", "hostel_type":"student", "bldg_code":"X2"},
],
shuttle_bus_route : [
{"route_id":"1", "route_name_en":"University Station > NA College", "route_name_xb5":"大學站 > 新亞書院", "route_color":"#ff0000"},
],
shuttle_bus_route_seg : [
{"route_id":"1", "seg_id":"1", "order":"2"},
{"route_id":"1", "seg_id":"2", "order":"1"},
],
shuttle_bus_seg : [
{"bus_route_seg_id":"1", "start_bus_stop_id":"2", "end_bus_stop_id":"3", "encoded_line":"_p~iF~ps|U_ulLnnqC"},
{"bus_route_seg_id":"2", "start_bus_stop_id":"1", "end_bus_stop_id":"2", "encoded_line":"_mqNvxq`@"},
],
shuttle_bus_stops : [
{"bus_stop_id":"1", "bus_stop_name_en":"University Station", "bus_stop_name_xb5":"港鐵大學站", "lat_lng":"(22.4145, 114.2101)"},
],
walking_route : [
{"walking_route_id":"1", "walking_route_name_en":"Station > NA", "walking_route_name_xb5":"大學站 > 新亞", "ecoded_line":"_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
],
};
"""


def test_parse_map_data_sections():
    db = official.parse_map_data(SAMPLE_JS)
    assert set(db) >= {"campus", "buildings", "shuttle_bus_route", "walking_route"}
    assert db["buildings"][0]["bldg_name_en"] == "Benjamin Franklin Centre"
    # 嵌套花括号与转义引号不炸解析
    assert len(db["buildings"]) == 2


def test_decode_polyline_google_example():
    pts = official.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts == pytest.approx(
        [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)], abs=1e-4
    )


def test_parse_lat_lng():
    assert official.parse_lat_lng("(22.41841513972474, 114.20518487691879)") == (
        114.20518487691879,
        22.41841513972474,
    )
    assert official.parse_lat_lng("") is None


def test_official_buildings_gdf():
    db = official.parse_map_data(SAMPLE_JS)
    gdf = official.official_buildings(db)
    assert len(gdf) == 1  # 第二条 lat_lng 为空被跳过
    row = gdf.iloc[0]
    assert row["name_en"] == "Benjamin Franklin Centre"
    assert row["name_zh"] == "范克廉樓"
    assert row.geometry.x == pytest.approx(114.20518487691879)


def test_shuttle_routes_ordered_assembly():
    db = official.parse_map_data(SAMPLE_JS)
    gdf = official.shuttle_routes(db)
    assert len(gdf) == 1
    row = gdf.iloc[0]
    assert row["color"] == "#ff0000"
    # order=1 的 seg2 (_mqNvxq`@) 应排在 order=2 的 seg1 前面
    line = row.geometry.geoms[0]
    assert line.coords[0] == pytest.approx((-126.453, 43.252), abs=1e-4)


def test_walking_routes():
    db = official.parse_map_data(SAMPLE_JS)
    gdf = official.walking_routes(db)
    assert len(gdf) == 1
    assert len(gdf.iloc[0].geometry.coords) == 3
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest cuhk/tests/test_official.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'pipeline.official'`

- [ ] **Step 4: 实现 official.py**

`cuhk/scripts/pipeline/official.py`：

```python
"""CUHK 官方校园地图数据集（CUHK_MAP_DATA）解析。

数据源：https://www.cuhk.edu.hk/english/js/campus/cuhk_location_db.js
文件以 cuhk/data/official/cuhk_location_db.js 存档（可复现、可离线）。
解析策略：定位各顶层 `key : [` 数组段，括号配平（字符串感知）切出每条 JSON 记录。
折线为 Google encoded polyline（shuttle_bus_seg.encoded_line / walking_route.ecoded_line）。
"""

import json
import re
from pathlib import Path

import geopandas as gp
from shapely.geometry import LineString, MultiLineString, Point

OFFICIAL_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "official" / "cuhk_location_db.js"

SECTIONS = [
    "campus", "colleges", "buildings", "landmarks",
    "shuttle_bus_route", "shuttle_bus_route_seg", "shuttle_bus_seg",
    "shuttle_bus_stops", "walking_route",
]


def _scan_balanced(text, start, open_ch, close_ch):
    """从 text[start]（open_ch）扫到配平的 close_ch，返回结束索引（不含）。
    字符串感知：跳过 "..." 内部及 \\ 转义。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"括号不配平：{open_ch} @ {start}")


def parse_map_data(text):
    """把 CUHK_MAP_DATA JS 文本解析成 {section: [record, ...]}。"""
    db = {}
    for section in SECTIONS:
        m = re.search(rf"\n{section}\s*:\s*\[", text)
        if not m:
            continue
        arr_start = text.index("[", m.end() - 1)
        arr_end = _scan_balanced(text, arr_start, "[", "]")
        body = text[arr_start + 1 : arr_end]
        records = []
        pos = 0
        while True:
            brace = body.find("{", pos)
            if brace == -1:
                break
            end = _scan_balanced(body, brace, "{", "}")
            records.append(json.loads(body[brace : end + 1]))
            pos = end + 1
        db[section] = records
    return db


def decode_polyline(encoded):
    """Google encoded polyline → [(lat, lng), ...]。"""
    points, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        points.append((lat / 1e5, lng / 1e5))
    return points


def parse_lat_lng(raw):
    """'(22.41, 114.20)' → (lng, lat)；空串/非法 → None。"""
    if not raw:
        return None
    m = re.match(r"\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)", str(raw))
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    return (lng, lat)


def _points_gdf(records, name_fields, extra_fields=()):
    """通用：records → Point GeoDataFrame（跳过无坐标）。"""
    rows = []
    for rec in records:
        ll = parse_lat_lng(rec.get("lat_lng"))
        if ll is None:
            continue
        row = {k: rec.get(src, "") for k, src in name_fields}
        for k in extra_fields:
            row[k] = rec.get(k, "")
        row["geometry"] = Point(ll)
        rows.append(row)
    return gp.GeoDataFrame(rows, crs="EPSG:4326")


def official_buildings(db):
    return _points_gdf(
        db["buildings"],
        [("name_en", "bldg_name_en"), ("name_zh", "bldg_name_xb5")],
        extra_fields=("bldg_code", "campus_id", "hostel_type", "type"),
    )


def official_landmarks(db):
    return _points_gdf(
        db["landmarks"],
        [("name_en", "landmark_name_en"), ("name_zh", "landmark_name_xb5")],
        extra_fields=("campus_id",),
    )


def official_colleges(db):
    return _points_gdf(
        db["colleges"],
        [("name_en", "name_en"), ("name_zh", "name_xb5")],
    )


def shuttle_stops(db):
    return _points_gdf(
        db["shuttle_bus_stops"],
        [("name_en", "bus_stop_name_en"), ("name_zh", "bus_stop_name_xb5")],
    )


def shuttle_routes(db):
    """按 route_id 组装有序 seg 折线 → MultiLineString。"""
    segs = {s["bus_route_seg_id"]: s for s in db["shuttle_bus_seg"]}
    order = {}
    for r in db["shuttle_bus_route_seg"]:
        order.setdefault(r["route_id"], []).append((int(r["order"]), r["seg_id"]))

    rows = []
    for route in db["shuttle_bus_route"]:
        rid = route["route_id"]
        lines = []
        for _, seg_id in sorted(order.get(rid, [])):
            seg = segs.get(seg_id)
            if seg and seg.get("encoded_line"):
                pts = decode_polyline(seg["encoded_line"])
                if len(pts) >= 2:
                    lines.append(LineString([(lng, lat) for lat, lng in pts]))
        if not lines:
            continue
        rows.append({
            "name_en": route.get("route_name_en", ""),
            "name_zh": route.get("route_name_xb5", ""),
            "color": route.get("route_color") or "#2F3737",
            "geometry": MultiLineString(lines),
        })
    return gp.GeoDataFrame(rows, crs="EPSG:4326")


def walking_routes(db):
    rows = []
    for rec in db["walking_route"]:
        encoded = rec.get("ecoded_line") or rec.get("encoded_line") or ""
        pts = decode_polyline(encoded)
        if len(pts) < 2:
            continue
        rows.append({
            "name_en": rec.get("walking_route_name_en", ""),
            "name_zh": rec.get("walking_route_name_xb5", ""),
            "geometry": LineString([(lng, lat) for lat, lng in pts]),
        })
    return gp.GeoDataFrame(rows, crs="EPSG:4326")


def load_official_db(path=None):
    """读存档文件并解析，返回 db dict。"""
    path = Path(path) if path else OFFICIAL_DB_PATH
    text = path.read_text(encoding="utf-8-sig")
    return parse_map_data(text)


def build_official_products(db):
    """一次性产出全部官方图层：{name: GeoDataFrame}。"""
    return {
        "official_buildings": official_buildings(db),
        "official_landmarks": official_landmarks(db),
        "official_colleges": official_colleges(db),
        "shuttle_routes": shuttle_routes(db),
        "shuttle_stops": shuttle_stops(db),
        "walking": walking_routes(db),
    }
```

- [ ] **Step 5: 运行确认通过 + 真实数据自检**

Run: `python -m pytest cuhk/tests/test_official.py -v` → 6 passed

真实数据自检（应输出 268/26/19/51/2）：

```bash
PYTHONPATH=cuhk/scripts python -X utf8 -c "
from pipeline import official
db = official.load_official_db()
p = official.build_official_products(db)
for k, v in p.items():
    print(k, len(v))
"
```

- [ ] **Step 6: Commit**

```bash
git add cuhk/data/official/cuhk_location_db.js cuhk/scripts/pipeline/official.py cuhk/tests/test_official.py
git commit -m "cuhk v2: official CUHK dataset parser (buildings/landmarks/shuttle/walking)"
```

---

## 任务 V2：POI 官方坐标校正

**Files:**
- Modify: `cuhk/scripts/pipeline/pois.py`
- Modify: `cuhk/data/pois.yml`
- Test: `cuhk/tests/test_pois.py`（追加）

- [ ] **Step 1: 追加失败测试**

追加到 `cuhk/tests/test_pois.py`：

```python
def test_resolve_prefers_official(features):
    official = gp.GeoDataFrame(
        {
            "name_en": ["New Asia College"],
            "name_zh": ["新亞書院"],
            "geometry": [box(114.2090, 22.4210, 114.2100, 22.4220)],
        },
        crs="EPSG:4326",
    )
    entries = [
        {"id": "na", "name_zh": "新亞書院", "name_en": "New Asia College",
         "category": "life", "desc": "", "official_name": "New Asia College",
         "osm_name": "New Asia College"}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features, official=official)
    assert unmatched == []
    # official 与 OSM fixture 同一坐标，证明走了哪条通道需要看 source 列
    assert gdf.iloc[0]["source"] == "official"


def test_resolve_official_falls_back_to_osm(features):
    official = gp.GeoDataFrame(
        {"name_en": [], "name_zh": [], "geometry": []}, crs="EPSG:4326"
    )
    entries = [
        {"id": "na", "name_zh": "新亞書院", "name_en": "New Asia College",
         "category": "life", "desc": "", "official_name": "No Such Place Zzz",
         "osm_name": "New Asia College"}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features, official=official)
    assert unmatched == []
    assert gdf.iloc[0]["source"] == "osm"
```

- [ ] **Step 2: 修改 pois.py（官方优先解析链）**

1. `load_pois` 的定位校验改为：`lon/lat`、`osm_name`、`official_name` 三者至少其一
2. `resolve_pois(entries, features, official=None)`：
   - `official_name` 存在且 official 非空 → 用 `_match_feature` 在 official 的 `name_en`/`name_zh` 列模糊匹配（阈值 0.55），命中 → 该坐标，`source="official"`
   - 未命中 → 回落 `lon/lat`（`source="manual"`）→ 再落 `osm_name`（`source="osm"`）
   - 全落空 → unmatched
   - 输出 gdf 增加 `source` 列（现有列不变）

`_match_feature` 的候选列改为参数化：`_match_feature(query, features, cols=("name", "name:en", "name:zh"))`，官方匹配调用时传 `cols=("name_en", "name_zh")`。

- [ ] **Step 3: 运行确认通过**

Run: `python -m pytest cuhk/tests/test_pois.py -v`
Expected: 全部通过（旧测试不受 source 列影响）

- [ ] **Step 4: pois.yml 加 official_name（含 beacon 修正 + 新增仲門）**

给以下条目加 `official_name`（执行者先用任务 V1 的真实数据核对官方确切名称再落笔，下表为最佳猜测）：

| id | official_name（猜测，需核对） |
|---|---|
| 9 个书院 | 同 name_en（如 `Chung Chi College`；若 buildings 无，查 colleges 数组） |
| ul, moore-lib, chien-mu-lib, wu-chung-lib, yia, cyt, shb, science-centre, mmw, elb, fkh, lsk | 同 name_en |
| franklin, orchid-lodge, cc-canteen, na-canteen, uc-canteen | 同 name_en（可能是 facilities 而非 buildings——V2 实现时把官方查找范围定为 buildings+landmarks+facilities+colleges 四段合并，facilities 解析加入 official.py 的 SECTIONS 与 `_points_gdf`（字段名 facilities_name_en/facilities_name_xb5）|
| sports-centre, haddon-cave | 同 name_en |
| university-station | `University Station`（shuttle_bus_stops，官方坐标 (22.4145, 114.2101)；校巴站也合并进官方查找范围） |
| harmony | `Pavilion of Harmony`（landmarks） |
| mall | `The University Mall`（landmarks） |
| beacon | `The Beacon`（landmarks；**替换现有 The Gate 匹配**，坐标以官方为准） |
| lake | `Lake Ad Excellentiam`（landmarks） |
| chapel, shaw-hall, uadmin | 同 name_en（buildings） |
| swimming-pool, shuttle-central, bus-terminus | 保持 lon/lat 不动 |
| pier, science-park, promenade | 保持 osm_name（校外，OSM 为准） |

新增第 43 条（官方 landmarks 里的独立地标，v1 误与烽火台混为一谈）：

```yaml
  - {id: gate-of-wisdom, name_zh: 仲門, name_en: Gate of Wisdom, category: landmark, desc: 大學圖書館前的雕塑《仲門》。, official_name: Gate of Wisdom}
```

执行者验证方法（同 v1 任务 8 Step 6）：跑 resolve 自检，42+1 条全部 resolved 且 source 分布合理（campus 内大多 official），打印对照表人工过目。

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/pois.py cuhk/tests/test_pois.py cuhk/data/pois.yml
git commit -m "cuhk v2: POI official-first resolution + Gate of Wisdom entry"
```

---

## 任务 V3：校巴模式（前端）

**Files:**
- Modify: `cuhk/site/style.json`
- Modify: `cuhk/site/app.js`
- Modify: `cuhk/site/index.html`
- Modify: `cuhk/scripts/build_data.py`（写出 shuttle_routes/shuttle_stops）

- [ ] **Step 1: build_data.py 接入官方图层**

在 ⑥ POI 之前插入一步（编号顺延打印）：

```python
    # ⑤b 官方数据（校巴/捷径/官方建筑）
    print("== ⑤b 官方数据 ==")
    from pipeline import official
    db = official.load_official_db()
    products = official.build_official_products(db)
    gdfs.update(products)
    for name, gdf in products.items():
        print(f"  {name}: {len(gdf)}")
```

keep dict 增加：

```python
        "official_buildings": ["name_en", "name_zh", "bldg_code", "campus_id", "hostel_type", "type", "geometry"],
        "official_landmarks": ["name_en", "name_zh", "geometry"],
        "shuttle_routes": ["name_en", "name_zh", "color", "geometry"],
        "shuttle_stops": ["name_en", "name_zh", "geometry"],
        "walking": ["name_en", "name_zh", "geometry"],
```

（official_colleges 不写出，仅供 V2 解析用——写入 gdfs 但 keep 不加，跳过时会写空 FC？注意：keep 循环只处理 keep 里的 key，official_colleges 不在 keep 就不会被写出，OK。）

- [ ] **Step 2: style.json 加 sources/layers**

sources 加：

```json
    "shuttle_routes": { "type": "geojson", "data": "data/shuttle_routes.geojson" },
    "shuttle_stops": { "type": "geojson", "data": "data/shuttle_stops.geojson" }
```

layers 加（放在 boundary 层之后）：

```json
    {
      "id": "shuttle-routes",
      "type": "line",
      "source": "shuttle_routes",
      "layout": { "visibility": "none" },
      "paint": {
        "line-color": ["get", "color"],
        "line-width": 3,
        "line-opacity": 0.9
      }
    },
    {
      "id": "shuttle-stops",
      "type": "circle",
      "source": "shuttle_stops",
      "layout": { "visibility": "none" },
      "paint": {
        "circle-radius": 5,
        "circle-color": "#ffffff",
        "circle-stroke-color": "#2F3737",
        "circle-stroke-width": 2
      }
    }
```

- [ ] **Step 3: index.html 加校巴按钮 + app.js 开关与弹窗**

index.html 在 `#btn3d` 前加：

```html
    <button id="btnBus">校巴線</button>
```

CSS 里 `#btn3d` 的选择器改为 `#btn3d, #btnBus`（同款样式），`#btnBus.active` 反色。

app.js：

```javascript
/* ---------- 校巴模式 ---------- */

function wireBusButton() {
  const btn = document.getElementById("btnBus");
  let on = false;
  btn.addEventListener("click", () => {
    on = !on;
    for (const id of ["shuttle-routes", "shuttle-stops"]) {
      map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    }
    btn.classList.toggle("active", on);
  });

  for (const layer of ["shuttle-routes", "shuttle-stops"]) {
    map.on("click", layer, (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "280px" })
        .setLngLat(e.lngLat)
        .setHTML(popupHTML({ name_zh: p.name_zh, name_en: p.name_en, desc: p.desc || "" }))
        .addTo(map);
    });
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }
}
```

启动序列中 `wire3DButton();` 后加 `wireBusButton();`。

- [ ] **Step 4: 管线重跑 + node --check**

```bash
python cuhk/scripts/build_data.py   # 校验应全部通过，新增 shuttle_routes 19 / shuttle_stops 51
node --check cuhk/site/app.js
```

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/build_data.py cuhk/site/style.json cuhk/site/app.js cuhk/site/index.html
git commit -m "cuhk v2: shuttle bus mode (routes/stops/toggle/popups)"
```

---

## 任务 V4：建筑分类着色

**Files:**
- Create: `cuhk/scripts/pipeline/building_types.py`
- Modify: `cuhk/scripts/build_data.py`（在 add_heights 后调用）
- Modify: `cuhk/site/style.json`（buildings-2d/3d 的 fill-color 改 bt 匹配）
- Test: `cuhk/tests/test_building_types.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_building_types.py`：

```python
import geopandas as gp
import pytest
from shapely.geometry import Point, box

from pipeline import building_types


def test_classify_rules():
    c = building_types.classify_building
    assert c("New Asia College", "") == "college"
    assert c("University Library", "") == "study"
    assert c("Ch'ien Mu Library", "") == "study"
    assert c("University Sports Centre", "") == "sports"
    assert c("University Swimming Pool", "") == "sports"
    assert c("Postgraduate Halls", "student") == "dorm"
    assert c("Staff Quarters", "staff") == "dorm"
    assert c("Esther Lee Building", "") == "other"


def test_match_official_to_osm():
    osm = gp.GeoDataFrame(
        {"geometry": [box(114.2000, 22.4100, 114.2010, 22.4110),
                      box(114.2100, 22.4200, 114.2110, 22.4210)]},
        crs="EPSG:4326",
    )
    official = gp.GeoDataFrame(
        {"name_en": ["A", "B"], "hostel_type": ["", "student"],
         "geometry": [Point(114.2005, 22.4105), Point(114.2105, 22.4205)]},
        crs="EPSG:4326",
    )
    bt = building_types.assign_types(osm, official, max_dist_m=60)
    assert list(bt) == ["other", "dorm"]


def test_no_match_stays_other():
    osm = gp.GeoDataFrame({"geometry": [box(114.2, 22.4, 114.21, 22.41)]}, crs="EPSG:4326")
    official = gp.GeoDataFrame(
        {"name_en": ["Far"], "hostel_type": [""],
         "geometry": [Point(114.3, 22.45)]},
        crs="EPSG:4326",
    )
    bt = building_types.assign_types(osm, official, max_dist_m=60)
    assert list(bt) == ["other"]
```

- [ ] **Step 2: 实现 building_types.py**

`cuhk/scripts/pipeline/building_types.py`：

```python
"""建筑功能分类：官方建筑点 → OSM 建筑面匹配，写入 bt 属性。

规则：hostel_type 非空 → dorm；名称含 College → college；Sports/Pool/Gym/Field → sports；
Library/Museum/Gallery → study；其余 → other（保留红/棕交替色）。
官方 type 字段是住宿类型，不能用作功能分类（见 v2 计划头注）。
"""

import re

import geopandas as gp

SPORTS_RE = re.compile(r"Sports|Pool|Gym|Field|Playground|Stadium", re.I)
STUDY_RE = re.compile(r"Library|Libraries|Museum|Gallery", re.I)
COLLEGE_RE = re.compile(r"College", re.I)

DORM_TYPES = {"student", "staff", "guest"}

PALETTE = {
    "college": "#E8B64C",
    "dorm": "#F2A65A",
    "sports": "#64B96A",
    "study": "#2f6fb5",
}


def classify_building(name_en, hostel_type):
    if str(hostel_type).strip().lower() in DORM_TYPES:
        return "dorm"
    name = str(name_en or "")
    if COLLEGE_RE.search(name):
        return "college"
    if SPORTS_RE.search(name):
        return "sports"
    if STUDY_RE.search(name):
        return "study"
    return "other"


def assign_types(osm_buildings, official_points, max_dist_m=60):
    """OSM 建筑面 ← 最近官方点（UTM 下 ≤max_dist_m），返回与 osm 对齐的 bt Series。"""
    if osm_buildings.empty:
        return gp.pd.Series([], dtype=str)
    osm_u = osm_buildings.to_crs(osm_buildings.estimate_utm_crs())
    centroids = osm_u.geometry.centroid
    result = ["other"] * len(osm_u)
    if official_points.empty:
        return gp.pd.Series(result, index=osm_buildings.index)
    off_u = official_points.to_crs(osm_u.crs)
    for _, off in off_u.iterrows():
        dists = centroids.distance(off.geometry)
        nearest = dists.idxmin()
        if dists.loc[nearest] <= max_dist_m:
            result[osm_u.index.get_loc(nearest)] = classify_building(
                off.get("name_en"), off.get("hostel_type")
            )
    return gp.pd.Series(result, index=osm_buildings.index)
```

- [ ] **Step 3: build_data.py 接入 + style.json 改色**

build_data.py 在 `heights.add_heights` 后加：

```python
    gdfs["buildings"]["bt"] = building_types.assign_types(
        gdfs["buildings"], gdfs["official_buildings"]
    )
```

（import building_types 加进文件头的 pipeline import 列表；keep["buildings"] 加 "bt"。）

style.json 的 buildings-2d fill-color 与 buildings-3d fill-extrusion-color 改为：

```json
["match", ["get", "bt"],
  "college", "#E8B64C",
  "dorm", "#F2A65A",
  "sports", "#64B96A",
  "study", "#2f6fb5",
  ["match", ["get", "c"], 0, "#FF5E5B", "#433633"]]
```

- [ ] **Step 4: 测试 + 管线重跑**

Run: `python -m pytest cuhk/tests -v`（新 3 + 既有全过）；`python cuhk/scripts/build_data.py`（全部 OK，无 bt 缺列 WARNING）

- [ ] **Step 5: Commit**

```bash
git add cuhk/scripts/pipeline/building_types.py cuhk/tests/test_building_types.py cuhk/scripts/build_data.py cuhk/site/style.json
git commit -m "cuhk v2: building type coloring (college/dorm/sports/study)"
```

---

## 任务 V5：真 3D 地形（terrain.py + setTerrain）

**Files:**
- Create: `cuhk/scripts/pipeline/terrain.py`
- Modify: `cuhk/scripts/build_data.py`（④ 后加瓦片生成）
- Modify: `cuhk/site/app.js`（raster-dem source + 3D 联动）
- Modify: `.gitignore`（cuhk/site/tiles/）
- Test: `cuhk/tests/test_terrain.py`

- [ ] **Step 1: 写失败测试**

`cuhk/tests/test_terrain.py`：

```python
import numpy as np
import pytest

from pipeline import terrain


def test_rgb_roundtrip():
    for h in (-5.0, 0.0, 42.5, 140.0, 8848.0):
        r, g, b = terrain.encode_height(h)
        assert terrain.decode_height(r, g, b) == pytest.approx(h, abs=0.06)


def test_tile_math():
    assert terrain.lon2tilex(114.0, 16) == pytest.approx(63147.8, abs=0.1)
    # 瓦片边界反解
    x0, x1 = 63147, 63148
    assert terrain.tilex2lon(x0, 16) < 114.0 < terrain.tilex2lon(x1, 16)
    y = terrain.lat2tiley(22.42, 16)
    assert terrain.tiley2lat(int(y), 16) > 22.42 > terrain.tiley2lat(int(y) + 1, 16)


def test_generate_tile_shape():
    dem = np.arange(100 * 100, dtype=np.float32).reshape(100, 100)
    lons = np.linspace(114.0, 114.1, 100)
    lats = np.linspace(22.0, 22.1, 100)
    tile = terrain.render_tile(dem, lons, lats, z=16, x=63147, y=terrain.lat2tiley(22.05, 16).__int__(), size=256)
    assert tile.shape == (256, 256, 3)
    assert tile.dtype == np.uint8


def test_tiles_covering():
    tiles = terrain.tiles_covering(114.20, 22.41, 114.22, 22.43, 14)
    assert tiles  # 非空
    assert all(t[0] == 14 for t in tiles)
```

- [ ] **Step 2: 实现 terrain.py**

`cuhk/scripts/pipeline/terrain.py`：

```python
"""terrain-RGB 瓦片（Mapbox 编码）：SRTM DEM → PNG 金字塔 → MapLibre setTerrain。

编码：h = -10000 + (R*65536 + G*256 + B) * 0.1
瓦片数学：标准 slippy map（Web Mercator）。
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import map_coordinates

ZMIN, ZMAX = 10, 16
TILE_SIZE = 256


def encode_height(h):
    v = int(round((h + 10000) * 10))
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def decode_height(r, g, b):
    return (r * 65536 + g * 256 + b) / 10 - 10000


def lon2tilex(lon, z):
    return (lon + 180.0) / 360.0 * 2**z


def lat2tiley(lat, z):
    r = math.radians(lat)
    return (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * 2**z


def tilex2lon(x, z):
    return x / 2**z * 360.0 - 180.0


def tiley2lat(y, z):
    n = math.pi - 2.0 * math.pi * y / 2**z
    return math.degrees(math.atan(math.sinh(n)))


def tiles_covering(minlon, minlat, maxlon, maxlat, z):
    x0 = int(math.floor(lon2tilex(minlon, z)))
    x1 = int(math.floor(lon2tilex(maxlon, z)))
    y0 = int(math.floor(lat2tiley(maxlat, z)))  # 北在上
    y1 = int(math.floor(lat2tiley(minlat, z)))
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def render_tile(dem, lons, lats, z, x, y, size=TILE_SIZE):
    """从 (dem, lons, lats) 双线性采样出一张 size×size×3 的 terrain-RGB 瓦片。"""
    west, east = tilex2lon(x, z), tilex2lon(x + 1, z)
    north, south = tiley2lat(y, z), tiley2lat(y + 1, z)
    out_lons = np.linspace(west, east, size, endpoint=False) + (east - west) / (2 * size)
    out_lats = np.linspace(north, south, size, endpoint=False) + (south - north) / (2 * size)
    cols = (out_lons - lons[0]) / (lons[-1] - lons[0]) * (len(lons) - 1)
    rows = (lats[0] - out_lats) / (lats[0] - lats[-1]) * (len(lats) - 1)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    sampled = map_coordinates(dem, [rr, cc], order=1, mode="nearest")
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    for i in range(size):
        for j in range(size):
            rgb[i, j] = encode_height(float(sampled[i, j]))
    return rgb


def generate_terrain_tiles(dem, lons, lats, out_dir, zmin=ZMIN, zmax=ZMAX):
    """为 (lons,lats) 覆盖范围生成 zmin..zmax 全部瓦片，返回瓦片数。"""
    out_dir = Path(out_dir)
    minlon, maxlon = float(lons[0]), float(lons[-1])
    minlat, maxlat = float(lats[-1]), float(lats[0])
    count = 0
    for z in range(zmin, zmax + 1):
        for z_, x, y in tiles_covering(minlon, minlat, maxlon, maxlat, z):
            rgb = render_tile(dem, lons, lats, z_, x, y)
            path = out_dir / str(z_) / str(x)
            path.mkdir(parents=True, exist_ok=True)
            plt.imsave(path / f"{y}.png", rgb)
            count += 1
    return count
```

注意 `render_tile` 的 Python 双重循环 256×256×~40 瓦片 ≈ 260 万次调用 encode_height——慢（分钟级）。向量化版本（执行时应采用）：

```python
    v = np.rint((sampled + 10000) * 10).astype(np.int32)
    rgb = np.stack(
        [(v >> 16) & 255, (v >> 8) & 255, v & 255], axis=-1
    ).astype(np.uint8)
```

把 encode/decode 作为标量函数保留给测试；render_tile 内部用向量化实现。

- [ ] **Step 3: build_data.py 接入 + .gitignore**

④ 高程段内 `build_elevation_products` 之后加：

```python
    from pipeline import terrain
    n_tiles = terrain.generate_terrain_tiles(
        dem_for_tiles, lons_for_tiles, lats_for_tiles,
        Path(out_dir).parent / "tiles" / "terrain-rgb",
    )
    print(f"[terrain] {n_tiles} 张 terrain-RGB 瓦片")
```

问题：build_elevation_products 目前不返回 dem/lons/lats。把它改为返回 `(contours, dem, lons, lats)`（同步改任务 6 的调用处与测试）。瓦片输出目录是 `cuhk/site/tiles/terrain-rgb/`（out_dir 是 site/data，取 parent/tiles/terrain-rgb）。

.gitignore 加一行：`cuhk/site/tiles/`

- [ ] **Step 4: app.js 地形联动**

style.json sources 加（app.js 里 addSource 也行，统一放 style.json）：

```json
    "dem": {
      "type": "raster-dem",
      "tiles": ["tiles/terrain-rgb/{z}/{x}/{y}.png"],
      "tileSize": 256,
      "encoding": "mapbox",
      "maxzoom": 16
    }
```

wire3DButton 的 click 处理加一行：

```javascript
    map.setTerrain(is3d ? { source: "dem", exaggeration: 1.2 } : null);
```

- [ ] **Step 5: 测试 + 管线重跑**

Run: `python -m pytest cuhk/tests -v`；`python cuhk/scripts/build_data.py`（应打印瓦片数，~30-60 张；校验全过）

- [ ] **Step 6: Commit**

```bash
git add cuhk/scripts/pipeline/terrain.py cuhk/tests/test_terrain.py cuhk/scripts/build_data.py cuhk/site/app.js cuhk/site/style.json .gitignore cuhk/scripts/pipeline/elevation.py
git commit -m "cuhk v2: terrain-RGB tiles + setTerrain on 3D toggle"
```

---

## 任务 V6：官方步行捷径图层

**Files:**
- Modify: `cuhk/site/style.json`
- 数据已在 V3 写出（walking.geojson）

- [ ] **Step 1: style.json 加 walking source + layer**

source：

```json
    "walking": { "type": "geojson", "data": "data/walking.geojson" }
```

layer（放在 roads-path 之后，保持可见）：

```json
    {
      "id": "walking",
      "type": "line",
      "source": "walking",
      "paint": {
        "line-color": "#4a8f52",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.2, 16, 2.5],
        "line-dasharray": [3, 2],
        "line-opacity": 0.9
      }
    }
```

- [ ] **Step 2: 校验 + Commit**

Run: `python -c "import json; json.load(open('cuhk/site/style.json',encoding='utf-8')); print('OK')"`

```bash
git add cuhk/site/style.json
git commit -m "cuhk v2: official walking shortcuts layer"
```

---

## 任务 V7：集成验证 + PR 更新

**Files:**
- Modify: `cuhk/scripts/pipeline/validate.py`（新增下限）
- Modify: `cuhk/README.md`（校巴模式/地形/官方数据源说明）
- Modify: `cuhk/site/index.html`（credit 行）
- Create: `cuhk/screenshots/v2-2d.png`、`v2-3d-terrain.png`、`v2-bus.png`

- [ ] **Step 1: validate.py 新增下限**

REQUIRED_MIN 增加：

```python
    "official_buildings": 200,
    "shuttle_routes": 10,
    "walking": 2,
```

注意 test_validate.py 的 good_gdfs() 需要同步补这三个图层（否则旧测试挂）：buildings 类合成数据各加对应数量。

- [ ] **Step 2: README 更新**

在「修改内容」后加：

```markdown
## 功能开关

- **校巴模式**：点顶栏「校巴線」显示/隐藏 19 条校巴线路（官方配色）与 51 个站点，点击看详情
- **3D 视角**：点顶栏「3D 視角」倾斜视角，建筑拉起 + 真实地形起伏（SRTM terrain-RGB）
- **URL 分享**：地址栏 hash 携带 zoom/lat/lon/pitch，可直接分享当前视角

## 数据来源

- 校园建筑/地标/校巴/步行捷径：© 香港中文大學官方校園地圖（cuhk.edu.hk）
- 校外与底图要素：© OpenStreetMap contributors (ODbL)
- 高程：NASA SRTM
```

- [ ] **Step 3: index.html credit 更新**

```html
<div id="credit">數據 © OpenStreetMap contributors · 校園建築/校巴 © CUHK 官方校園地圖 · 風格靈感來自 prettymaps</div>
```

- [ ] **Step 4: 全量回归 + 管线重跑**

```bash
python -m pytest cuhk/tests -v   # 全部通过（含新增测试）
python cuhk/scripts/build_data.py # 校验全过（含新下限）
```

- [ ] **Step 5: 三张截图（headless Edge CDP 法）**

复用 v1 的 CDP 截图法（`--remote-debugging-port` + 轮询 mapReady && map.loaded()）：

1. `v2-2d.png`：`http://localhost:8767/#14.6/22.4205/114.207`
2. `v2-3d-terrain.png`：`http://localhost:8767/#15.2/22.4205/114.207/0/55`（先临时把 buildings-3d 置 visible、buildings-2d 置 none + app.js 加初始 terrain？——不行，terrain 是按钮控制的。改法：CDP 里 evaluate `map.setTerrain({source:'dem',exaggeration:1.2}); map.setLayoutProperty('buildings-3d','visibility','visible'); map.setLayoutProperty('buildings-2d','visibility','none')` 后截图，不动代码）
3. `v2-bus.png`：CDP evaluate 打开校巴两层后截 `#14.8/22.4205/114.207`

人工（controller）Read 三张图核验：标记位置、校巴线路颜色、地形起伏、整体风格。

- [ ] **Step 6: Commit + 推送更新 PR**

```bash
git add cuhk/scripts/pipeline/validate.py cuhk/tests/test_validate.py cuhk/README.md cuhk/site/index.html cuhk/screenshots/v2-*.png
git commit -m "cuhk v2: integration validation, README, screenshots"
git push
```

在 PR #1 回复评论说明 6 条意见的处理方式与截图。

---

## 计划自审记录

**评论覆盖：** ①建筑名/位置 → V2；②捷径 → V6（+v1 已有 steps）；③校巴 → V3；④地形 → V5；⑤配色 → V4；⑥官方为准 → V1（数据源）+V2（POI 官方优先）✅
**类型一致性：** official 产品键名（official_buildings/shuttle_routes/shuttle_stops/walking）贯穿 V1→V3→V7；bt 值域（college/dorm/sports/study/other）贯穿 V4 代码与 style.json；terrain tiles 路径 `tiles/terrain-rgb/{z}/{x}/{y}.png` 贯穿 build_data.py 与 style.json dem source ✅
**风险点：** render_tile 向量化必须落实（避免 256²×40 次 Python 调用）；elevation.build_elevation_products 返回值变更需同步改既有调用与测试。
