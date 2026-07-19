# CUHK Public Shuttle Route Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and display the twelve current CUHK public shuttle routes from audited stop sequences instead of mapping them to archived route IDs 1-19.

**Architecture:** A curated YAML file defines public routes, stop sequences, conditional branches, and forbidden stops. A focused Python module builds a routable graph from the motor-road layer, snaps stops and waypoints, and emits public route/stop GeoDataFrames. The frontend filters the generated public identifiers directly and styles conditional branches separately.

**Tech Stack:** Python 3.12, GeoPandas, Shapely, NetworkX, PyYAML, MapLibre GL JS, Node assert, pytest.

---

## File structure

- Create `cuhk/data/shuttle_routes.yml`: audited public route catalog, stop coordinates, ordered sequences, variants, and forbidden stops.
- Create `cuhk/scripts/pipeline/shuttle.py`: road graph construction, snapping, shortest-path assembly, validation, and GeoDataFrame output.
- Modify `cuhk/scripts/build_data.py`: build public shuttle products after OSM roads and official DB are loaded; export variant fields.
- Modify `cuhk/scripts/pipeline/official.py`: keep archived parsing utilities but stop publishing archived shuttle routes/stops from `build_official_products`.
- Create `cuhk/tests/test_shuttle.py`: focused unit and real-data route constraint tests.
- Modify `cuhk/tests/test_official.py`: update official-product expectations so archived shuttle data is no longer a frontend product.
- Modify `cuhk/site/app-core.js`: filter public `route_id` values directly and expose conditional branch labels.
- Modify `cuhk/site/app.js`: render public route information and conditional variants without archived-ID mappings.
- Modify `cuhk/site/style.json`: add a dashed conditional-route layer and keep arrows on both base and conditional geometry.
- Modify `cuhk/tests/js/test_app_core.js`: lock public filtering and route catalog behavior.

### Task 1: Curated public route definitions

**Files:**
- Create: `cuhk/data/shuttle_routes.yml`
- Test: `cuhk/tests/test_shuttle.py`

- [ ] **Step 1: Write the failing catalog test**

```python
from pathlib import Path

from pipeline import shuttle


CONFIG = Path(__file__).parents[1] / "data" / "shuttle_routes.yml"


def test_public_route_catalog_and_explicit_constraints():
    config = shuttle.load_config(CONFIG)
    routes = config["routes"]
    assert list(routes) == ["1A", "1B", "2", "3", "4", "8", "5", "6A", "6B", "7", "N", "H"]
    assert "postgraduate_hall_1" in routes["1B"]["stops"]
    assert "residence_10" not in routes["3"]["stops"]
    assert routes["4"]["stops"].index("cw_chu_down") < routes["4"]["stops"].index("area_39_up")
    assert routes["5"]["stops"][-1] == "cw_chu_down"
    assert routes["5"]["departures"] == [18, 22, 26]
    assert routes["6A"]["stops"][0] == "cw_chu_down"
    assert routes["6B"]["stops"][-2:] == ["station_piazza", "chung_chi_teaching"]
    assert routes["7"]["stops"][-2:] == ["station_piazza", "chung_chi_teaching"]
    assert "residence_10" not in routes["N"]["stops"]
    assert routes["H"]["stops"][0] == "residence_10"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:UV_CACHE_DIR='J:\work\prettymaps\.uv-cache'
$env:UV_PYTHON_INSTALL_DIR='J:\work\prettymaps\.uv-python'
uv run --offline --with-requirements cuhk\requirements.txt python -m pytest cuhk\tests\test_shuttle.py::test_public_route_catalog_and_explicit_constraints -q --basetemp=J:\work\prettymaps\.pytest-cuhk-shuttle
```

Expected: FAIL because `pipeline.shuttle` and the YAML catalog do not exist.

- [ ] **Step 3: Create the audited YAML catalog**

Define named stops with `official_stop_id` where available and explicit `[longitude, latitude]` only for current stops not represented by the archived stop table. Define these route sequences from the current Transport Office diagrams:

```yaml
routes:
  1A:
    stops: [shaw_hall, sports_centre, admin_building, sh_ho, university_station]
  1B:
    stops: [shaw_hall, sports_centre, postgraduate_hall_1, admin_building, sh_ho, postgraduate_hall_1, university_station]
  2:
    stops: [united_up, fung_king_hey, sports_centre, new_asia, united_down, admin_building, sh_ho, station_piazza, university_station]
    variants:
      - id: minute_45_00_shaw_hall
        condition_zh: 逢45及00分班次停邵逸夫堂
        condition_en: Departures at minutes 45 and 00 serve Sir Run Run Shaw Hall
        insert_after: {fung_king_hey: shaw_hall}
  3:
    stops: [cw_chu_down, shaw_up, wu_yee_sun_up, fung_king_hey, science_centre, sports_centre, residence_15, uc_staff_residence, chan_chun_ha, shaw_down, wu_yee_sun_down, admin_building, sh_ho, yiap, station_piazza]
    forbidden_stops: [residence_10]
  4:
    stops: [uc_staff_residence, residence_15, cw_chu_down, area_39_up, cw_chu_up, circuit_east_up, chan_chun_ha, shaw_down, wu_yee_sun_down, new_asia, united_down, admin_building, sh_ho, yiap, university_station]
  8:
    stops: [new_asia_circle, science_centre, admin_building, wu_yee_sun_down, shaw_down, chan_chun_ha, uc_staff_residence, cw_chu_down, united_down, wu_yee_sun_up, shaw_up, area_39_down, circuit_north, circuit_east_down, university_station]
    variants:
      - id: non_teaching_terminal
        condition_zh: 非教学日停大学站广场及崇基教学楼，不停大学站
        condition_en: Non-teaching days serve Station Piazza and Chung Chi Teaching Building instead of University Station
        replace_tail: {from: circuit_east_down, with: [station_piazza, area_39_up, chung_chi_teaching]}
  5:
    departures: [18, 22, 26]
    stops: [chung_chi_teaching, sports_centre, shaw_hall, fung_king_hey, united_up, new_asia, wu_yee_sun_down, chan_chun_ha, uc_staff_residence, cw_chu_down]
  6A:
    stops: [cw_chu_down, uc_staff_residence, chan_chun_ha, wu_yee_sun_down, new_asia, united_down, admin_building, sh_ho, station_piazza, chung_chi_teaching]
  6B:
    stops: [new_asia, united_down, admin_building, sh_ho, station_piazza, chung_chi_teaching]
  7:
    stops: [shaw_down, wu_yee_sun_down, new_asia, united_down, admin_building, sh_ho, station_piazza, chung_chi_teaching]
  N:
    stops: [cw_chu_down, area_39_up, shaw_up, wu_yee_sun_up, united_down, new_asia_circle, shaw_hall, sports_centre, residence_15, uc_staff_residence, chan_chun_ha, shaw_down, wu_yee_sun_down, new_asia, united_down, admin_building, sh_ho, university_station]
    forbidden_stops: [residence_10]
    variants:
      - id: minute_00_pgh1
        condition_zh: 逢00分班次停研究生宿舍一座
        condition_en: Departures at minute 00 serve Postgraduate Hall 1
        insert_after: {sports_centre: postgraduate_hall_1, sh_ho: postgraduate_hall_1}
  H:
    stops: [residence_10, cw_chu_down, shaw_up, wu_yee_sun_up, united_down, new_asia_circle, shaw_hall, sports_centre, residence_15, uc_staff_residence, chan_chun_ha, shaw_down, wu_yee_sun_down, new_asia, united_down, admin_building, sh_ho, university_station]
    variants:
      - id: minute_00_area39_pgh1
        condition_zh: 逢00分班次停39区及研究生宿舍一座
        condition_en: Departures at minute 00 serve Area 39 and Postgraduate Hall 1
        insert_after: {cw_chu_down: area_39_up, sports_centre: postgraduate_hall_1, sh_ho: postgraduate_hall_1}
```

Add bilingual metadata and one stable display color to every route. Do not define any archived route ID.

- [ ] **Step 4: Implement `load_config` with schema validation**

```python
def load_config(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if list(data.get("routes", {})) != PUBLIC_ROUTE_IDS:
        raise ValueError("public shuttle route order must match the approved catalog")
    for route_id, route in data["routes"].items():
        if len(route.get("stops", [])) < 2:
            raise ValueError(f"route {route_id}: at least two ordered stops are required")
    return data
```

- [ ] **Step 5: Run the focused test and verify GREEN**

Expected: one passing test.

### Task 2: Road-graph route generation

**Files:**
- Modify: `cuhk/scripts/pipeline/shuttle.py`
- Test: `cuhk/tests/test_shuttle.py`

- [ ] **Step 1: Write failing graph and route tests**

Create a small road network with a forbidden spur and assert that `build_route_geometry` follows ordered waypoints, preserves direction, and never enters the spur. Add a disconnected-road test expecting `ValueError("route X: no road path from A to B")`.

```python
import geopandas as gp
from shapely.geometry import LineString, Point


def sample_roads_with_residence_10_spur():
    return gp.GeoDataFrame(
        {"road_class": ["minor", "minor", "minor"]},
        geometry=[
            LineString([(0, 0), (2, 0)]),
            LineString([(2, 0), (4, 0)]),
            LineString([(2, 0), (2, 1)]),
        ],
        crs="EPSG:32650",
    )


def test_ordered_route_avoids_unrequested_spur():
    roads = sample_roads_with_residence_10_spur()
    stops = {"start": Point(0, 0), "middle": Point(2, 0), "end": Point(4, 0)}
    line = shuttle.build_route_geometry("X", ["start", "middle", "end"], stops, roads)
    assert list(line.coords)[0] == (0, 0)
    assert list(line.coords)[-1] == (4, 0)
    assert line.distance(Point(2, 1)) > 0.5
```

- [ ] **Step 2: Run the focused tests and verify RED**

Expected: FAIL because graph generation is missing.

- [ ] **Step 3: Implement the minimal graph builder**

Project roads to EPSG:32650, exclude `road_class` values `path` and `steps`, split every line into consecutive coordinate-pair edges, and add both directions to a `networkx.MultiDiGraph`. Store edge geometry and metric length. Snap each stop/waypoint to the nearest graph node using a Shapely `STRtree`; reject snaps over the configured maximum distance.

- [ ] **Step 4: Implement ordered path assembly**

For each consecutive stop pair, run weighted shortest path, orient edge coordinates, remove duplicated junction coordinates, and concatenate. Include the exact route ID and stop names in all errors. Convert back to EPSG:4326 only after route validation.

- [ ] **Step 5: Build route and stop GeoDataFrames**

Return route features with `route_id`, bilingual names, `color`, `variant`, bilingual conditions, `is_conditional`, and geometry. Return one stop feature per named stop with `route_ids` containing public identifiers only.

- [ ] **Step 6: Run focused tests and verify GREEN**

Expected: all `test_shuttle.py` unit tests pass.

### Task 3: Pipeline integration and real-route regression tests

**Files:**
- Modify: `cuhk/scripts/build_data.py`
- Modify: `cuhk/scripts/pipeline/official.py`
- Modify: `cuhk/tests/test_official.py`
- Modify: `cuhk/tests/test_shuttle.py`

- [ ] **Step 1: Write failing real-data tests**

Build products from cached roads, official stops, and the curated catalog. Assert exactly twelve route IDs, continuous geometry, public-only stop memberships, and the approved route constraints. Use projected distance checks for forbidden stops and ordered-point projection checks for route 4, 6B, and 7.

- [ ] **Step 2: Run the real-data tests and verify RED**

Expected: FAIL because `build_data.py` still publishes archived route products.

- [ ] **Step 3: Integrate public route generation**

Load official non-shuttle products first, then call:

```python
shuttle_products = shuttle.build_products(
    roads=gdfs["roads"],
    official_db=db,
    config_path=REPO_CUHK / "data" / "shuttle_routes.yml",
)
gdfs.update(shuttle_products)
```

Remove archived `shuttle_routes` and `shuttle_stops` from `official.build_official_products`. Preserve the archived parsing functions for tests and reference only.

- [ ] **Step 4: Export variant fields**

Add `variant`, `condition_zh`, `condition_en`, and `is_conditional` to the `shuttle_routes` keep list in `build_data.py`.

- [ ] **Step 5: Generate site data from cache**

Run `cuhk/scripts/build_data.py` with the existing cached OSM data and the standard output directory. Expected output: twelve public route IDs plus conditional-variant features, with no archived ID 1-19 route features.

- [ ] **Step 6: Run Python tests and verify GREEN**

Expected: the full `cuhk/tests` suite passes.

### Task 4: Public-ID frontend filtering and conditional branches

**Files:**
- Modify: `cuhk/site/app-core.js`
- Modify: `cuhk/site/app.js`
- Modify: `cuhk/site/style.json`
- Modify: `cuhk/tests/js/test_app_core.js`

- [ ] **Step 1: Replace mapping tests with failing direct-filter tests**

```javascript
assert.deepEqual(core.routeFilter("N"), ["==", ["get", "route_id"], "N"]);
assert.deepEqual(core.stopFilter("H"), ["in", "|H|", ["get", "route_ids"]]);
assert.ok(core.publicRouteCatalog().every((route) => !(route.sourceRouteIds || []).length));
```

- [ ] **Step 2: Run Node tests and verify RED**

Expected: FAIL because the frontend still maps public IDs to archived IDs.

- [ ] **Step 3: Remove archived mappings**

Keep only metadata in `PUBLIC_ROUTES`. Make `routeFilter` and `stopFilter` use the public identifiers directly. Find route badges by public `route_id`.

- [ ] **Step 4: Add conditional route styling**

Split shuttle rendering into a solid base layer filtered by `is_conditional == false` and a dashed conditional layer filtered by `is_conditional == true`. Add arrows to both layers. Show bilingual condition text in the route information panel.

- [ ] **Step 5: Run Node tests and verify GREEN**

Expected: `app-core tests passed` and both JavaScript files pass `node --check`.

### Task 5: Final route-by-route verification

**Files:**
- Test: generated `cuhk/site/data/shuttle_routes.geojson`
- Test: generated `cuhk/site/data/shuttle_stops.geojson`

- [ ] **Step 1: Run all automated verification**

```powershell
node cuhk\tests\js\test_app_core.js
node --check cuhk\site\app-core.js
node --check cuhk\site\app.js
$env:UV_CACHE_DIR='J:\work\prettymaps\.uv-cache'
$env:UV_PYTHON_INSTALL_DIR='J:\work\prettymaps\.uv-python'
uv run --offline --with-requirements cuhk\requirements.txt python -m pytest cuhk\tests -q --basetemp=J:\work\prettymaps\.pytest-cuhk-shuttle
git diff --check
```

Expected: Node tests pass, JavaScript syntax checks exit 0, all Python tests pass, and `git diff --check` exits 0.

- [ ] **Step 2: Inspect every route in the local browser**

Select `1A`, `1B`, `2`, `3`, `4`, `8`, `5`, `6A`, `6B`, `7`, `N`, and `H` one by one. Confirm route line, stops, badge, panel, arrows, and conditional dashed branches. Capture screenshots for 1B, 3, 4, 5, 6A, 6B, 7, N, and H.

- [ ] **Step 3: Check the reported failure locations**

Verify visually that 1B enters Postgraduate Hall 1; 3 and N do not enter Residence No. 10; 4 traverses CW Chu then Area 39; 5 ends at CW Chu; 6A starts at CW Chu; 6B and 7 use the correct Station Piazza approach; and H begins at Residence No. 10 with only its minute-00 conditional branch entering Area 39/Postgraduate Hall 1.

- [ ] **Step 4: Commit the implementation intentionally**

Stage only shuttle-route implementation, generated shuttle GeoJSON, tests, and directly related frontend changes. Do not include unrelated existing map edits.
