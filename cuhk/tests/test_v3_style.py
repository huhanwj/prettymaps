import json
from pathlib import Path


CUHK = Path(__file__).resolve().parents[1]
STYLE_PATH = CUHK / "site" / "style.json"
INDEX_PATH = CUHK / "site" / "index.html"
APP_PATH = CUHK / "site" / "app.js"
README_PATH = CUHK / "README.md"
KNOWN_ISSUES_PATH = CUHK / "KNOWN_ISSUES.md"


def _style():
    return json.loads(STYLE_PATH.read_text(encoding="utf-8"))


def _layer(style, layer_id):
    return next(layer for layer in style["layers"] if layer["id"] == layer_id)


def test_v3_uses_white_background_and_official_road_blue():
    style = _style()
    assert _layer(style, "background")["paint"]["background-color"] == "#FFFFFF"
    assert _layer(style, "green")["paint"]["fill-color"] == "#FFFFFF"
    assert _layer(style, "forest")["paint"]["fill-color"] == "#FFFFFF"
    assert _layer(style, "roads-minor")["paint"]["line-color"] == "#A5BFD2"
    assert _layer(style, "roads-major")["paint"]["line-color"] == "#A5BFD2"


def test_v3_restores_separate_sports_surfaces():
    style = _style()
    assert style["sources"]["sports"]["data"] == "data/sports.geojson"
    assert _layer(style, "sports-fields")["paint"]["fill-color"] == "#DCE8C8"
    assert _layer(style, "sports-tracks")["paint"]["fill-color"] == "#EFC7B8"


def test_v3_building_palette_covers_all_official_campus_ids():
    style = _style()
    expression = _layer(style, "buildings-2d")["paint"]["fill-color"]
    serialized = json.dumps(expression)
    for campus_id in map(str, range(1, 14)):
        assert f'"{campus_id}"' in serialized
    for color in ("#C396C5", "#F59288", "#7ED3F7", "#59C5C2", "#FBB04C", "#4069B2"):
        assert color in serialized


def test_v3_has_distinct_bridge_and_stair_layers():
    style = _style()
    assert style["sources"]["pedestrian_links"]["data"] == "data/pedestrian_links.geojson"
    bridge = _layer(style, "pedestrian-bridges")
    stairs = _layer(style, "pedestrian-stairs")
    assert bridge["filter"] == ["==", ["get", "kind"], "bridge"]
    assert stairs["filter"] == ["==", ["get", "kind"], "stairs"]
    assert "line-dasharray" not in bridge["paint"]
    assert stairs["paint"]["line-dasharray"]


def test_v3_keeps_ordinary_paths_solid_and_reserves_dashes_for_pdf_stairs():
    style = _style()
    paths = _layer(style, "roads-path")
    assert paths["filter"] == ["==", ["get", "road_class"], "path"]
    assert "line-dasharray" not in paths["paint"]


def test_v3_hides_3d_and_exposes_bus_selector_and_link_legend():
    style = _style()
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert _layer(style, "buildings-3d")["layout"]["visibility"] == "none"
    assert 'id="btn3d"' not in html
    assert 'id="busRouteSelect"' in html
    assert "天橋" in html and "樓梯" in html
    assert "wire3DButton()" not in app
    assert "green-hatch" not in app


def test_v3_terrain_is_optional_and_has_conditional_legend():
    style = _style()
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert _layer(style, "contours")["layout"]["visibility"] == "none"
    assert 'id="btnTerrain"' in html
    assert 'id="terrain-legend"' in html
    assert "terrain-tint.png" in app
    assert "hillshade.png" not in app
    assert "setTerrain(" not in app


def test_v3_records_deferred_3d_freeze_as_known_issue():
    assert KNOWN_ISSUES_PATH.exists()
    issue = KNOWN_ISSUES_PATH.read_text(encoding="utf-8").lower()
    readme = README_PATH.read_text(encoding="utf-8")
    assert "3d" in issue and "unfixed" in issue and "deferred" in issue
    assert "切回" in issue and "卡" in issue
    assert "KNOWN_ISSUES.md" in readme
    assert "**3D 視角**" not in readme
