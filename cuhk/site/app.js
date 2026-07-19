/* CUHK V3 校园地图：MapLibre 初始化 + POI marker + 分类筛选 + 校巴方向
 * 数据全部来自本地 ./data/（由 cuhk/scripts/build_data.py 生成），零外部请求。
 */

const CUHK_CENTER = [114.2070, 22.4205];

const map = new maplibregl.Map({
  container: "map",
  style: "style.json",
  center: CUHK_CENTER,
  zoom: 14.6,
  hash: true,
  minZoom: 12.5,
  maxZoom: 18,
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
  return `<div class="pop">
    <div class="zh">${escapeHTML(props.name_zh)}</div>
    <div class="en">${escapeHTML(props.name_en)}</div>
    <p>${escapeHTML(props.desc)}</p>
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
    new maplibregl.Marker({ element: el })
      .setLngLat(feat.geometry.coordinates)
      .setPopup(popup)
      .addTo(map);
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
  for (const id of ["shuttle-routes", "shuttle-stops", "shuttle-arrows"]) {
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
  map.setFilter("shuttle-routes", CUHKAppCore.routeFilter(selection));
  map.setFilter("shuttle-arrows", CUHKAppCore.routeFilter(selection));
  map.setFilter("shuttle-stops", CUHKAppCore.stopFilter(selection));
}

async function wireBusRouteSelect() {
  const select = document.getElementById("busRouteSelect");
  try {
    const routes = await loadJSON("data/shuttle_routes.geojson");
    for (const route of CUHKAppCore.routeOptions(routes)) {
      const option = document.createElement("option");
      option.value = route.routeId;
      option.textContent = route.label;
      select.appendChild(option);
    }
    select.disabled = false;
    select.addEventListener("change", () => applyBusSelection(select.value));
    applyBusSelection(select.value);
  } catch (error) {
    select.disabled = true;
    console.warn("校巴线路加载失败，筛选器已停用：", error);
  }

  for (const layer of ["shuttle-routes", "shuttle-stops"]) {
    map.on("click", layer, (e) => {
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

/* ---------- 标注密度随缩放变化 ---------- */

function updateZoomClass() {
  const z = map.getZoom();
  document.body.classList.toggle("z-mid", z >= 14.5);
  document.body.classList.toggle("z-high", z >= 15.5);
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
  try {
    const pois = await loadJSON("data/pois.geojson");
    addPOIMarkers(pois);
  } catch (e) {
    console.warn("pois.geojson 加载失败，跳过 POI 标注：", e);
  }
  wireChips();
  addBusArrowLayer();
  await wireBusRouteSelect();
  updateZoomClass();
  map.on("zoom", updateZoomClass);
  mapReady = true;
});
