/* CUHK V3 校园地图：MapLibre 初始化 + POI marker + 分类筛选 + 校巴方向
 * 数据全部来自本地 ./data/（由 cuhk/scripts/build_data.py 生成），零外部请求。
 */

const CUHK_CENTER = [114.2070, 22.4205];
const CUHK_MAX_BOUNDS = [[114.1900, 22.4040], [114.2230, 22.4360]];

const map = new maplibregl.Map({
  container: "map",
  style: "style.json",
  center: CUHK_CENTER,
  zoom: 15,
  hash: true,
  minZoom: 14.8,
  maxZoom: 18,
  maxBounds: CUHK_MAX_BOUNDS,
  renderWorldCopies: false,
  maxPitch: 65,
  attributionControl: { compact: true },
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

/* ---------- 工具 ---------- */

async function loadJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url}: HTTP ${resp.status}`);
  return resp.json();
}

const escapeHTML = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

let mapReady = false;
const poiMarkers = [];
const officialBuildingMarkers = [];
let routeCatalog = [];
let shuttleRoutesGeoJSON = null;
let routeBadge = null;
let routeRecordingActive = false;
let routeRecordingId = "";
let routeRecordingPoints = [];

function showError() {
  document.getElementById("error-overlay").classList.remove("hidden");
}

map.on("error", (e) => {
  console.error(e);
  if (!mapReady) showError();
});

/* ---------- 点状纹理（prettymaps hatch 风格） ---------- */

function makeDotsImage(color) {
  const size = 12;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(3, 3, 1.6, 0, Math.PI * 2);
  ctx.arc(9, 9, 1.6, 0, Math.PI * 2);
  ctx.fill();
  const img = ctx.getImageData(0, 0, size, size);
  return { width: size, height: size, data: new Uint8Array(img.data.buffer) };
}

function addWaterHatchLayer() {
  if (!map.hasImage("dots-water")) {
    map.addImage("dots-water", makeDotsImage("#9bc3d4"));
  }
  map.addLayer(
    {
      id: "water-hatch",
      type: "fill",
      source: "water",
      paint: { "fill-pattern": "dots-water" },
    },
    "green"
  );
}

/* ---------- 可选高程分层（默认关闭，不启用 3D terrain） ---------- */

async function addTerrainTint() {
  const meta = await loadJSON("data/terrain-tint.json");
  map.addSource("terrain-tint", {
    type: "image",
    url: "data/terrain-tint.png",
    coordinates: meta.coordinates,
  });
  map.addLayer(
    {
      id: "terrain-tint",
      type: "raster",
      source: "terrain-tint",
      layout: { visibility: "none" },
      paint: { "raster-opacity": 0.78, "raster-resampling": "linear" },
    },
    "contours"
  );
}

function wireTerrainButton() {
  const btn = document.getElementById("btnTerrain");
  const legend = document.getElementById("terrain-legend");
  let visible = false;
  btn.disabled = false;
  btn.addEventListener("click", () => {
    visible = !visible;
    for (const id of ["terrain-tint", "contours"]) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
    btn.classList.toggle("active", visible);
    btn.setAttribute("aria-pressed", String(visible));
    legend.classList.toggle("hidden", !visible);
  });
}

/* ---------- POI markers ---------- */

function popupHTML(props) {
  const description = props.desc ? `<p>${escapeHTML(props.desc)}</p>` : "";
  return `<div class="pop">
    <div class="zh">${escapeHTML(props.name_zh)}</div>
    <div class="en">${escapeHTML(props.name_en)}</div>
    ${description}
  </div>`;
}

function addPOIMarkers(geojson) {
  for (const feat of geojson.features) {
    const p = feat.properties;
    const el = document.createElement("div");
    el.className = `poi-marker cat-${p.category}`;
    el.classList.add(`poi-${p.id}`);
    el.innerHTML = `<div class="dot"></div>
      <div class="lbl"><div class="zh">${escapeHTML(p.name_zh)}</div><div class="en">${escapeHTML(p.name_en)}</div></div>`;
    const popup = new maplibregl.Popup({ maxWidth: "280px", offset: 12 }).setHTML(popupHTML(p));
    const marker = new maplibregl.Marker({ element: el })
      .setLngLat(feat.geometry.coordinates)
      .setPopup(popup)
      .addTo(map);
    poiMarkers.push({ id: `poi-${p.id}`, kind: "poi", props: p, coordinates: feat.geometry.coordinates, el, marker });
  }
  updatePOILabels();
}

function addOfficialBuildingLabels(geojson, poisGeoJSON) {
  const features = CUHKAppCore.dedupeBuildingFeatures(
    geojson.features || [],
    (poisGeoJSON && poisGeoJSON.features) || []
  );
  features.forEach((feat, index) => {
    const p = feat.properties || {};
    const el = document.createElement("div");
    el.className = "building-label-marker label-hidden";
    el.innerHTML = `<div class="lbl"><div class="zh">${escapeHTML(p.name_zh)}</div><div class="en">${escapeHTML(p.name_en)}</div></div>`;
    const popup = new maplibregl.Popup({ maxWidth: "280px", offset: 8 }).setHTML(popupHTML(p));
    const marker = new maplibregl.Marker({ element: el })
      .setLngLat(feat.geometry.coordinates)
      .setPopup(popup)
      .addTo(map);
    officialBuildingMarkers.push({
      id: `building-${index}`,
      kind: "building",
      props: p,
      coordinates: feat.geometry.coordinates,
      el,
      marker,
    });
  });
  updatePOILabels();
}

function estimateLabelBox(item) {
  const point = map.project(item.coordinates);
  const building = item.kind === "building";
  const zhWidth = Array.from(String(item.props.name_zh || "")).length * (building ? 10 : 12);
  const enWidth = String(item.props.name_en || "").length * (building ? 5.2 : 6.1);
  const width = Math.max(building ? 34 : 42, zhWidth, enWidth) + 4;
  const height = building ? 24 : 30;
  if (building) {
    return [point.x - width / 2, point.y - height / 2, point.x + width / 2, point.y + height / 2];
  }
  const placeLeft = item.props.id === "university-station-west";
  const x1 = placeLeft ? point.x - 15 - width : point.x + 15;
  return [x1, point.y - height / 2, x1 + width, point.y + height / 2];
}

function updatePOILabels() {
  if (!poiMarkers.length && !officialBuildingMarkers.length) return;
  const zoom = map.getZoom();
  const allowPOILabels = zoom >= 13.8;
  const allowBuildingLabels = CUHKAppCore.buildingLabelsEnabled(zoom);
  const canvas = map.getCanvas();
  const activeItems = [
    ...(allowPOILabels ? poiMarkers : []),
    ...(allowBuildingLabels ? officialBuildingMarkers : []),
  ];
  const candidates = activeItems
    .filter((item) => !item.el.classList.contains("hidden"))
    .map((item) => ({
      id: item.id,
      priority: item.kind === "building"
        ? CUHKAppCore.officialBuildingPriority(item.props)
        : CUHKAppCore.labelPriority(item.props),
      box: estimateLabelBox(item),
    }))
    .filter((item) => (
      item.box[2] >= 0 && item.box[0] <= canvas.clientWidth &&
      item.box[3] >= 58 && item.box[1] <= canvas.clientHeight
  ));
  const visible = new Set(
    CUHKAppCore.selectNonOverlappingLabels(
      candidates,
      CUHKAppCore.labelCollisionPadding(zoom)
    )
  );
  for (const item of [...poiMarkers, ...officialBuildingMarkers]) {
    item.el.classList.toggle("label-hidden", !visible.has(item.id));
  }
}

/* ---------- 分类筛选 chips ---------- */

function wireChips() {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const cat = chip.dataset.cat;
      chip.classList.toggle("off");
      const show = !chip.classList.contains("off");
      chip.setAttribute("aria-pressed", String(show));
      document
        .querySelectorAll(`.poi-marker.cat-${cat}`)
        .forEach((m) => m.classList.toggle("hidden", !show));
      updatePOILabels();
    });
  });
}

/* ---------- 校巴筛选与方向 ---------- */

function makeArrowImage(color) {
  const size = 24;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(3, 5);
  ctx.lineTo(21, 12);
  ctx.lineTo(3, 19);
  ctx.lineTo(7, 12);
  ctx.closePath();
  ctx.fill();
  const image = ctx.getImageData(0, 0, size, size);
  return { width: size, height: size, data: new Uint8Array(image.data.buffer) };
}

function addBusArrowLayer() {
  if (!map.hasImage("shuttle-arrow")) {
    map.addImage("shuttle-arrow", makeArrowImage("#2F3737"));
  }
  if (!map.getLayer("shuttle-arrows")) {
    map.addLayer({
      id: "shuttle-arrows",
      type: "symbol",
      source: "shuttle_routes",
      layout: {
        visibility: "none",
        "symbol-placement": "line",
        "symbol-spacing": 90,
        "icon-image": "shuttle-arrow",
        "icon-size": 0.55,
        "icon-rotation-alignment": "map",
        "icon-keep-upright": false,
        "icon-allow-overlap": true,
      },
    });
  }
}

function applyBusSelection(selection) {
  const visible = selection !== "off";
  for (const id of ["shuttle-routes", "shuttle-route-variants", "shuttle-stops", "shuttle-arrows"]) {
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
  map.setFilter("shuttle-routes", CUHKAppCore.routeVariantFilter(selection, false));
  map.setFilter("shuttle-route-variants", CUHKAppCore.routeVariantFilter(selection, true));
  map.setFilter("shuttle-arrows", CUHKAppCore.routeFilter(selection));
  map.setFilter("shuttle-stops", CUHKAppCore.stopFilter(selection));
  map.setPaintProperty("shuttle-routes", "line-color", CUHKAppCore.routeColor(selection));
  map.setPaintProperty("shuttle-route-variants", "line-color", CUHKAppCore.routeColor(selection));
  renderBusRouteInfo(selection);
  updateRouteBadge(selection);
}

function routeInfoItem(route) {
  const conditions = (route.conditions || []).map((condition) =>
    `<div class="route-condition">${escapeHTML(condition.zh)}${condition.zh && condition.en ? " / " : ""}${escapeHTML(condition.en)}</div>`
  ).join("");
  return `<div class="bus-route-item">
    <span class="bus-route-swatch" style="background:${escapeHTML(route.color || "#5C95B7")}"></span>
    <div><div><strong class="bus-route-code">${escapeHTML(route.routeId)}</strong> ${escapeHTML(route.nameZh)}</div>
      <div class="route-en">${escapeHTML(route.nameEn)}</div>
      ${conditions}
    </div>
  </div>`;
}

function routeGroupHTML(group) {
  return `<section class="bus-service-group">
    <div class="bus-service-label">${escapeHTML(group.label)}</div>
    ${group.routes.map(routeInfoItem).join("")}
  </section>`;
}

function renderBusRouteInfo(selection) {
  const panel = document.getElementById("bus-route-info");
  if (!panel) return;
  if (!selection || selection === "off") {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  const routes = selection === "all"
    ? routeCatalog
    : routeCatalog.filter((route) => route.routeId === String(selection));
  const groups = CUHKAppCore.routeGroups(routes);
  panel.innerHTML = `<div class="bus-route-title">校巴服務 Shuttle Service</div>${groups.map(routeGroupHTML).join("")}`;
  panel.classList.remove("hidden");
}

function middleCoordinate(geometry) {
  if (!geometry) return null;
  const lines = geometry.type === "MultiLineString" ? geometry.coordinates : [geometry.coordinates];
  const line = lines.reduce((best, current) => current.length > best.length ? current : best, []);
  return line.length ? line[Math.floor((line.length - 1) / 2)] : null;
}

function updateRouteBadge(selection) {
  if (routeBadge) {
    routeBadge.remove();
    routeBadge = null;
  }
  if (!shuttleRoutesGeoJSON || !selection || selection === "off" || selection === "all") return;
  const route = routeCatalog.find((item) => item.routeId === String(selection));
  const feature = shuttleRoutesGeoJSON.features.find(
    (item) => route && String(item.properties.route_id) === route.routeId && !item.properties.is_conditional
  );
  const coordinates = feature && middleCoordinate(feature.geometry);
  if (!coordinates) return;
  const el = document.createElement("div");
  el.className = "route-badge";
  el.textContent = route ? route.badgeLabel : "校巴";
  el.title = route ? `${route.groupLabel} · ${route.label}` : "";
  routeBadge = new maplibregl.Marker({ element: el }).setLngLat(coordinates).addTo(map);
}

/* ---------- 校巴真实走线录制 ---------- */

function refreshRouteRecording() {
  const data = CUHKAppCore.routeRecordingGeoJSON(routeRecordingId, routeRecordingPoints);
  map.getSource("route-recording").setData(data);
  document.getElementById("recorderRouteId").textContent = routeRecordingId;
  document.getElementById("recorderPoints").innerHTML = routeRecordingPoints.map((point, index) => {
    const label = point.kind === "stop"
      ? `${point.nameZh || point.nameEn || point.stopId}（站点）`
      : `道路控制点 ${point.coordinates.map((value) => value.toFixed(5)).join(", ")}`;
    return `<li class="${point.kind === "waypoint" ? "waypoint" : ""}">${index + 1}. ${escapeHTML(label)}</li>`;
  }).join("");
}

function setRouteRecordingActive(active) {
  routeRecordingActive = active;
  const button = document.getElementById("btnRecordRoute");
  const panel = document.getElementById("route-recorder");
  button.classList.toggle("active", active);
  document.body.classList.toggle("route-recording-active", active);
  button.setAttribute("aria-pressed", String(active));
  panel.classList.toggle("hidden", !active);
  map.setLayoutProperty("recording-stop-candidates", "visibility", active ? "visible" : "none");
  map.setLayoutProperty("route-recording-line", "visibility", active ? "visible" : "none");
  map.setLayoutProperty("route-recording-points", "visibility", active ? "visible" : "none");
  map.getCanvas().style.cursor = active ? "crosshair" : "";
  if (!active) renderBusRouteInfo(document.getElementById("busRouteSelect").value);
}

function startRouteRecording() {
  const select = document.getElementById("busRouteSelect");
  if (!select.value || select.value === "off" || select.value === "all") {
    select.value = "1A";
    applyBusSelection("1A");
  }
  routeRecordingId = select.value;
  routeRecordingPoints = [];
  document.getElementById("bus-route-info").classList.add("hidden");
  setRouteRecordingActive(true);
  refreshRouteRecording();
}

function handleRouteRecordingClick(event) {
  if (!routeRecordingActive) return;
  const box = [[event.point.x - 10, event.point.y - 10], [event.point.x + 10, event.point.y + 10]];
  const candidates = map.queryRenderedFeatures(box, { layers: ["recording-stop-candidates"] });
  const stop = candidates[0];
  if (stop) {
    routeRecordingPoints.push({
      coordinates: [...stop.geometry.coordinates],
      kind: "stop",
      stopId: stop.properties.stop_id,
      nameZh: stop.properties.name_zh,
      nameEn: stop.properties.name_en,
    });
  } else {
    routeRecordingPoints.push({ coordinates: [event.lngLat.lng, event.lngLat.lat], kind: "waypoint" });
  }
  refreshRouteRecording();
}

function exportRouteRecording() {
  const data = CUHKAppCore.exportRouteRecording(routeRecordingId, routeRecordingPoints);
  const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `cuhk-shuttle-${routeRecordingId}-recording.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function wireRouteRecorder() {
  map.addSource("route-recording", { type: "geojson", data: CUHKAppCore.routeRecordingGeoJSON("", []) });
  map.addLayer({
    id: "recording-stop-candidates", type: "circle", source: "shuttle_stops",
    layout: { visibility: "none" },
    paint: { "circle-radius": 8, "circle-color": "#FFE16A", "circle-stroke-color": "#2F3737", "circle-stroke-width": 2 },
  });
  map.addLayer({
    id: "route-recording-line", type: "line", source: "route-recording",
    filter: ["==", ["geometry-type"], "LineString"], layout: { visibility: "none" },
    paint: { "line-color": "#D84A3A", "line-width": 5, "line-opacity": 0.9 },
  });
  map.addLayer({
    id: "route-recording-points", type: "circle", source: "route-recording",
    filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" },
    paint: { "circle-radius": 6, "circle-color": ["match", ["get", "kind"], "stop", "#FFE16A", "#FFFFFF"], "circle-stroke-color": "#D84A3A", "circle-stroke-width": 3 },
  });
  document.getElementById("btnRecordRoute").addEventListener("click", () => routeRecordingActive ? setRouteRecordingActive(false) : startRouteRecording());
  document.getElementById("recorderClose").addEventListener("click", () => setRouteRecordingActive(false));
  document.getElementById("recorderUndo").addEventListener("click", () => { routeRecordingPoints.pop(); refreshRouteRecording(); });
  document.getElementById("recorderClear").addEventListener("click", () => { routeRecordingPoints = []; refreshRouteRecording(); });
  document.getElementById("recorderExport").addEventListener("click", exportRouteRecording);
  map.on("click", handleRouteRecordingClick);
}

async function wireBusRouteSelect() {
  const select = document.getElementById("busRouteSelect");
  try {
    shuttleRoutesGeoJSON = await loadJSON("data/shuttle_routes.geojson");
    routeCatalog = CUHKAppCore.routeOptions(shuttleRoutesGeoJSON).map((route) => ({
      ...route,
      conditions: CUHKAppCore.routeConditions(shuttleRoutesGeoJSON, route.routeId),
    }));
    for (const group of CUHKAppCore.routeGroups(routeCatalog)) {
      const optgroup = document.createElement("optgroup");
      optgroup.label = group.label;
      for (const route of group.routes) {
        const option = document.createElement("option");
        option.value = route.routeId;
        option.textContent = route.label;
        optgroup.appendChild(option);
      }
      select.appendChild(optgroup);
    }
    select.disabled = false;
    select.addEventListener("change", () => applyBusSelection(select.value));
    applyBusSelection(select.value);
  } catch (error) {
    select.disabled = true;
    console.warn("校巴线路加载失败，筛选器已停用：", error);
  }

  for (const layer of ["shuttle-routes", "shuttle-route-variants", "shuttle-stops"]) {
    map.on("click", layer, (e) => {
      if (routeRecordingActive) return;
      const p = e.features[0].properties;
      new maplibregl.Popup({ maxWidth: "280px" })
        .setLngLat(e.lngLat)
        .setHTML(popupHTML({ name_zh: p.name_zh, name_en: p.name_en, desc: p.desc || "" }))
        .addTo(map);
    });
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }
}

/* ---------- 启动 ---------- */

map.on("load", async () => {
  // 核心数据探测失败 = 管线没跑过 → 显示错误浮层并放弃启动
  try {
    await loadJSON("data/buildings.geojson");
  } catch (e) {
    console.error(e);
    showError();
    return;
  }
  addWaterHatchLayer();
  // 非核心资源各自降级：缺高程着色 / POI 不影响地图其余部分
  try {
    await addTerrainTint();
    wireTerrainButton();
  } catch (e) {
    console.warn("terrain tint 加载失败，地形开关已停用：", e);
  }
  let pois = { features: [] };
  try {
    pois = await loadJSON("data/pois.geojson");
    addPOIMarkers(pois);
  } catch (e) {
    console.warn("pois.geojson 加载失败，跳过 POI 标注：", e);
  }
  try {
    const officialBuildings = await loadJSON("data/official_buildings.geojson");
    addOfficialBuildingLabels(officialBuildings, pois);
  } catch (e) {
    console.warn("official_buildings.geojson 加载失败，跳过官方楼名：", e);
  }
  wireChips();
  addBusArrowLayer();
  await wireBusRouteSelect();
  wireRouteRecorder();
  updatePOILabels();
  map.on("move", updatePOILabels);
  map.on("resize", updatePOILabels);
  mapReady = true;
});
