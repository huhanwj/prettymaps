# CUHK Official Building Labels Design

## Goal

Show substantially more official building names as users zoom in, without turning the campus overview into overlapping text.

## Data sources

- Keep `pois.geojson` as the high-priority source for landmarks, colleges, transport, sports, and selected buildings.
- Add `official_buildings.geojson` as the complete building-label source. It currently contains 159 features with paired Chinese and English names.
- Deduplicate official-building labels against POIs by normalized bilingual name and by screen-space proximity, so the same building is not labeled twice.

## Zoom behavior

- Below zoom 15, retain the current curated POI overview.
- From zoom 15, introduce official building labels using stable importance ranks and the existing collision-avoidance engine.
- From zoom 16, allow denser placement so most buildings visible in the viewport can receive a label when space permits.
- POI labels always outrank generated official-building labels.
- Marker dots remain exclusive to curated POIs; official buildings add text labels only.

## Label presentation

- Use paired Chinese and English official names.
- Building labels use a quieter visual treatment than POI labels: smaller type, neutral colour, and no category dot.
- Collision decisions are deterministic and recomputed on pan, zoom, resize, and category-filter changes.
- Clicking a labeled official building opens a bilingual popup.

## Testing and acceptance

- Unit tests cover bilingual-name normalization, POI/building deduplication, zoom thresholds, and density changes.
- Frontend/style tests require loading `official_buildings.geojson` and prohibit building labels below zoom 15.
- Browser review checks that the overview remains legible, zoom 15 adds official building names, zoom 16 adds more, and existing POI labels remain higher priority.

## Out of scope

- Editing official building names or coordinates.
- Re-enabling 3D.
- Labeling unnamed OSM buildings.

