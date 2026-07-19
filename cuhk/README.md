# CUHK 校园迎新地图

面向新生的香港中文大学交互式网页地图：prettymaps 插画风、中英双语地点标注、
官方书院配色、天桥/楼梯和带方向的校巴线路。纯静态、零前端外部依赖，可离线运行。

## 快速开始

```bash
# 0. 装依赖（Python 3.11+）
pip install -r cuhk/requirements.txt

# 1. 跑数据管线（需要网络抓 OSM/SRTM，约 3-10 分钟，之后有缓存；
#    产出写入 cuhk/site/data/，该目录被 gitignore，必须本机生成）
python cuhk/scripts/build_data.py

# 2. 启动本地服务并打开地图（Windows）
cuhk\site\start.bat
# 或 macOS/Linux：
bash cuhk/site/start.sh
```

浏览器打开 http://localhost:12580/ 即可。`file://` 直接双击 index.html 无法工作
（浏览器限制 fetch/Web Worker），必须走 http.server。

## 修改内容

- 改地点：编辑 `cuhk/data/pois.yml`（43 条中英双语 POI），重跑管线
- 改样式：编辑 `cuhk/site/style.json`（书院配色取自官方校园 PDF），刷新页面即可
- 改交互：编辑 `cuhk/site/app.js`

## 主要功能

- **书院配色**：建筑按官方 `campus_id` 区分中央校园及九所书院，底图以白色留白为主
- **天桥与楼梯**：实心蓝线表示天桥，蓝色虚线表示楼梯或明显高差通道
- **校巴线路**：可关闭、显示全部或筛选单条官方线路；线路上重复显示行驶方向箭头
- **URL 分享**：地址栏 hash 携带 zoom/lat/lon/pitch，可直接分享当前视角

3D 因 V2 存在切换卡屏且无法恢复的问题，在 V3 暂时停用。详情见
[KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

## 数据来源

- 校园建筑/地标/校巴：© 香港中文大學官方校園地圖（cuhk.edu.hk）
- 书院配色及人工补齐的天桥/楼梯：`data/official/Campus-Map-YIA-LT2.pdf`
- 校外与底图要素：© OpenStreetMap contributors (ODbL)
- 高程：NASA SRTM

## 测试

```bash
python -m pytest cuhk/tests -v
```

## 常见问题

- **Overpass 超时**：重跑一次（有缓存）；或设镜像环境变量
  `CUHK_OVERPASS_URL=https://overpass.private.coffee/api/interpreter`
- **POI 匹配失败**：管线会列出未匹配的 id，对照 `cuhk/cache/names_dump.csv`
  修正 `osm_name` 或改用 `lon/lat`

## 数据与许可

地图数据 © OpenStreetMap contributors (ODbL)。视觉风格灵感来自
[prettymaps](https://github.com/marceloprates/prettymaps)。
