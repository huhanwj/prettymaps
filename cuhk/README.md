# CUHK 校园迎新地图

面向新生的香港中文大学交互式网页地图：prettymaps 插画风、中英双语地点标注、
等高线 + 山体阴影 + 3D 建筑表现山城高差。纯静态、零外部依赖，可离线运行。

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

- 改地点：编辑 `cuhk/data/pois.yml`（42 条中英双语 POI），重跑管线
- 改样式：编辑 `cuhk/site/style.json`（配色取自 prettymaps default preset），刷新页面即可
- 改交互：编辑 `cuhk/site/app.js`

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
