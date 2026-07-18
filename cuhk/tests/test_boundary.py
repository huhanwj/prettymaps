from pipeline import boundary


def test_assemble_multipolygon_with_hole(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    # 外正方形面积 0.01*0.01，内洞 0.002*0.002
    assert abs(geom.area - (0.01 * 0.01 - 0.002 * 0.002)) < 1e-12


def test_buffer_polygon_meters(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    buffered = boundary.buffer_polygon_meters(geom, 800)
    # buffer 后面积必须变大，且仍然合法
    assert buffered.area > geom.area
    assert buffered.is_valid
    # CRS 必须是经纬度
    assert abs(buffered.bounds[0] - 114.2) < 0.05
