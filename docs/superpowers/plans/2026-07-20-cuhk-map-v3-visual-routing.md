# CUHK Campus Map V3 实施计划

**目标：** 实现白底书院配色、PDF 校准的天桥/楼梯、可筛选且带方向箭头的校巴，并停用及记录 3D 问题。

**依据：** `docs/superpowers/specs/2026-07-20-cuhk-map-v3-visual-routing-design.md`

## 任务 1：建筑区域归属

**文件：**

- 修改 `cuhk/tests/test_building_types.py`
- 修改 `cuhk/scripts/pipeline/building_types.py`
- 修改 `cuhk/scripts/build_data.py`

步骤：

1. 先写失败测试，要求统一匹配函数同时返回 `bt` 和字符串 `campus_id`。
2. 覆盖包含优先、最近点回退、冲突时最近者胜出、未匹配为空区域标识。
3. 运行定向测试并确认因新 API 缺失而失败。
4. 提取现有空间匹配为一次计算，生成两个对齐 Series；保留 `assign_types` 兼容入口。
5. 在 `build_data.py` 写出建筑 `campus_id`。
6. 运行定向测试至通过。

## 任务 2：行人连接数据

**文件：**

- 新建 `cuhk/scripts/pipeline/pedestrian.py`
- 新建 `cuhk/tests/test_pedestrian.py`
- 新建 `cuhk/data/official/pedestrian_links.geojson`
- 修改 `cuhk/scripts/pipeline/layers.py`
- 修改 `cuhk/scripts/build_data.py`

步骤：

1. 先写失败测试，定义 OSM 分类规则：`highway=steps` 为楼梯；步行道路带 `bridge=yes` 或正 `layer` 为天桥；普通步道不进入捷径层。
2. 写失败测试校验人工 GeoJSON：只接受 `LineString`、`bridge|stairs` 和校园范围内坐标。
3. 写失败测试，要求人工数据与接近的 OSM 数据合并时人工记录优先且去重。
4. 运行定向测试并确认失败原因正确。
5. 实现最小分类、加载、校验、合并和去重逻辑。
6. 根据 PDF 与现有建筑/道路数据校准重要天桥和楼梯，写入人工 GeoJSON。
7. 管线生成 `pedestrian_links.geojson`，同时让普通道路保留现有输出。
8. 运行定向测试至通过。

## 任务 3：校巴稳定标识与站点线路

**文件：**

- 修改 `cuhk/tests/test_official.py`
- 修改 `cuhk/scripts/pipeline/official.py`
- 修改 `cuhk/scripts/build_data.py`

步骤：

1. 先写失败测试，要求路线包含 `route_id`。
2. 写失败测试，要求站点包含去重、排序后的 `route_ids`。
3. 运行测试并确认缺失字段导致失败。
4. 从官方 route-segment-stop 关系构建站点到线路的映射。
5. 写出路线 `route_id` 和站点 `route_ids`。
6. 运行定向测试至通过。

## 任务 4：V3 MapLibre 样式

**文件：**

- 新建 `cuhk/tests/test_v3_style.py`
- 修改 `cuhk/site/style.json`
- 修改 `cuhk/site/app.js`

步骤：

1. 先写失败测试，断言白色背景、道路浅蓝灰、建筑颜色表达式覆盖 `campus_id` 1–13。
2. 写失败测试，断言存在天桥实线层、楼梯虚线层、校巴箭头符号层，并且 3D 建筑默认不可见。
3. 运行定向测试并确认现有样式不满足断言。
4. 修改 `style.json`：移除绿色大面积填充、应用区域色、增加 `pedestrian_links` source 和分层样式。
5. 在 `app.js` 生成本地方向箭头图像；地图加载后添加沿线符号层，确保与线路共用过滤器。
6. 运行样式测试和 `node --check` 至通过。

## 任务 5：校巴控件与 3D 停用

**文件：**

- 新建 `cuhk/site/app-core.js`
- 新建 `cuhk/tests/js/test_app_core.js`
- 修改 `cuhk/site/app.js`
- 修改 `cuhk/site/index.html`
- 修改 `cuhk/tests/test_app_runs.py`

步骤：

1. 先写 Node 失败测试，定义关闭、全部线路、单线路三种状态产生的路线和站点过滤器。
2. 写失败测试，要求线路选项由 GeoJSON 唯一 `route_id`/名称生成。
3. 写页面失败测试，要求可见线路选择器存在、可见 3D 控件不存在、图例包含天桥和楼梯。
4. 运行测试并确认缺少核心模块/新 DOM 导致失败。
5. 实现无 DOM 依赖的 `app-core.js`，再接入 `app.js` 和 `index.html`。
6. 路线、站点和箭头层使用同一状态；加载失败时禁用选择器并警告。
7. 不再调用或注册 `wire3DButton`。
8. 运行 Node、页面和语法检查至通过。

## 任务 6：Known issue 与文档

**文件：**

- 新建 `cuhk/KNOWN_ISSUES.md`
- 修改 `cuhk/README.md`

步骤：

1. 记录 V2 3D 切换卡屏、无法恢复 2D 的复现步骤、影响、状态和 V3 缓解措施。
2. README 移除 3D 功能描述，增加 V3 视觉、捷径和校巴筛选说明，并链接 known issue。
3. 确认文档没有把 3D 描述为已修复。

## 任务 7：集成验证与视觉检查

步骤：

1. 运行所有 CUHK Python 测试。
2. 运行全部 Node 测试和 JavaScript 语法检查。
3. 解析 `style.json`，运行 `git diff --check`。
4. 运行数据管线，确认建筑 `campus_id`、`pedestrian_links`、校巴 `route_id/route_ids` 均写出。
5. 启动本地站点并检查：默认 2D 白底、书院色、天桥/楼梯图例、全部校巴、单条校巴、箭头方向和无 3D 控件。
6. 检查浏览器控制台没有新增错误。
7. 对照 spec 逐项验收，报告任何未完成或需要人工继续校准的 PDF 连接线。
