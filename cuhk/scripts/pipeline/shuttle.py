"""Current public CUHK shuttle route products."""

from pathlib import Path

import geopandas as gp
import networkx as nx
import yaml
from shapely.geometry import LineString, Point

from .official import parse_lat_lng


PUBLIC_ROUTE_IDS = [
    "1A", "1B", "2", "3", "4", "8",
    "5", "6A", "6B", "7", "N", "H",
]


def load_config(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    routes = data.get("routes", {})
    if list(routes) != PUBLIC_ROUTE_IDS:
        raise ValueError("public shuttle route order must match the approved catalog")
    stops = data.get("stops", {})
    for route_id, route in routes.items():
        route_stops = route.get("stops", [])
        if len(route_stops) < 2:
            raise ValueError(f"route {route_id}: at least two ordered stops are required")
        missing = [stop for stop in route_stops if stop not in stops]
        if missing:
            raise ValueError(f"route {route_id}: unknown stops {missing}")
    return data


def variant_stops(base_stops, variant):
    stops = list(base_stops)
    replacement = variant.get("replace_tail")
    if replacement:
        pivot = replacement["from"]
        index = stops.index(pivot)
        stops = stops[: index + 1] + list(replacement["with"])
    for insertion in variant.get("insertions", []):
        index = stops.index(insertion["after"])
        stops.insert(index + 1, insertion["stop"])
    return stops


def _road_graph(roads):
    graph = nx.Graph()
    for _, row in roads.iterrows():
        if row.get("road_class") in {"path", "steps"}:
            continue
        geometry = row.geometry
        lines = list(geometry.geoms) if geometry.geom_type == "MultiLineString" else [geometry]
        for line in lines:
            coordinates = list(line.coords)
            for start, end in zip(coordinates, coordinates[1:]):
                start = tuple(start[:2])
                end = tuple(end[:2])
                edge = LineString([start, end])
                length = edge.length
                if length <= 0:
                    continue
                if graph.has_edge(start, end) and graph[start][end]["weight"] <= length:
                    continue
                graph.add_edge(start, end, weight=length)
    return graph


def _nearest_node(point, nodes, max_snap_m, route_id, stop_name):
    node = min(nodes, key=lambda candidate: point.distance(Point(candidate)))
    distance = point.distance(Point(node))
    if distance > max_snap_m:
        raise ValueError(
            f"route {route_id}: stop {stop_name} is {distance:.1f} m from the road graph"
        )
    return node


def build_route_geometry(
    route_id,
    ordered_stops,
    stop_points,
    roads,
    max_snap_m=120,
    graph=None,
):
    graph = graph or _road_graph(roads)
    if not graph.nodes:
        raise ValueError(f"route {route_id}: road graph is empty")
    nodes = list(graph.nodes)
    snapped = {
        name: _nearest_node(stop_points[name], nodes, max_snap_m, route_id, name)
        for name in ordered_stops
    }
    coordinates = []
    for start_name, end_name in zip(ordered_stops, ordered_stops[1:]):
        try:
            path = nx.shortest_path(
                graph,
                snapped[start_name],
                snapped[end_name],
                weight="weight",
            )
        except nx.NetworkXNoPath as exc:
            raise ValueError(
                f"route {route_id}: no road path from {start_name} to {end_name}"
            ) from exc
        segment = [tuple(stop_points[start_name].coords[0]), *path, tuple(stop_points[end_name].coords[0])]
        for coordinate in segment:
            if not coordinates or coordinate != coordinates[-1]:
                coordinates.append(coordinate)
    return LineString(coordinates)


def _resolve_stop_points(config, official_db):
    official_stops = {
        str(item.get("bus_stop_id", "")): item
        for item in official_db.get("shuttle_bus_stops", [])
    }
    records = []
    for stop_id, definition in config["stops"].items():
        coordinates = definition.get("coordinates")
        if coordinates is None:
            source = official_stops.get(str(definition.get("official_stop_id", "")))
            coordinates = parse_lat_lng(source.get("lat_lng", "")) if source else None
        if coordinates is None:
            raise ValueError(f"shuttle stop {stop_id}: coordinates are unavailable")
        records.append({
            "stop_id": stop_id,
            "name_en": definition["name_en"],
            "name_zh": definition["name_zh"],
            "geometry": Point(coordinates),
        })
    return gp.GeoDataFrame(records, crs="EPSG:4326")


def _conditional_sequences(base_stops, variant):
    sequences = []
    replacement = variant.get("replace_tail")
    if replacement:
        sequences.append([replacement["from"], *replacement["with"]])
    for insertion in variant.get("insertions", []):
        index = base_stops.index(insertion["after"])
        if index + 1 >= len(base_stops):
            raise ValueError(f"variant {variant['id']}: insertion cannot follow final stop")
        sequences.append([
            insertion["after"], insertion["stop"], base_stops[index + 1]
        ])
    return sequences


def build_products(roads, official_db, config_path):
    config = load_config(config_path)
    stop_gdf = _resolve_stop_points(config, official_db)
    target_crs = roads.crs if roads.crs and roads.crs.is_projected else "EPSG:32650"
    roads_metric = roads.to_crs(target_crs)
    stops_metric = stop_gdf.to_crs(target_crs).set_index("stop_id")
    stop_points = stops_metric.geometry.to_dict()
    graph = _road_graph(roads_metric)

    route_rows = []
    memberships = {stop_id: set() for stop_id in config["stops"]}
    group_meta = {
        "campus": ("1", "星期一至六", "Monday to Saturday"),
        "meet-class": ("2", "轉堂", "Meet-class"),
        "special": ("3", "晚間及假日", "Night-time and Public Holidays"),
    }
    for route_id, definition in config["routes"].items():
        ordered_stops = list(definition["stops"])
        for stop_id in ordered_stops:
            memberships[stop_id].add(route_id)
        service_type_id, service_type_zh, service_type_en = group_meta[definition["group"]]
        common = {
            "route_id": route_id,
            "name_en": definition["name_en"],
            "name_zh": definition["name_zh"],
            "color": definition["color"],
            "service_type_id": service_type_id,
            "service_type_en": service_type_en,
            "service_type_zh": service_type_zh,
            "service_time_id": "",
            "service_time_en": "",
            "service_time_zh": "",
        }
        base_geometry = build_route_geometry(
            route_id,
            ordered_stops,
            stop_points,
            roads_metric,
            graph=graph,
        )
        route_rows.append({
            **common,
            "variant": "base",
            "condition_zh": "",
            "condition_en": "",
            "is_conditional": False,
            "stop_ids": "|".join(ordered_stops),
            "geometry": base_geometry,
        })
        for variant in definition.get("variants", []):
            for branch_number, branch_stops in enumerate(
                _conditional_sequences(ordered_stops, variant), start=1
            ):
                for stop_id in branch_stops:
                    memberships[stop_id].add(route_id)
                geometry = build_route_geometry(
                    route_id,
                    branch_stops,
                    stop_points,
                    roads_metric,
                    graph=graph,
                )
                route_rows.append({
                    **common,
                    "variant": f"{variant['id']}:{branch_number}",
                    "condition_zh": variant["condition_zh"],
                    "condition_en": variant["condition_en"],
                    "is_conditional": True,
                    "stop_ids": "|".join(branch_stops),
                    "geometry": geometry,
                })

    routes = gp.GeoDataFrame(route_rows, crs=target_crs).to_crs("EPSG:4326")
    stop_rows = []
    stop_source = stop_gdf.set_index("stop_id")
    for stop_id, route_ids in memberships.items():
        if not route_ids:
            continue
        source = stop_source.loc[stop_id]
        ordered_route_ids = [route_id for route_id in PUBLIC_ROUTE_IDS if route_id in route_ids]
        stop_rows.append({
            "stop_id": stop_id,
            "name_en": source["name_en"],
            "name_zh": source["name_zh"],
            "route_ids": "|" + "|".join(ordered_route_ids) + "|",
            "geometry": source.geometry,
        })
    stops = gp.GeoDataFrame(stop_rows, crs="EPSG:4326")
    return {"shuttle_routes": routes, "shuttle_stops": stops}
