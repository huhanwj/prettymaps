# CUHK Public Shuttle Route Geometry Design

Date: 2026-07-20

## Goal

Replace the incorrect mapping from public CUHK shuttle identifiers to archived route IDs 1-19. The map must display the current public routes `1A`, `1B`, `2`, `3`, `4`, `8`, `5`, `6A`, `6B`, `7`, `N`, and `H` with route-specific geometry, stops, direction arrows, and conditional detours.

## Sources of truth

Route order and service variants come from the current CUHK Transport Office diagrams:

- `Shuttle.pdf` for routes 1A, 1B, 2, 3, 4, and 8.
- `Meet-class_24-25.pdf` for routes 5, 6A, 6B, and 7.
- `NH.pdf` for routes N and H.
- User correction on 2026-07-20: all three route 5 departures at minutes 18, 22, and 26 now continue to CW Chu College.

The archived CUHK campus-map database remains useful for stop coordinates and legacy line segments, but its route IDs and route compositions are not authoritative for the current public service.

## Root cause

The current implementation maps each public route to one or more complete archived routes. A complete archived route contains branches that cannot be removed independently. This produces false detours such as Residence No. 10 on routes N and 3, while failing to represent current stops such as CW Chu College, Area 39, Station Piazza, and the Postgraduate Hall 1 detour correctly.

## Route requirements

The implementation must preserve the route order shown by the current Transport Office diagrams and satisfy these explicit constraints:

- `1B`: include the Postgraduate Hall 1 detour. Route 1A must not inherit that detour.
- `3`: exclude Residence No. 10.
- `4`: traverse CW Chu College and Area 39 in the official order near the beginning of the route.
- `8`: use the Western Campus route shown in the current daytime diagram, not archived route 15 as a whole.
- `5`: all departures at minutes 18, 22, and 26 continue to CW Chu College.
- `6A`: start at CW Chu College and follow the current downward route to Chung Chi Teaching Building.
- `6B`: use the current NA/UC downward route and the correct final approach to Station Piazza and Chung Chi Teaching Building.
- `7`: use the current Shaw downward route and the correct final approach to Station Piazza and Chung Chi Teaching Building.
- `N`: exclude Residence No. 10 and use the correct CW Chu College/Area 39 section. The Postgraduate Hall 1 branch applies only to departures at minute 00.
- `H`: start from Residence No. 10 and use the correct CW Chu College/Area 39 section. Area 39 and Postgraduate Hall 1 are conditional stops for departures at minute 00.

## Data model

Create a curated public route definition for each public identifier. A route definition contains:

- public identifier, bilingual name, group, and display color;
- ordered stop identifiers;
- ordered routing waypoints where stop-to-stop shortest routing alone is ambiguous;
- one base path and zero or more conditional variants;
- variant label and service condition;
- explicit forbidden stops used by validation tests.

Generated route GeoJSON uses the public identifier as `route_id`; archived route IDs do not reach the frontend. Stop GeoJSON stores public route identifiers in `route_ids`.

## Geometry generation

Build a routable graph from the generated campus road layer. Snap each official stop and curated waypoint to the nearest valid road edge, then compute the path between consecutive ordered points. Preserve direction and concatenate the paths into one continuous route geometry.

Use curated waypoints only where needed to force the side of the road, the CW Chu/Area 39 loop, the Postgraduate Hall 1 spur, or the correct Station Piazza approach. This keeps the definitions reviewable while avoiding hand-drawn line coordinates.

Conditional service paths are separate GeoJSON features sharing the public route identifier and carrying `variant`, `condition_zh`, and `condition_en` properties. Base paths render as solid lines. Conditional-only branches render as dashed lines with the same route color and retain direction arrows.

## Frontend behavior

The selector continues to show only the twelve public route identifiers. Selecting a route filters route geometry and stops directly by the public `route_id`. The information panel shows the base route and any conditional branch conditions. The map never exposes archived route IDs.

Selecting `all` shows all public routes. Conditional branches remain dashed so they are not mistaken for stops served by every departure.

## Validation and tests

Tests must verify:

- the public route catalog contains exactly the twelve identifiers in the agreed order;
- every generated route is continuous and follows the road network;
- every declared stop lies on its generated route within a small projected tolerance;
- direction arrows follow coordinate order;
- route 1B includes Postgraduate Hall 1;
- routes 3 and N exclude Residence No. 10;
- route 4 contains CW Chu College before Area 39;
- route 5 ends at CW Chu College for all listed departures;
- route 6A starts at CW Chu College;
- routes 6B and 7 use Station Piazza and Chung Chi Teaching Building in the correct final order;
- H starts at Residence No. 10 and represents its minute-00 Area 39/Postgraduate Hall 1 variant separately;
- no archived numeric route ID is visible in frontend options, badges, panels, or filters.

Visual verification must check each route individually at the local site, with special attention to CW Chu College, Area 39, Residence No. 10, Postgraduate Hall 1, and Station Piazza.

## Failure handling

Data generation fails with a route-and-stop-specific error if a stop cannot be snapped, a path cannot be found, or a generated route violates a forbidden-stop constraint. It must not silently fall back to an archived complete route.

## Out of scope

- Live vehicle positions and real-time service status.
- Timetable countdowns.
- Re-enabling the 3D mode.
- Redesigning pedestrian links, terrain, or building labels.
