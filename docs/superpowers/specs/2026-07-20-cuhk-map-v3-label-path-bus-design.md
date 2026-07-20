# CUHK Map V3 Label, Path, Pool, and Bus Design

## Goal

Make the V3 map readable without hiding whole POI categories, give every pedestrian line one unambiguous meaning, model swimming pools as sports surfaces, and expose the identity of every shuttle route.

## Confirmed behavior

### POI labels

- Every POI category participates in labeling at the default zoom.
- Labels are ordered by a stable importance rank and placed with screen-space collision avoidance.
- Marker dots remain available when their labels cannot fit; zooming in reveals more labels.
- Category chips still hide both the marker and its label.
- A clicked marker remains discoverable through its popup regardless of label density.

### Pedestrian network

- The V3 map no longer renders the PDF-curated pedestrian GeoJSON.
- OSM road tags are classified once as `path`, `bridge`, or `stairs`.
- A bridge or stair geometry is excluded from the ordinary path layer, preventing double drawing.
- Ordinary paths are solid grey-blue, bridges are solid blue, and stairs are dashed blue.
- The official walking-route overlay and dashed campus boundary are hidden because their grey dashes conflict with the stair convention.

### Sports and swimming pools

- OSM `leisure=swimming_pool` polygons are fetched with other sports surfaces.
- Pools are classified as `pool` and rendered as a distinct pale-blue fill with a blue outline.
- This is a 2D pool-surface model; deferred 3D remains disabled.

### Shuttle routes

- Selector entries include the route number and bilingual official route name.
- Selecting one route shows a compact route card with its colour, number, Chinese name, and English name.
- Selecting all routes shows a compact route list; selecting off hides it.
- Direction arrows and stop filtering continue to use the same route selection.

## Acceptance

- Unit tests cover OSM path classification, pool classification, route labels, and label collision selection.
- Style tests reject the grey dashed walking and boundary layers, verify mutually exclusive path filters, and require a pool layer.
- The data pipeline exports the new road kind and pool surfaces.
- Browser review checks default label coverage, absence of unexplained grey dashes, visible pool geometry, and route names for single/all selections.

