from pathlib import Path

import geopandas as gp
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline import official, pois


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


def test_resolve_fuzzy_match_with_typo(features):
    entries = [
        {"id": "na", "name_zh": "新亚书院", "name_en": "New Asia College",
         "category": "life", "desc": "", "osm_name": "New Asia Collage"}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features)
    assert unmatched == []
    # 错拼仍模糊命中新亚书院，取面内代表点（box 质心）
    assert gdf.geometry.iloc[0].x == pytest.approx(114.2095)
    assert gdf.geometry.iloc[0].y == pytest.approx(22.4215)
    _, score = pois._match_feature("New Asia Collage", features)
    assert 0.55 < score < 1.0


def test_load_pois_missing_pois_key(tmp_path):
    yml = tmp_path / "nopois.yml"
    yml.write_text("other:\n  - id: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="缺少 pois"):
        pois.load_pois(yml)


def test_load_pois_blank_osm_name(tmp_path):
    yml = tmp_path / "blank.yml"
    yml.write_text(
        "pois:\n  - id: x\n    name_zh: 测试\n    name_en: Test\n"
        "    category: study\n    desc: d\n    osm_name: \"\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="osm_name"):
        pois.load_pois(yml)


def test_load_pois_bad_lonlat(tmp_path):
    non_numeric = tmp_path / "non_numeric.yml"
    non_numeric.write_text(
        "pois:\n  - id: x\n    name_zh: 测试\n    name_en: Test\n"
        "    category: study\n    desc: d\n    lon: \"abc\"\n    lat: 22.4\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="经纬度"):
        pois.load_pois(non_numeric)

    outside_hk = tmp_path / "outside_hk.yml"
    outside_hk.write_text(
        "pois:\n  - id: x\n    name_zh: 测试\n    name_en: Test\n"
        "    category: study\n    desc: d\n    lon: 120.0\n    lat: 30.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="经纬度"):
        pois.load_pois(outside_hk)


def test_resolve_prefers_official(features):
    official = gp.GeoDataFrame(
        {
            "name_en": ["New Asia College"],
            "name_zh": ["新亞書院"],
            "geometry": [box(114.2000, 22.4100, 114.2010, 22.4110)],
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
    assert gdf.iloc[0]["source"] == "official"
    # 官方坐标与 OSM fixture 不同：命中点必须来自官方要素的面内代表点（box 质心）
    assert gdf.geometry.iloc[0].x == pytest.approx(114.2005)
    assert gdf.geometry.iloc[0].y == pytest.approx(22.4105)


def test_resolve_empty_official_falls_back_to_osm(features):
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


def test_resolve_below_threshold_official_falls_back_to_osm(features):
    official = gp.GeoDataFrame(
        {
            "name_en": ["Something Else Entirely"],
            "name_zh": ["完全不相干"],
            "geometry": [box(114.2000, 22.4100, 114.2010, 22.4110)],
        },
        crs="EPSG:4326",
    )
    entries = [
        {"id": "na", "name_zh": "新亞書院", "name_en": "New Asia College",
         "category": "life", "desc": "", "official_name": "No Such Place Zzz",
         "osm_name": "New Asia College"}
    ]
    gdf, unmatched = pois.resolve_pois(entries, features, official=official)
    assert unmatched == []
    # 官方库里有不相关名字但相似度低于阈值 → 回落 OSM
    assert gdf.iloc[0]["source"] == "osm"
    assert gdf.geometry.iloc[0].x == pytest.approx(114.2095)


def test_validate_official_pairs_rejects_crossed_bilingual_name():
    entries = [{
        "id": "elb",
        "name_zh": "伍何曼原樓",
        "name_en": "Esther Lee Building",
        "official_name": "Esther Lee Building",
    }]
    official_names = pd.DataFrame({
        "name_en": ["Esther Lee Building"],
        "name_zh": ["利黃瑤璧樓"],
    })

    with pytest.raises(ValueError, match="elb.*利黃瑤璧樓"):
        pois.validate_official_pairs(entries, official_names)


def test_real_pois_use_matching_official_chinese_names():
    entries = pois.load_pois(Path(__file__).resolve().parents[1] / "data" / "pois.yml")
    db = official.load_official_db()
    official_names = pd.concat([
        official.official_buildings(db)[["name_en", "name_zh"]],
        official.official_landmarks(db)[["name_en", "name_zh"]],
        official.official_colleges(db)[["name_en", "name_zh"]],
        official.official_facilities(db)[["name_en", "name_zh"]],
        official.shuttle_stops(db)[["name_en", "name_zh"]],
    ], ignore_index=True)

    pois.validate_official_pairs(entries, official_names)


def test_transport_pois_use_official_exit_and_interchange_points():
    entries = {
        entry["id"]: entry
        for entry in pois.load_pois(Path(__file__).resolve().parents[1] / "data" / "pois.yml")
    }

    assert entries["university-station-north"]["official_name"] == "University MTR Station (Northern Exit)"
    assert entries["university-station-west"]["official_name"] == "University MTR Station (Western Exit)"
    assert entries["bus-terminus"]["name_zh"] == "大學站公共運輸交匯處"
    assert entries["bus-terminus"]["lon"] == pytest.approx(114.21080678701401)
    assert entries["bus-terminus"]["lat"] == pytest.approx(22.412917985947334)
