# CUHK 交互式网页地图 · 设计文档

- 日期：2026-07-18
- 状态：已与需求方确认，待实现
- 代码库：prettymaps fork（`J:\work\prettymaps`），项目代码置于 `cuhk/` 子目录，不改动 prettymaps 本体

---

## 1. 背景与目标

为香港中文大学（CUHK）新生宣传制作一张**交互式网页地图**，三个核心目标：

1. **展现学校风貌** —— 视觉上采用 prettymaps 经典插画风（奶油底 + 撞色建筑），海报级美感
2. **导航** —— 地点标注 + 点击信息弹窗（明确**不做**路线规划）
3. **体现高低差** —— CUHK 是山城（海平面至 ~140m），高差是学校的标志性特征

## 2. 需求总结（来自澄清问答）

| 项 | 决定 |
|---|---|
| 用途 | 新生宣传材料 |
| 形式 | 真·交互式网络地图（缩放/平移/倾斜），非静态图 |
| 覆盖范围 | CUHK 校园边界 + 周边一圈缓冲（含港铁大学站、马料水、科学园海滨方向） |
| POI 类别 | 学习类、生活类、体育类、交通类（另加地标类，如天人合一） |
| 标注语言 | 中英双语 |
| 部署 | 先本地静态运行（纯静态文件，日后迁移容易） |
| 视觉风格 | prettymaps 经典插画风（方案 A 配色） |
| 技术路线 | 方案 A：MapLibre GL JS + 自处理 OSM 矢量数据（见 §3） |

## 3. 技术路线选择

比较过三个方案：

- **A（已选）**：MapLibre GL JS + Python 管线自产矢量数据 + prettymaps 风自定义样式。真交互、矢量任意缩放、3D 高差、免 API key 全离线。工作量最大但唯一满足全部需求
- B：Leaflet + prettymaps 静态大图叠加。最快但位图放大模糊、建筑不可点、交互感弱
- C：MapLibre + 第三方矢量瓦片底图。需 API key、风格受限、内地 CDN 访问不稳

## 4. 整体架构

两个松耦合部分，通过静态文件衔接：

```
┌──────────────────────────────┐         ┌────────────────────────────┐
│ 数据管线 (Python, 离线运行一次) │ ──────▶ │ 前端 (纯静态站点, MapLibre)   │
│ cuhk/scripts/build_data.py   │ GeoJSON │ cuhk/site/index.html       │
│ OSM + SRTM → 分层数据文件      │ +PNG/JSON│ 本地 http.server 即可运行    │
└──────────────────────────────┘         └────────────────────────────┘
```

- 管线跑一次产出数据；之后调样式/POI 只需改前端文件或 POI 表，不用重跑
- 前端完全离线：MapLibre vendor 到本地，零 CDN、零 API key
- prettymaps 本体代码不改动；管线仅以 `json.load` 读取 `prettymaps/presets/*.json` 作为调色板来源（不 import prettymaps 包，避免 vsketch 等重依赖）
- 项目代码全部放 `cuhk/` 子目录，保持 fork 与 upstream 可合并

## 5. 数据管线设计（`cuhk/scripts/`）

入口：`python scripts/build_data.py`，产出写入 `cuhk/site/data/`。

| 步骤 | 内容 | 产出 |
|---|---|---|
| ① 范围 | 从 OSM 取 CUHK 校园边界 relation，向外 buffer ~800m（覆盖大学站、马料水、科学园海滨） | `boundary.geojson` |
| ② 图层 | osmnx 按 tag 组合抓取，图层定义沿用 prettymaps preset：建筑 / 道路 / 水体 / 绿地 / 沙滩 / 停车场，另增步道与楼梯（`highway=steps/footway/path`，山城必须） | 每层一个 `.geojson` |
| ③ 高差 | `elevation` 包下载 SRTM → 10m 间隔等高线（线要素）+ 山体阴影（半透明 PNG + 地理配准参数）。10m 间隔依据：校园高程 0–140m，约 14 条等高线，疏密合适 | `contours.geojson`、`hillshade.png` |
| ④ POI | 手工维护 `pois.yml`（约 40 个重点地点：九大书院、图书馆、食堂、体育设施、大学站、校巴站、地标），每条含中英名、分类、一句话简介。坐标两种写法：直接写 `lon/lat`，或写 OSM 对象名由管线模糊匹配取坐标（匹配失败即报错列入待处理清单，不静默丢弃） | `pois.geojson` |
| ⑤ 校验 | 断言每层非空、建筑数 >300、坐标落在香港范围内；失败即报错中止 | 控制台汇总表 |

约定：

- **POI 手工维护而非全自动抓取**：迎新内容本来就要人工把关；OSM 自动抓取中英名经常缺一（已与需求方确认）
- Overpass API 端点可配置（内地网络可一键切镜像站）
- OSM 原始数据缓存在 `cuhk/cache/`，改 `pois.yml` 不必重新抓取

## 6. 前端设计（`cuhk/site/`）

```
cuhk/site/
├── index.html                  # 唯一入口
├── vendor/maplibre-gl.{js,css} # vendor 本地化，零 CDN
├── style.json                  # 地图样式
├── data/                       # 管线产出（§5）
└── start.bat                   # 双击 → python -m http.server → 自动开浏览器
```

### 6.1 样式

- 调色板直接取自 prettymaps preset：背景 `#F2F4CB`、绿地 `#8BB174`、水体 `#a8e1e6`、建筑 `#FF5E5B`/`#433633` 撞色交替、深色道路 `#2F3737`
- 图层顺序（自底向上）：背景 → 山体阴影 → 等高线 → 绿地/水体 → 道路 → 3D 建筑 → POI 标注
- 中文标注用 MapLibre `localIdeographFontFamily`（微软雅黑/苹方等本地字体渲染），离线可显示，无需打包 CJK 字体 PBF

### 6.2 本地运行

`file://` 直接双击无法工作（Web Worker 与 fetch 受浏览器限制），故提供 `start.bat`：启动 `python -m http.server` 并自动打开浏览器。

## 7. 高低差呈现（v1 方案）

| 手法 | 说明 |
|---|---|
| 等高线（10m） | 浅色虚线，不抢戏但看得出山势 |
| 山体阴影 | 半透明叠加，平地/山坡一眼分明 |
| 3D 建筑拉伸 | MapLibre fill-extrusion，按 OSM `height` / `building:levels` 标签估算；视角倾斜（pitch ~45°）时山城立体感强 |

- 默认 2D 俯视，提供一键切换 3D 视角；支持右键拖动倾斜/旋转
- 高度缺失回退规则：无 `height` 则 `levels × 3m`；再缺则按类别默认值（书院 15m / 教学楼 12m / 其他 8m）
- **v2 可选增强**：自生成 terrain-RGB 瓦片做真 3D 地形（山坡隆起）。v1 不做，接口预留（已与需求方确认）

## 8. POI 交互

- 顶部分类筛选 chip：`学习 / 生活 / 体育 / 交通 / 地标`，点击开关对应标注
- 点击 POI 弹窗：**中文名 + 英文名 + 一句话简介**（v1 不含照片；`pois.yml` schema 预留 `photo` 字段，日后有素材即可加——已与需求方确认）
- 缩放联动：低缩放只显示大类地标，放大后 POI 逐级出现，避免标注过密

## 9. 错误处理与边界情况

- OSM 抓取失败/返回空 → 管线报错并提示切换 Overpass 镜像，不让空数据静默进前端
- 建筑高度标签缺失 → §7 回退规则
- 前端数据文件缺失 → 页面显示"请先运行 build_data.py"，不白屏
- Python 环境：本机 3.11.2（repo setup.py 声明 ≥3.12，但管线不 import prettymaps 包，只依赖 osmnx/geopandas/rasterio/elevation 等，3.11 可运行；如踩坑再建 3.12 虚拟环境）

## 10. 验证方案

- 管线：自动断言（§5 步骤⑤）+ 控制台汇总表
- 前端手工 checklist：离线打开 ✓ 缩放 ✓ 3D 倾斜 ✓ 弹窗 ✓ 分类筛选 ✓ 中英标注 ✓
- 效果确认：全图截图 + 3D 视角截图各一张，人工过目

## 11. 明确不做（v1 范围外）

- 路线规划 / 导航引擎
- 真 3D 地形（terrain-RGB）
- POI 照片展示（仅预留字段）
- 部署上线（仅本地运行）
- POI 文字搜索（v2 候选）
