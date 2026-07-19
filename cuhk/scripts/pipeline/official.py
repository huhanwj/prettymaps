"""CUHK 官方校园地图数据集（CUHK_MAP_DATA）解析。

数据源：https://www.cuhk.edu.hk/english/js/campus/cuhk_location_db.js
文件以 cuhk/data/official/cuhk_location_db.js 存档（可复现、可离线）。
解析策略：定位各顶层 `key : [` 数组段，括号配平（字符串感知）切出每条 JSON 记录。
折线为 Google encoded polyline（shuttle_bus_seg.encoded_line / walking_route.ecoded_line）。
注意：walking 折线为绝对编码；shuttle seg 折线为相对其 start_bus_stop 站点的
增量编码（实测验证：独立解码落点全在 (0,0) 附近，锚定站点后落点与站点吻合）。
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
    """按 route_id 组装有序 seg 折线 → MultiLineString。

    seg 折线是相对其 start_bus_stop 的增量编码：优先锚定该站坐标；
    start 站缺失时锚定上一 seg 终点（链式）；首 seg 且无站可锚则跳过并告警。
    """
    segs = {s["bus_route_seg_id"]: s for s in db["shuttle_bus_seg"]}
    stops = {s["bus_stop_id"]: s for s in db["shuttle_bus_stops"]}
    order = {}
    for r in db["shuttle_bus_route_seg"]:
        order.setdefault(r["route_id"], []).append((int(r["order"]), r["seg_id"]))

    rows = []
    for route in db["shuttle_bus_route"]:
        rid = route["route_id"]
        lines = []
        prev_end = None  # 上一 seg 终点 (lat, lng)，作链式锚
        for _, seg_id in sorted(order.get(rid, [])):
            seg = segs.get(seg_id)
            if not seg or not seg.get("encoded_line"):
                continue
            pts = decode_polyline(seg["encoded_line"])  # 相对 (0,0) 的增量
            anchor = None
            stop = stops.get(seg.get("start_bus_stop_id", ""))
            if stop:
                ll = parse_lat_lng(stop.get("lat_lng"))  # → (lng, lat)
                if ll is not None:
                    anchor = (ll[1], ll[0])
            if anchor is None:
                anchor = prev_end
            if anchor is None:
                print(f"[official] 警告：route {rid} seg {seg_id} 无法定位，已跳过")
                continue
            abs_pts = [(anchor[0] + lat, anchor[1] + lng) for lat, lng in pts]
            prev_end = abs_pts[-1]
            if len(abs_pts) >= 2:
                lines.append(LineString([(lng, lat) for lat, lng in abs_pts]))
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
