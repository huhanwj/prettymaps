import numpy as np
import pytest

from pipeline import elevation


def test_tile_bounds():
    assert elevation.tile_bounds("N22E114") == (114.0, 22.0, 115.0, 23.0)


def test_read_hgt_roundtrip(tmp_path):
    dem = (np.arange(1201 * 1201) % 30000).astype(">i2").reshape(1201, 1201)
    path = tmp_path / "tile.hgt"
    dem.tofile(path)
    out = elevation.read_hgt(path)
    assert out.shape == (1201, 1201)
    assert out[0, 1] == 1


def test_read_hgt_rejects_bad_size(tmp_path):
    (tmp_path / "bad.hgt").write_bytes(b"\x00" * 100)
    with pytest.raises(ValueError, match="HGT"):
        elevation.read_hgt(tmp_path / "bad.hgt")


def test_fill_voids():
    dem = np.full((5, 5), 100.0)
    dem[2, 2] = np.nan
    filled = elevation.fill_voids(dem)
    assert filled[2, 2] == pytest.approx(100.0)


def test_contours_of_tilted_plane():
    # 沿 x 方向每度上升 1000m 的斜面 → 等高线是等间距竖直线
    lons = np.linspace(114.0, 114.1, 101)
    lats = np.linspace(22.0, 22.1, 101)
    dem = np.tile((lons - 114.0) * 10000, (101, 1))  # 0..1000m
    gdf = elevation.contour_lines(dem, lons, lats, interval=100)
    # 100..900m 必定出现（1000m 恰好在数据边缘，是否出线是实现细节，不断言）
    assert set(range(100, 1000, 100)) <= set(gdf["ele"])
    # 100m 等高线应在 lon≈114.01 附近且南北走向
    line = gdf[gdf["ele"] == 100].geometry.iloc[0]
    xs, ys = line.xy
    assert abs(np.mean(xs) - 114.01) < 0.002
    assert max(xs) - min(xs) < 0.002  # 竖直


def test_hillshade_rgba_shape():
    dem = np.random.default_rng(0).normal(100, 10, (50, 50))
    rgba = elevation.hillshade_rgba(dem, cellsize_m=30)
    assert rgba.shape == (50, 50, 4)
    assert rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # 有阴影
