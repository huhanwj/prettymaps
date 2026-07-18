import pathlib
import sys

import pytest
from shapely.geometry import LineString, Polygon, box

# 让测试可以 import cuhk/scripts/pipeline 下的模块
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

HK_BBOX = (113.8, 22.1, 114.5, 22.6)  # (min_lon, min_lat, max_lon, max_lat)


@pytest.fixture
def campus_square():
    """合成'校园'多边形：约 1km 见方，位于 CUHK 真实位置。"""
    return box(114.200, 22.415, 114.210, 22.425)


@pytest.fixture
def synthetic_relation():
    """合成 Overpass relation JSON：两条 outer way 拼成正方形 + 一条 inner way 挖洞。"""
    def way(wid, coords, role):
        return {
            "type": "way",
            "id": wid,
            "role": role,
            "geometry": [{"lat": lat, "lon": lon} for lon, lat in coords],
        }

    outer1 = [(114.200, 22.415), (114.210, 22.415), (114.210, 22.425)]
    outer2 = [(114.210, 22.425), (114.200, 22.425), (114.200, 22.415)]
    inner = [(114.204, 22.419), (114.206, 22.419), (114.206, 22.421), (114.204, 22.421), (114.204, 22.419)]
    return {
        "elements": [
            {
                "type": "relation",
                "id": 7802779,
                "members": [
                    way(101, outer1, "outer"),
                    way(102, outer2, "outer"),
                    way(103, inner, "inner"),
                ],
            }
        ]
    }
