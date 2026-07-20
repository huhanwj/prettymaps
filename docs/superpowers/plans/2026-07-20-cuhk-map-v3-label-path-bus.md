# CUHK Map V3 Label, Path, Pool, and Bus Implementation Plan

1. Add regression tests for road-kind classification, swimming pools, route naming, label collision, and style semantics.
2. Extend the OSM layer pipeline to export a mutually exclusive pedestrian kind and pool sports kind.
3. Replace PDF pedestrian styling with filtered OSM road layers and remove ambiguous dashed overlays.
4. Add priority-aware collision-managed POI labels.
5. Add route-numbered selector labels and a bilingual shuttle route information panel.
6. Rebuild static data, run Python and JavaScript tests, and visually inspect the served map.

