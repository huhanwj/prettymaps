import numpy as np
import pytest

from pipeline import terrain


def test_rgb_roundtrip():
    for h in (-5.0, 0.0, 42.5, 140.0, 8848.0):
        r, g, b = terrain.encode_height(h)
        assert terrain.decode_height(r, g, b) == pytest.approx(h, abs=0.06)


def test_tile_math():
    assert terrain.lon2tilex(114.0, 16) == pytest.approx(53521.07, abs=0.1)
    # 瓦片边界反解
    x0, x1 = 53521, 53522
    assert terrain.tilex2lon(x0, 16) < 114.0 < terrain.tilex2lon(x1, 16)
    y = terrain.lat2tiley(22.42, 16)
    assert terrain.tiley2lat(int(y), 16) > 22.42 > terrain.tiley2lat(int(y) + 1, 16)


def test_generate_tile_shape():
    dem = np.arange(100 * 100, dtype=np.float32).reshape(100, 100)
    lons = np.linspace(114.0, 114.1, 100)
    lats = np.linspace(22.0, 22.1, 100)
    tile = terrain.render_tile(dem, lons, lats, z=16, x=53521, y=int(terrain.lat2tiley(22.05, 16)), size=256)
    assert tile.shape == (256, 256, 3)
    assert tile.dtype == np.uint8


def test_tiles_covering():
    tiles = terrain.tiles_covering(114.20, 22.41, 114.22, 22.43, 14)
    assert tiles  # 非空
    assert all(t[0] == 14 for t in tiles)


def _decode_px(tile, row, col):
    r, g, b = (int(v) for v in tile[row, col])
    return terrain.decode_height(r, g, b)


def test_render_tile_planar_dem_correctness():
    # 斜面 z = 100 + 1000*(lon-114.0)，瓦片完全落在 DEM 内 → 解码值应等于斜面值
    lons = np.linspace(114.0, 114.1, 200)
    lats = np.linspace(22.1, 22.0, 200)  # 北在上
    dem = (100 + 1000 * (lons - 114.0))[None, :].repeat(200, axis=0).astype(np.float32)
    z, x, y, size = 14, 13381, 7163, 256  # 该瓦片 lon∈[114.0161,114.0381] lat∈[22.052,22.067]，全在网格内
    tile = terrain.render_tile(dem, lons, lats, z=z, x=x, y=y, size=size)
    west, east = terrain.tilex2lon(x, z), terrain.tilex2lon(x + 1, z)
    for row, col in [(10, 10), (128, 128), (245, 245)]:
        lon_px = west + (col + 0.5) * (east - west) / size
        expected = 100 + 1000 * (lon_px - 114.0)
        assert _decode_px(tile, row, col) == pytest.approx(expected, abs=0.15)
    # 方向性：斜面随经度升高 → 东侧像素高于西侧
    assert _decode_px(tile, 128, 245) > _decode_px(tile, 128, 10)


def test_render_tile_rows_mercator():
    # 高度只随纬度变 h = lat*10000：行解码值应匹配 Mercator 纬度，而非线性纬度
    lons = np.linspace(113.5, 114.5, 100)
    lats = np.linspace(22.5, 21.5, 200)  # 北在上，覆盖 z10 瓦片
    dem = (lats * 10000)[:, None].repeat(100, axis=1).astype(np.float32)
    z, size = 10, 256
    x = int(terrain.lon2tilex(114.1, z))
    y = int(terrain.lat2tiley(22.1, z))
    tile = terrain.render_tile(dem, lons, lats, z=z, x=x, y=y, size=size)
    row = 128
    decoded = _decode_px(tile, row, 128)
    merc_lat = terrain.tiley2lat(y + (row + 0.5) / size, z)
    north, south = terrain.tiley2lat(y, z), terrain.tiley2lat(y + 1, z)
    lin_lat = north - (row + 0.5) / size * (north - south)
    # 与 Mercator 纬度一致（双线性对线性场精确 + 0.1m 量化）
    assert decoded == pytest.approx(merc_lat * 10000, abs=0.4)
    # 与线性纬度有可分辨的差（z10 中行约 0.94m）
    assert abs(decoded - lin_lat * 10000) > 0.5


def test_render_tile_outside_dem_is_sea_level():
    # DEM 覆盖外像素必须解码为海平面 0，而不是 DEM 边缘高程的复制
    dem = np.full((101, 101), 300.0, dtype=np.float32)
    lons = np.linspace(114.0, 114.02, 101)
    lats = np.linspace(22.02, 22.0, 101)
    z, size = 16, 256
    x = int(terrain.lon2tilex(114.0, z))  # 瓦片西缘在 DEM 西侧之外
    y = int(terrain.lat2tiley(22.01, z))
    tile = terrain.render_tile(dem, lons, lats, z=z, x=x, y=y, size=size)
    west, east = terrain.tilex2lon(x, z), terrain.tilex2lon(x + 1, z)
    assert west < 114.0  # 确认瓦片确实伸出 DEM 西缘
    assert _decode_px(tile, 128, 0) == pytest.approx(0.0, abs=0.06)
    assert _decode_px(tile, 128, 200) == pytest.approx(300.0, abs=0.15)
