/* CUHK 迎新校园地图：MapLibre 初始化 + POI marker + 分类筛选 + 3D 切换
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

function addHatchLayers() {
  if (!map.hasImage("dots-green")) {
    map.addImage("dots-green", makeDotsImage("#A7C497"));
    map.addImage("dots-water", makeDotsImage("#9bc3d4"));
  }
  map.addLayer(
    {
      id: "green-hatch",
      type: "fill",
      source: "green",
      paint: { "fill-pattern": "dots-green" },
    },
    "forest"
  );
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

/* ---------- 山体阴影（image source，坐标来自 hillshade.json） ---------- */

async function addHillshade() {
  const meta = await loadJSON("data/hillshade.json");
  map.addSource("hillshade", {
    type: "image",
    url: "data/hillshade.png",
    coordinates: meta.coordinates,
  });
  map.addLayer(
    { id: "hillshade", type: "raster", source: "hillshade", paint: { "raster-opacity": 1 } },
    "sea" // 插到 sea 之下：陆上有阴影、海面干净
  );
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

/* ---------- 3D 切换 ---------- */

function wire3DButton() {
  const btn = document.getElementById("btn3d");
  let is3d = false;
  btn.addEventListener("click", () => {
    is3d = !is3d;
    map.setLayoutProperty("buildings-3d", "visibility", is3d ? "visible" : "none");
    map.setLayoutProperty("buildings-2d", "visibility", is3d ? "none" : "visible");
    map.easeTo({ pitch: is3d ? 45 : 0, duration: 800 });
    btn.textContent = is3d ? "2D 視角" : "3D 視角";
  });
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
  addHatchLayers();
  // 非核心资源各自降级：缺 hillshade / POI 不影响地图其余部分
  try {
    await addHillshade();
  } catch (e) {
    console.warn("hillshade 加载失败，跳过山体阴影：", e);
  }
  try {
    const pois = await loadJSON("data/pois.geojson");
    addPOIMarkers(pois);
  } catch (e) {
    console.warn("pois.geojson 加载失败，跳过 POI 标注：", e);
  }
  wireChips();
  wire3DButton();
  updateZoomClass();
  map.on("zoom", updateZoomClass);
  mapReady = true;
});
