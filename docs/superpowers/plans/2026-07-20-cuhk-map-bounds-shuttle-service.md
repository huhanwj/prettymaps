# CUHK Map Bounds and Shuttle Service Implementation Plan

1. Add failing parser tests for official service type/time joins, including routes without a service-time record.
2. Add failing frontend tests that group routes by service schedule and never expose internal route IDs as public numbers.
3. Add failing configuration tests for initial zoom, minimum zoom, campus bounds, and disabled world copies.
4. Export shuttle service metadata and rebuild the static route GeoJSON.
5. Replace numbered selector options, route cards, and map badges with grouped schedule/destination labels.
6. Apply viewport constraints, run the full test suite, and visually verify minimum zoom and shuttle selection.

