"""CUHK 地图数据管线编排。

用法：python cuhk/scripts/build_data.py [--out cuhk/site/data] [--allow-unmatched]
跑一次产出全部前端数据；OSM/SRTM 缓存于 cuhk/cache，重复跑很快。
"""

import argparse
import json
import sys
from pathlib import Path

import geopandas as gp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import (  # noqa: E402
    boundary,
    elevation,
    heights,
    layers,
    pois,
    sea,
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

    # ③ 海面
    print("== ③ 海面 ==")
    gdfs["sea"] = sea.fetch_sea(campus)

    # ④ 高程（hillshade + 等高线）
    print("== ④ 高程 ==")
    gdfs["contours"] = elevation.build_elevation_products(
        campus, cache_dir, out_dir, interval=10
    )

    # ⑤ 建筑高度 + 配色索引
    print("== ⑤ 建筑高度 ==")
    gdfs["buildings"] = heights.add_heights(gdfs["buildings"])

    # ⑥ POI
    print("== ⑥ POI ==")
    entries = pois.load_pois(REPO_CUHK / "data" / "pois.yml")
    features = pois.fetch_named_features(campus)
    pois_gdf, unmatched = pois.resolve_pois(entries, features)
    if unmatched:
        msg = f"以下 POI 未匹配到 OSM 要素：{unmatched}（核对 pois.yml 的 osm_name 或改 lon/lat）"
        if args.allow_unmatched:
            print("WARNING:", msg)
        else:
            raise SystemExit(msg)

    # ⑦ 校验
    print("== ⑦ 校验 ==")
    for line in validate.validate(gdfs, pois_gdf):
        print(" ", line)

    # ⑧ 写出（所有图层都要落盘——style.json 静态引用全部 12 个文件，
    #    空图层写成空 FeatureCollection，避免前端 404。
    #    全部 GeoJSON 都在校验通过后写出，避免混 vintage 产出）
    print("== ⑧ 写出 ==")
    campus.to_file(out_dir / "boundary.geojson", driver="GeoJSON")

    keep = {
        "buildings": ["h", "c", "geometry"],
        "roads": ["road_class", "geometry"],
        "railway": ["geometry"],
        "water": ["geometry"],
        "waterway": ["geometry"],
        "forest": ["geometry"],
        "green": ["geometry"],
        "beach": ["geometry"],
        "parking": ["geometry"],
        "sea": ["geometry"],
        "contours": ["ele", "geometry"],
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
    print(f"完成 → {out_dir}")


if __name__ == "__main__":
    main()
