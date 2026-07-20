# CUHK Map Bounds and Shuttle Service Design

## Goal

Prevent users from zooming or panning into large empty areas, and replace the misleading public display of internal shuttle route IDs with the actual official service categories, times, and destinations.

## Map viewport

- Raise the initial zoom from 14.6 to 15.0.
- Set the minimum zoom to approximately 14.8 so the campus remains the dominant page content.
- Add maximum navigation bounds covering the CUHK campus and its useful surrounding transport context.
- Keep zooming in, rotation, and normal campus panning available.
- Disable repeated world copies.
- The constraint must apply consistently after browser resize and hash-based navigation.

## Shuttle semantics

- Treat official `route_id` values 1–19 as internal identifiers only. They remain in GeoJSON for filtering and stop membership but are never presented as public route numbers.
- Export the official service type and service-time metadata paired to each route:
  - Monday to Saturday / before 9:00 a.m.
  - Monday to Saturday / 9:00 a.m. to 6:00 p.m.
  - Monday to Saturday / after 6:00 p.m.
  - Meet-class.
  - Sundays and public holidays.
- Group selector options by service type and time. Within each group, show the bilingual origin/destination route name.
- The selected-route panel shows the service category, time, colour, and bilingual origin/destination. It does not show `線路 N` or `Route N`.
- The map badge uses a short service-time/category label rather than the internal ID.
- Direction arrows, route geometry, and stop filters continue to use the internal ID invisibly.

## Data flow

1. The official parser joins each shuttle route to `shuttle_bus_route_type` and `shuttle_bus_route_service_time` using the official IDs, including the source typo `rotue_service_time_id`.
2. The pipeline exports bilingual service fields alongside the existing internal route ID and geometry.
3. Frontend route options form stable service groups and keep internal IDs only in option values and MapLibre filters.
4. Map construction applies the new zoom and navigation constraints before loading data.

## Testing and acceptance

- Parser tests verify service metadata joins and missing-time handling.
- Frontend tests reject visible `線路 1`/`Route 1` labels and verify grouped service labels.
- Map configuration tests require the new initial/minimum zoom, maximum bounds, and disabled world copies.
- Browser review verifies that zooming out stops before large blank areas appear and that route selection exposes no internal 1–19 numbering.

## Out of scope

- Replacing the archived CUHK route geometry or timetable with a new external transit API.
- Expanding the map into a Shatin regional map.
- Removing internal route IDs from data, since route filtering depends on them.

