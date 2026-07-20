# CUHK Map V3 Corrections Design

## Goal

Correct the V3 map where the first implementation diverged from the official campus map or paired official data. The corrected version must preserve the white, college-coloured V3 style while restoring sports grounds, reducing pedestrian links to the official PDF set, accurately pairing bilingual labels, drawing shuttle routes through every stop, and making terrain optional and legible.

## Confirmed behaviour

### Base map and sports grounds

- The default base remains white.
- Forest, generic grass, park, and other blank land remain white.
- Sports polygons are split from the generic green layer using OSM `leisure` values `pitch`, `track`, `sports_centre`, and `stadium`.
- Sports grounds use restrained official-map colours: pale green for playing surfaces and a pale warm track treatment where the available tags distinguish tracks.

### Pedestrian links

- V3 uses only the 12 georeferenced links curated from `Campus-Map-YIA-LT2.pdf`.
- The 227 automatically inferred OSM bridge/stair segments are excluded from the rendered V3 dataset because they fragment and duplicate facilities.
- Solid blue means footbridge.
- Dashed blue means stairs or a height-changing pedestrian connection.
- The pipeline retains validation for geometry type, allowed kind, CRS, and campus bounds.

### Bilingual POI audit

- Every POI with `official_name` is checked against the archived official CUHK dataset.
- The displayed Chinese label must be paired with the selected official English record; common aliases belong in the description rather than replacing the paired official name.
- Known corrections include:
  - `Yasumoto International Academic Park` -> `康本國際學術園`.
  - `Esther Lee Building` -> `利黃瑤璧樓`.
  - `United College Wu Chung Library` -> `聯合書院胡忠圖書館`.
  - `William M.W. Mong Engineering Building` -> `蒙民偉工程學大樓`.
- The generic University Station POI is replaced by the official northern and western MTR exit records from the PDF/database.
- The bus terminus is placed at the official transport-interchange coordinates and labelled `大學站公共運輸交匯處` / `University Station Public Transport Interchange`.

### Shuttle route continuity

- A shuttle segment is interpreted as `start stop -> decoded intermediate path -> end stop`.
- Start and end stop coordinates are mandatory geometry anchors when present.
- A decoded single intermediate point remains a valid segment after the two stop anchors are added.
- Ordered segments for a route meet at their shared stop, so routes visibly enter Central Campus, United College, New Asia College, and every other listed stop.
- Automated validation measures every route stop against its route geometry and rejects visible gaps.
- Direction arrows remain aligned to the official route order.

### Terrain mode

- Terrain is off by default.
- The previous grey raster hillshade is removed.
- A `地形` toggle shows or hides both a subtle hypsometric elevation tint and contours.
- The tint uses light neutral elevation bands so it does not reintroduce the disliked green base.
- The terrain legend is visible only while terrain is enabled and labels `0 / 50 / 100 / 150 m`.
- The terrain toggle does not enable 3D terrain and does not call `map.setTerrain`; the deferred 3D freeze remains unfixed.

## Data flow

1. The OSM green query is classified into generic green and sports surfaces before export.
2. The pedestrian export uses the validated curated PDF GeoJSON only.
3. The POI loader checks official bilingual pair consistency and uses explicit official transport records.
4. The shuttle parser prepends/appends stop coordinates around decoded intermediate points.
5. The elevation build emits a transparent, georeferenced tint raster and metadata alongside existing contour data.
6. The frontend loads all layers with terrain layers hidden, then toggles tint, contours, contour labels, and the elevation legend together.

## Testing and acceptance

- Unit tests cover sports extraction, curated-only pedestrian output, official bilingual pair checks, MTR/transport coordinates, and stop-anchored shuttle geometry.
- A real-data regression asserts that every route's ordered segment endpoints meet at the shared stop and that route-associated stops lie on their route.
- Style tests assert terrain defaults off, the old hillshade is absent, and the terrain legend/toggle are wired.
- The full offline pipeline must pass validation.
- Browser review must check the default white map, restored sports fields, uncluttered PDF pedestrian links, corrected labels, terrain on/off states and legend, and at least one route through Central Campus and United College.

## Out of scope

- Repairing or re-enabling 3D terrain.
- Automatically adding pedestrian links not present in the supplied PDF.
- Re-routing official shuttle paths through an external routing service.
