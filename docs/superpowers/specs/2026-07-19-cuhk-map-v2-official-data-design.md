# CUHK 校园地图 v2 · 官方数据版 设计文档

- 日期：2026-07-19
- 状态：已与需求方确认范围（全做）
- 上游输入：PR #1 的 6 条人工核验意见（huhanwj）
- v1 基础：`cuhk-map` 分支（管线 + 离线前端 + 55 测试 + 真实数据）

## 背景

v1 完全基于 OSM 数据，人工核验发现：建筑名/位置有偏差、缺校园捷径、无校巴、3D 无地形、建筑配色无意义、校园数据应官方为准。

**关键发现**：CUHK 官方校园地图的位置数据库 `cuhk_location_db.js`（`CUHK_MAP_DATA`，397KB）可直接下载，含 268 栋官方建筑（中英名+坐标）、19 条校巴线路（含官方颜色与折线）、51 个校巴站、26 个官方地标、2 条官方步行捷径（encoded polyline）。校园内数据以它为准；校外（大学站周边、赤泥坪、科学园、码头）继续用 OSM。

## 逐条意见 → 方案

| 评论 | 方案 | 数据来源 |
|---|---|---|
| 1. 建筑名/位置错 | POI 校正链：官方坐标优先，lon/lat 其次，OSM 兜底 | official buildings/landmarks |
| 2. 缺捷径 | 官方步行捷径（绿色虚线）+ OSM steps 已有 | walking_route |
| 3. 无校巴 | "校巴模式"图层：线路（官方颜色）+ 站点 + 开关，默认可切换 | shuttle_bus_* |
| 4. 3D 无地形 | SRTM → terrain-RGB 瓦片（Mapbox 编码，z10–16）+ setTerrain，3D 按钮联动 | 已有 SRTM 缓存 |
| 5. 建筑配色懒 | 分类着色：书院=金 / 宿舍=橙 / 体育=绿 / 图书馆=蓝 / 其他=红棕交替（官方地图本身不给建筑 footprint 配色，此为官方分类 + prettymaps 调和色板） | official type/hostel_type + 名称规则 |
| 6. 校园以官方为准 | 数据集存档 `cuhk/data/official/cuhk_location_db.js`（可复现、可离线），管线新增 official 数据源 | — |

## 架构变化（v1 基础上增量）

- 管线新增 `pipeline/official.py`：下载/解析 CUHK_MAP_DATA（容错解析器 + polyline 解码）→ `official_buildings / official_landmarks / shuttle_routes / shuttle_stops / walking` GeoJSON
- 管线新增 `pipeline/terrain.py`：SRTM → terrain-RGB 瓦片 → `site/tiles/terrain-rgb/`
- `pipeline/building_types.py`：官方建筑点 → OSM 建筑面匹配 → `bt` 分类属性
- `pois.py`：解析链加 `official_name` 优先通道
- 前端：校巴开关按钮 + 校巴线图层/站点图层（点击弹窗）、walking 绿色虚线层、3D 按钮联动 setTerrain、建筑 fill-color 按 bt 分类
- `validate.py` 新增下限：official_buildings ≥200、shuttle_routes ≥10、walking ≥2
- credit 更新：校园建筑/校巴数据 © CUHK 官方校園地圖

## 不做（本轮）

- 官方 facilities（382 条）全量导入（POI 仍走 42+ 手工策划路线，避免标注爆炸；日后可按类别开）
- 实时校巴位置/时刻表（无 API）
- 官方地图 UI 复刻（仅借鉴，不抄）

## 验证

- 每任务 TDD + 两轮审查（同 v1 流程）
- 端到端：管线重跑（校验全过）+ 55+ 测试 + 三张截图（2D / 3D 含地形 / 校巴模式）人工核验 + PR 更新
