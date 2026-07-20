import json
from pathlib import Path


CUHK = Path(__file__).resolve().parents[1]
STYLE_PATH = CUHK / "site" / "style.json"
INDEX_PATH = CUHK / "site" / "index.html"
APP_PATH = CUHK / "site" / "app.js"
BUILD_DATA_PATH = CUHK / "scripts" / "build_data.py"
README_PATH = CUHK / "README.md"
KNOWN_ISSUES_PATH = CUHK / "KNOWN_ISSUES.md"


def _style():
    return json.loads(STYLE_PATH.read_text(encoding="utf-8"))


def _layer(style, layer_id):
    return next(layer for layer in style["layers"] if layer["id"] == layer_id)


def test_v3_uses_tijuca_palette_except_for_college_buildings():
    style = _style()
    assert _layer(style, "background")["paint"]["background-color"] == "#FFFFFF"
    assert _layer(style, "green")["paint"]["fill-color"] == "#72C07A"
    assert _layer(style, "forest")["paint"]["fill-color"] == "#72C07A"
    assert _layer(style, "water")["paint"]["fill-color"] == "#6CCFF6"
    assert _layer(style, "beach")["paint"]["fill-color"] == "#F2E3BC"
    assert _layer(style, "roads-minor")["paint"]["line-color"] == "#898989"
    assert _layer(style, "roads-major")["paint"]["line-color"] == "#898989"


def test_v3_restores_separate_sports_surfaces():
    style = _style()
    assert style["sources"]["sports"]["data"] == "data/sports.geojson"
    assert _layer(style, "sports-fields")["paint"]["fill-color"] == "#DCE8C8"
    assert _layer(style, "sports-tracks")["paint"]["fill-color"] == "#EFC7B8"
    assert _layer(style, "sports-pools")["filter"] == ["==", ["get", "sports_kind"], "pool"]
    assert _layer(style, "sports-pools")["paint"]["fill-color"] == "#B9E3F2"
    layer_ids = [layer["id"] for layer in style["layers"]]
    assert layer_ids.index("sports-tracks") < layer_ids.index("sports-fields")


def test_v3_building_palette_covers_all_official_campus_ids():
    style = _style()
    expression = _layer(style, "buildings-2d")["paint"]["fill-color"]
    serialized = json.dumps(expression)
    for campus_id in map(str, range(1, 14)):
        assert f'"{campus_id}"' in serialized
    for color in ("#C396C5", "#F59288", "#7ED3F7", "#59C5C2", "#FBB04C", "#4069B2"):
        assert color in serialized


def test_v3_has_distinct_osm_bridge_and_stair_layers():
    style = _style()
    bridge = _layer(style, "pedestrian-bridges")
    stairs = _layer(style, "pedestrian-stairs")
    assert bridge["source"] == "roads"
    assert stairs["source"] == "roads"
    assert bridge["filter"] == ["==", ["get", "pedestrian_kind"], "bridge"]
    assert stairs["filter"] == ["==", ["get", "pedestrian_kind"], "stairs"]
    assert "line-dasharray" not in bridge["paint"]
    assert stairs["paint"]["line-dasharray"]


def test_v3_keeps_ordinary_paths_solid_and_separate_from_osm_links():
    style = _style()
    paths = _layer(style, "roads-path")
    assert paths["filter"] == ["==", ["get", "pedestrian_kind"], "path"]
    assert "line-dasharray" not in paths["paint"]


def test_v3_removes_ambiguous_grey_dashed_overlays():
    style = _style()
    layer_ids = {layer["id"] for layer in style["layers"]}
    assert "walking" not in layer_ids
    assert "boundary" not in layer_ids
    assert "line-dasharray" not in _layer(style, "railway")["paint"]
    assert _layer(style, "railway-center")["paint"]["line-color"] == "#FFFFFF"


def test_v3_hides_3d_and_exposes_bus_selector_and_link_legend():
    style = _style()
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert _layer(style, "buildings-3d")["layout"]["visibility"] == "none"
    assert 'id="btn3d"' not in html
    assert 'id="busRouteSelect"' in html
    assert 'id="bus-route-info"' in html
    assert "天橋" in html and "樓梯" in html
    assert "wire3DButton()" not in app


def test_v3_uses_collision_managed_labels_instead_of_category_zoom_hiding():
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert "body.z-mid .poi-marker.cat-landmark" not in html
    assert "selectNonOverlappingLabels" in app
    assert "updateZoomClass" not in app


def test_v3_has_no_general_poi_dots_or_category_chips():
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert 'class="chip"' not in html
    assert ".poi-marker" not in html
    assert "addPOIMarkers" not in app
    assert 'loadJSON("data/pois.geojson")' not in app
    assert "addOfficialBuildingLabels(officialBuildings)" in app


def test_v3_adds_tijuca_surface_hatches():
    app = APP_PATH.read_text(encoding="utf-8")
    assert 'addSurfaceHatch("green-hatch", "green", "#64a38d"' in app
    assert 'addSurfaceHatch("forest-hatch", "forest", "#64a38d"' in app
    assert 'addSurfaceHatch("water-hatch", "water", "#59adcf"' in app


def test_v3_loads_zoom_progressive_official_building_labels():
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert "official_buildings.geojson" in app
    assert "addOfficialBuildingLabels" in app
    assert "buildingLabelsEnabled" in app
    assert "labelCollisionPadding" in app
    assert ".building-label-marker" in html


def test_v3_constrains_viewport_and_hides_internal_shuttle_ids():
    app = APP_PATH.read_text(encoding="utf-8")
    assert "const CUHK_MAX_BOUNDS" in app
    assert "zoom: 15" in app
    assert "minZoom: 14.8" in app
    assert "maxBounds: CUHK_MAX_BOUNDS" in app
    assert "renderWorldCopies: false" in app
    assert "CUHKAppCore.routeGroups" in app
    assert "線路 ${" not in app


def test_v3_splits_regular_and_conditional_shuttle_paths():
    style = _style()
    regular = _layer(style, "shuttle-routes")
    conditional = _layer(style, "shuttle-route-variants")
    assert regular["filter"] == ["==", ["get", "is_conditional"], False]
    assert conditional["filter"] == ["==", ["get", "is_conditional"], True]
    assert conditional["paint"]["line-dasharray"]


def test_v3_uses_public_route_ids_and_renders_service_conditions():
    app = APP_PATH.read_text(encoding="utf-8")
    assert "sourceRouteIds" not in app
    assert "routeConditions" in app
    assert "shuttle-route-variants" in app


def test_v3_exposes_interactive_route_recorder():
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    assert 'id="btnRecordRoute"' in html
    assert 'id="route-recorder"' in html
    assert 'id="recorderUndo"' in html
    assert 'id="recorderExport"' in html
    assert "recording-stop-candidates" in app
    assert "routeRecordingGeoJSON" in app
    assert ".route-recording-active .building-label-marker" in html
    assert 'classList.toggle("route-recording-active"' in app


def test_v3_refreshes_map_source_from_uncached_shuttle_data():
    app = APP_PATH.read_text(encoding="utf-8")
    assert 'fetch(url, { cache: "no-store" })' in app
    assert 'getSource("shuttle_routes").setData(shuttleRoutesGeoJSON)' in app


def test_v3_can_overlay_recorded_points_for_visual_review():
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    build_data = BUILD_DATA_PATH.read_text(encoding="utf-8")
    assert 'get("recordingPreview")' in app
    assert 'cuhk-shuttle-${routeId}-recording.json' in app
    assert "showRecordingPreviewFromQuery" in app
    assert 'glob("cuhk-shuttle-*-recording.json")' in build_data
    assert 'app-core.js?v=20260720-tijuca-3' in html
    assert 'app.js?v=20260720-tijuca-3' in html
    assert 'map.setLayoutProperty("route-recording-line", "visibility", "none");' in app


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
