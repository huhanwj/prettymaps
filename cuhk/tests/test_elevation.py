import numpy as np
import pytest

from pipeline import elevation


def test_tile_bounds():
    assert elevation.tile_bounds("N22E114") == (114.0, 22.0, 115.0, 23.0)


def test_tile_bounds_western():
    assert elevation.tile_bounds("S22W114") == (-114.0, -23.0, -113.0, -22.0)


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


def test_hgt_size_ok_accepts_both_resolutions(tmp_path):
    """skadi 文件名不编码分辨率：1201² 和 3601² 都算合法缓存。"""
    srtm3 = tmp_path / "N22E114.hgt"
    srtm3.write_bytes(b"\x00" * (1201 * 1201 * 2))
    assert elevation._hgt_size_ok(srtm3)
    srtm1 = tmp_path / "N22E115.hgt"
    srtm1.write_bytes(b"\x00" * (3601 * 3601 * 2))
    assert elevation._hgt_size_ok(srtm1)


def test_hgt_size_ok_rejects_garbage(tmp_path):
    bad = tmp_path / "N22E114.hgt"
    bad.write_bytes(b"\x00" * 12345)
    assert not elevation._hgt_size_ok(bad)
    assert not elevation._hgt_size_ok(tmp_path / "missing.hgt")


def test_download_hgt_uses_valid_cache(tmp_path):
    """合法缓存直接命中，不触发下载（SRTM1 大小，文件名不含 3）。"""
    cached = tmp_path / "N22E114.hgt"
    cached.write_bytes(b"\x00" * (3601 * 3601 * 2))
    assert elevation.download_hgt("N22E114", tmp_path) == cached


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
    rgba = elevation.hillshade_rgba(dem, dx_m=30, dy_m=30)
    assert rgba.shape == (50, 50, 4)
    assert rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # 有阴影


def test_crop_to_bounds_corners():
    n = 1201
    dem = np.arange(n * n, dtype=np.float32).reshape(n, n)
    # 裁剪 114.25–114.35 E, 22.15–22.25 N（tile N22E114 西南角 114,22）
    west, south, east, north = 114.25, 22.15, 114.35, 22.25
    crop, lons, lats = elevation.crop_to_bounds(dem, "N22E114", west, south, east, north)
    assert lons[0] == pytest.approx(114.25)
    assert lons[-1] == pytest.approx(114.35)
    assert lats[0] == pytest.approx(22.25)  # 第 0 行是北边缘
    assert lats[-1] == pytest.approx(22.15)
    assert crop.shape == (len(lats), len(lons))
    # 西北角对应源图像 row=(23-22.25)*1200, col=(114.25-114)*1200
    row_idx = int(round((23.0 - 22.25) * (n - 1)))
    col_idx = int(round((114.25 - 114.0) * (n - 1)))
    assert crop[0, 0] == dem[row_idx, col_idx]
    # 东南角对应源图像 row=(23-22.15)*1200, col=(114.35-114)*1200
    row_idx_se = int(round((23.0 - 22.15) * (n - 1)))
    col_idx_se = int(round((114.35 - 114.0) * (n - 1)))
    assert crop[-1, -1] == dem[row_idx_se, col_idx_se]


def test_hillshade_orientation_contract():
    # 北半部一个高斯丘、南半部 0：行 0（图像顶部/NW）应更暗（alpha 更大）
    y = np.arange(20)
    x = np.arange(20)
    Y, X = np.meshgrid(y, x, indexing="ij")
    dem = 100 * np.exp(-((Y - 5) ** 2 + (X - 10) ** 2) / 15).astype(np.float32)
    dem[Y >= 10] = 0.0
    rgba = elevation.hillshade_rgba(dem, dx_m=30, dy_m=30)
    assert rgba[:10, :, 3].mean() > rgba[10:, :, 3].mean()


def test_elevation_tint_uses_four_neutral_height_bands():
    dem = np.array([[0, 49, 50, 99, 100, 149, 150, 220]], dtype=np.float32)

    rgba = elevation.elevation_tint_rgba(dem)

    assert rgba.shape == (1, 8, 4)
    assert rgba.dtype == np.uint8
    assert rgba[0, 0, 3] == 0
    assert len({tuple(pixel) for pixel in rgba[0, 1:]}) == 4
    assert all(abs(int(pixel[0]) - int(pixel[1])) < 25 for pixel in rgba[0, 1:])


def test_fill_voids_all_nan():
    dem = np.full((5, 5), np.nan)
    filled = elevation.fill_voids(dem)
    assert filled.shape == (5, 5)
    assert filled.dtype == np.float32
    assert np.all(filled == 0)


def test_contour_lines_empty_levels():
    dem = np.full((10, 10), 5.0)
    lons = np.linspace(114.0, 114.1, 10)
    lats = np.linspace(22.0, 22.1, 10)
    gdf = elevation.contour_lines(dem, lons, lats, interval=10)
    assert gdf.empty
    assert "ele" in gdf.columns
    assert gdf.crs.to_string() == "EPSG:4326"
