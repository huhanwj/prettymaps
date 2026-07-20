"""CUHK 地图数据管线编排。

用法：python cuhk/scripts/build_data.py [--out cuhk/site/data] [--allow-unmatched]
跑一次产出全部前端数据；OSM/SRTM 缓存于 cuhk/cache，重复跑很快。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import (  # noqa: E402
    boundary,
    building_types,
    elevation,
    heights,
    layers,
    official,
    pois,
    sea,
    shuttle,
    terrain,
    validate,
)
from pipeline.overpass import OverpassClient  # noqa: E402

REPO_CUHK = Path(__file__).resolve().parents[1]


def main():
    # 中文 Windows 控制台默认 GBK：输出含 ²/繁体等字符会直接崩溃，强制 UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="CUHK 地图数据管线")
    parser.add_argument("--out", default=str(REPO_CUHK / "site" / "data"))
    parser.add_argument("--cache", default=str(REPO_CUHK / "cache"))
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help="POI 匹配失败仅警告不中止（调试用）",
    )
    args = parser.parse_args()

    out_dir, cache_dir = Path(args.out), Path(args.cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OverpassClient(cache_dir=cache_dir)

    # ① 边界（校园 + 800m 缓冲）
    print("== ① 边界 ==")
    campus = boundary.fetch_campus_boundary(client, buffer_m=800)

    # ② 图层
    print("== ② OSM 图层 ==")
    gdfs = layers.fetch_all_layers(campus, cache_dir)
    gdfs["green"], gdfs["sports"] = layers.split_green_and_sports(gdfs["green"])

    # ③ 海面
    print("== ③ 海面 ==")
    gdfs["sea"] = sea.fetch_sea(campus, cache_dir)

    # ④ 高程（分层浅色 + 等高线 + terrain-RGB 瓦片）
    print("== ④ 高程 ==")
    gdfs["contours"], dem, dem_lons, dem_lats = elevation.build_elevation_products(
        campus, cache_dir, out_dir, interval=10
    )
    n_tiles = terrain.generate_terrain_tiles(
        dem, dem_lons, dem_lats,
        Path(out_dir).parent / "tiles" / "terrain-rgb",
    )
    print(f"[terrain] {n_tiles} 张 terrain-RGB 瓦片")

    # ⑤ 建筑高度 + 配色索引
    print("== ⑤ 建筑高度 ==")
    gdfs["buildings"] = heights.add_heights(gdfs["buildings"])

    # ⑤b 官方数据（校巴/捷径/官方建筑/POI 校正源）
    print("== ⑤b 官方数据 ==")
    db = official.load_official_db()
    products = official.build_official_products(db)
    gdfs.update(products)
    # Lady Shaw Building's former planted courtyard is now paved/white.
    gdfs["green"] = layers.remove_green_courtyards(
        gdfs["green"], gdfs["official_buildings"], {"H24"}
    )
    for name, gdf in products.items():
        print(f"  {name}: {len(gdf)}")
    shuttle_products = shuttle.build_products(
        roads=gdfs["roads"],
        official_db=db,
        config_path=REPO_CUHK / "data" / "shuttle_routes.yml",
    )
    gdfs.update(shuttle_products)
    for name, gdf in shuttle_products.items():
        print(f"  {name}: {len(gdf)}")

    # ⑤c 建筑功能分类（依赖 ⑤b 的官方建筑点，故必须在 ⑤b 之后）
    print("== ⑤c 建筑分类 ==")
    building_attrs = building_types.assign_attributes(
        gdfs["buildings"], gdfs["official_buildings"]
    )
    gdfs["buildings"][["bt", "campus_id"]] = building_attrs
    print("  建筑 bt 分布:", dict(gdfs["buildings"]["bt"].value_counts()))
    print("  建筑 campus_id 分布:", dict(gdfs["buildings"]["campus_id"].value_counts()))

    # ⑥ POI
    print("== ⑥ POI ==")
    entries = pois.load_pois(REPO_CUHK / "data" / "pois.yml")
    features = pois.fetch_named_features(campus, cache_dir)
    official_src = official.official_poi_sources(db)
    pois.validate_official_pairs(entries, official_src)
    pois_gdf, unmatched = pois.resolve_pois(entries, features, official=official_src)
    if unmatched:
        msg = f"以下 POI 三通道均未解析：{unmatched}（核对 official_name / lon,lat / osm_name）"
        if args.allow_unmatched:
            print("WARNING:", msg)
        else:
            raise SystemExit(msg)
    print("  POI source 分布:", dict(pois_gdf["source"].value_counts()))

    # ⑦ 校验
    print("== ⑦ 校验 ==")
    for line in validate.validate(gdfs, pois_gdf):
        print(" ", line)

    # ⑧ 写出（所有图层都要落盘——style.json 静态引用这些文件，
    #    空图层写成空 FeatureCollection，避免前端 404。
    #    全部 GeoJSON 都在校验通过后写出，避免混 vintage 产出）
    print("== ⑧ 写出 ==")
    campus.to_file(out_dir / "boundary.geojson", driver="GeoJSON")

    keep = {
        "buildings": ["h", "c", "bt", "campus_id", "geometry"],
        "roads": ["road_class", "pedestrian_kind", "drive_direction", "geometry"],
        "railway": ["geometry"],
        "water": ["geometry"],
        "waterway": ["geometry"],
        "forest": ["geometry"],
        "green": ["geometry"],
        "sports": ["sports_kind", "geometry"],
        "beach": ["geometry"],
        "parking": ["geometry"],
        "sea": ["geometry"],
        "contours": ["ele", "geometry"],
        "official_buildings": ["name_en", "name_zh", "bldg_code", "campus_id", "hostel_type", "type", "geometry"],
        "official_landmarks": ["name_en", "name_zh", "geometry"],
        "shuttle_routes": [
            "route_id", "name_en", "name_zh", "color",
            "service_type_id", "service_type_en", "service_type_zh",
            "service_time_id", "service_time_en", "service_time_zh",
            "variant", "condition_zh", "condition_en", "is_conditional",
            "stop_ids", "geometry",
        ],
        "shuttle_stops": ["stop_id", "name_en", "name_zh", "route_ids", "geometry"],
        "walking": ["name_en", "name_zh", "geometry"],
    }
    EMPTY_FC = {"type": "FeatureCollection", "features": []}
    for name, cols in keep.items():
        gdf = gdfs.get(name)
        path = out_dir / f"{name}.geojson"
        if gdf is None or gdf.empty:
            path.write_text(json.dumps(EMPTY_FC), encoding="utf-8")
            print(f"  {name}.geojson: 空图层")
            continue
        missing = set(cols) - {"geometry"} - set(gdf.columns)
        if missing:
            print(f"  WARNING {name}: 缺列 {missing}")
        existing = [c for c in cols if c in gdf.columns]
        gdf[existing].to_file(path, driver="GeoJSON")
        print(f"  {name}.geojson: {len(gdf)} 要素")
    pois_gdf.to_file(out_dir / "pois.geojson", driver="GeoJSON")
    print(f"  pois.geojson: {len(pois_gdf)} 条")
    for recording_path in (REPO_CUHK / "data").glob("cuhk-shuttle-*-recording.json"):
        recording = json.loads(recording_path.read_text(encoding="utf-8"))
        target = out_dir / recording_path.name
        target.write_text(json.dumps(recording, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {target.name}: {len(recording.get('points', []))} 个录制点")
    print(f"完成 → {out_dir}")


if __name__ == "__main__":
    main()
