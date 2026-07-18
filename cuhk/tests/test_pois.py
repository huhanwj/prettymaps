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
