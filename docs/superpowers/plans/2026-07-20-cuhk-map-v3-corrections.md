# CUHK Map V3 Corrections Implementation Plan

1. Add failing tests for sports-surface classification and export.
2. Add failing tests that the rendered pedestrian dataset contains only curated PDF links.
3. Add failing tests for official bilingual POI pair consistency and corrected transport points.
4. Add failing tests proving shuttle segments include both stop anchors and real routes pass through their assigned stops.
5. Implement the minimal pipeline changes for sports, pedestrians, POIs, and shuttle geometry.
6. Add failing frontend/style tests for a terrain toggle, default-hidden tint/contours, and conditional legend.
7. Generate a neutral hypsometric tint raster from the DEM and implement the terrain UI without 3D terrain calls.
8. Rebuild all site data, run the complete Python and JavaScript suites, and check syntax/diffs.
9. Review the corrected map in a browser at overview and campus zooms, including terrain off/on and selected shuttle routes.
10. Commit the verified correction set on `cuhk-map`.
