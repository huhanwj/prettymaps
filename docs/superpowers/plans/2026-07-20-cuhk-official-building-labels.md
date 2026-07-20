# CUHK Official Building Labels Implementation Plan

1. Add JavaScript unit tests for normalized bilingual deduplication, zoom thresholds, density padding, and building priority.
2. Implement pure building-label helpers in `app-core.js`.
3. Load `official_buildings.geojson`, remove POI duplicates, and create text-only interactive building markers.
4. Extend the shared collision pass so POIs rank above buildings and zoom 16 uses denser placement.
5. Add the quieter bilingual building-label styling and frontend integration assertions.
6. Run JavaScript and Python tests, then verify zoom 14.6, 15.6, and 16.6 in the local browser.

