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
{"bus_route_seg_id":"1", "start_bus_stop_id":"2", "end_bus_stop_id":"3", "encoded_line":"SS{@oA"},
{"bus_route_seg_id":"2", "start_bus_stop_id":"1", "end_bus_stop_id":"2", "encoded_line":"g@{@{@{@oA{@"},
],
shuttle_bus_stops : [
{"bus_stop_id":"1", "bus_stop_name_en":"University Station", "bus_stop_name_xb5":"港鐵大學站", "lat_lng":"(22.4100, 114.2100)"},
{"bus_stop_id":"2", "bus_stop_name_en":"Sports Centre", "bus_stop_name_xb5":"大學體育中心", "lat_lng":"(22.4110, 114.2110)"},
{"bus_stop_id":"3", "bus_stop_name_en":"NA College", "bus_stop_name_xb5":"新亞書院", "lat_lng":"(22.4120, 114.2120)"},
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
    # seg 折线锚定其 start 站：order=1 的 seg2（锚 stop1）应排在 order=2 的 seg1（锚 stop2）前
    # seg2 "g@{@{@{@oA{@" 解码相对点 (0.0002,0.0003),(0.0005,0.0006),(0.0009,0.0009)
    line0 = row.geometry.geoms[0]
    flat0 = [c for pt in line0.coords for c in pt]
    assert flat0 == pytest.approx(
        [114.2103, 22.4102, 114.2106, 22.4105, 114.2109, 22.4109], abs=1e-6
    )
    # seg1 "SS{@oA" 锚 stop2 (22.4110, 114.2110)，相对点 (0.0001,0.0001),(0.0004,0.0005)
    line1 = row.geometry.geoms[1]
    flat1 = [c for pt in line1.coords for c in pt]
    assert flat1 == pytest.approx([114.2111, 22.4111, 114.2115, 22.4114], abs=1e-6)


def test_walking_routes():
    db = official.parse_map_data(SAMPLE_JS)
    gdf = official.walking_routes(db)
    assert len(gdf) == 1
    assert len(gdf.iloc[0].geometry.coords) == 3


def test_decode_polyline_malformed_raises_valueerror():
    with pytest.raises(ValueError, match="截断/非法"):
        official.decode_polyline("_p~iF")  # 只有 lat 缺 lng，截断


def test_shuttle_anchor_prefers_encoded_start_pt():
    """锚点级联：encoded_start_pt（绝对编码单点）优先于 start_bus_stop。"""
    db = {
        "shuttle_bus_route": [
            {"route_id": "1", "route_name_en": "R", "route_name_xb5": "", "route_color": "#000000"},
        ],
        "shuttle_bus_route_seg": [{"route_id": "1", "seg_id": "1", "order": "1"}],
        "shuttle_bus_seg": [{
            "bus_route_seg_id": "1", "start_bus_stop_id": "9", "end_bus_stop_id": "",
            "encoded_start_pt": "ksxgCkpaxT",  # 绝对点 (22.4135, 114.2095)
            "encoded_line": "SS{@oA",  # 相对点 (0.0001,0.0001),(0.0004,0.0005)
        }],
        "shuttle_bus_stops": [
            {"bus_stop_id": "9", "bus_stop_name_en": "S", "bus_stop_name_xb5": "", "lat_lng": "(22.4000, 114.2000)"},
        ],
    }
    gdf = official.shuttle_routes(db)
    flat = [c for pt in gdf.iloc[0].geometry.geoms[0].coords for c in pt]
    # 锚 encoded_start_pt → (114.2096,22.4136),(114.2100,22.4139)；若错锚 stop9 则全在 (114.2,22.4) 附近
    assert flat == pytest.approx([114.2096, 22.4136, 114.2100, 22.4139], abs=1e-6)


def test_shuttle_seg_unanchorable_warns():
    """无 encoded_start_pt 且 start 站缺失 → warnings.warn 跳过；路线因此为空则不产出。"""
    db = {
        "shuttle_bus_route": [{"route_id": "1", "route_name_en": "R", "route_name_xb5": "", "route_color": ""}],
        "shuttle_bus_route_seg": [{"route_id": "1", "seg_id": "1", "order": "1"}],
        "shuttle_bus_seg": [
            {"bus_route_seg_id": "1", "start_bus_stop_id": "X", "end_bus_stop_id": "", "encoded_line": "SS{@oA"},
        ],
        "shuttle_bus_stops": [],
    }
    with pytest.warns(UserWarning, match="无法定位"):
        gdf = official.shuttle_routes(db)
    assert len(gdf) == 0  # 空 GeoDataFrame 也不炸
    assert "geometry" in gdf.columns


def test_empty_layers_no_crash():
    """空输入 → 带列结构的空 GeoDataFrame，不报错。"""
    assert len(official.official_buildings({})) == 0
    assert len(official.official_landmarks({})) == 0
    assert len(official.official_colleges({})) == 0
    assert len(official.shuttle_routes({})) == 0
    assert len(official.walking_routes({})) == 0
    assert list(official.shuttle_stops({}).columns) == ["name_en", "name_zh", "geometry"]


def test_shuttle_real_file_lands_on_campus():
    """真实存档回归：shuttle seg 锚定 encoded_start_pt 后，所有坐标须落在中大及周边 bbox。"""
    db = official.load_official_db()
    gdf = official.shuttle_routes(db)
    assert len(gdf) == 19
    for geom in gdf.geometry:
        for line in geom.geoms:
            for x, y in line.coords:
                assert 114.19 <= x <= 114.23, f"lon out of range: {x}"
                assert 22.40 <= y <= 22.44, f"lat out of range: {y}"
    # 真实文件 19 条 shuttle 路线全部带显式 route_color，无 #2F3737 回退
    assert (gdf["color"] != "").all()
    assert (gdf["color"] != "#2F3737").all()


def test_real_file_products_smoke(recwarn):
    """真实存档冒烟：各图层计数 + encoded_start_pt 全覆盖（零跳过告警）。"""
    db = official.load_official_db()
    p = official.build_official_products(db)
    counts = {k: len(v) for k, v in p.items()}
    assert counts == {
        "official_buildings": 159,
        "official_landmarks": 26,
        "official_colleges": 9,
        "shuttle_routes": 19,
        "shuttle_stops": 51,
        "walking": 2,
    }
    skips = [w for w in recwarn.list if "无法定位" in str(w.message)]
    assert skips == []


def test_official_poi_sources_combines_layers():
    """POI 校正合集 = buildings + landmarks + colleges + shuttle_stops，列齐。"""
    db = {
        "buildings": [
            {"bldg_name_en": "B1", "bldg_name_xb5": "樓一", "lat_lng": "(22.41, 114.20)"},
            {"bldg_name_en": "B2", "bldg_name_xb5": "樓二", "lat_lng": "(22.42, 114.21)"},
        ],
        "landmarks": [
            {"landmark_name_en": "L1", "landmark_name_xb5": "標一", "lat_lng": "(22.43, 114.22)"},
        ],
        "colleges": [
            {"name_en": "C1", "name_xb5": "院一", "lat_lng": "(22.44, 114.23)"},
        ],
        "shuttle_bus_stops": [
            {"bus_stop_name_en": "S1", "bus_stop_name_xb5": "站一", "lat_lng": "(22.45, 114.24)"},
            {"bus_stop_name_en": "S2", "bus_stop_name_xb5": "站二", "lat_lng": "(22.46, 114.25)"},
            {"bus_stop_name_en": "S3", "bus_stop_name_xb5": "站三", "lat_lng": "(22.47, 114.26)"},
        ],
    }
    gdf = official.official_poi_sources(db)
    assert len(gdf) == 2 + 1 + 1 + 3
    assert set(gdf.columns) >= {"name_en", "name_zh", "geometry"}
    assert gdf.crs.to_string() == "EPSG:4326"
