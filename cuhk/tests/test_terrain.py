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
