(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.CUHKAppCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const noRoute = () => ["==", ["get", "route_id"], "__none__"];
  const noStop = () => ["==", ["get", "route_ids"], "__none__"];

  const PUBLIC_ROUTES = [
    { routeId: "1A", nameZh: "本部线", nameEn: "Main Campus", color: "#D84A3A", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "1B", nameZh: "本部线（经研究生宿舍）", nameEn: "Main Campus via PGH", color: "#E26C3A", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "2", nameZh: "新联线", nameEn: "NA / UC", color: "#D79C2F", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "3", nameZh: "逸夫线", nameEn: "Shaw", color: "#4C8B62", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "4", nameZh: "环回线", nameEn: "Campus Circuit", color: "#3A8C91", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "8", nameZh: "西部线", nameEn: "Western Campus", color: "#3976A8", groupKey: "campus", groupLabel: "穿梭校巴 / Campus shuttle" },
    { routeId: "5", nameZh: "上行线", nameEn: "Upward", color: "#7159A6", groupKey: "meet-class", groupLabel: "转堂校巴 / Meet-class" },
    { routeId: "6A", nameZh: "下行线（敬文）", nameEn: "Downward (CW Chu)", color: "#A15396", groupKey: "meet-class", groupLabel: "转堂校巴 / Meet-class" },
    { routeId: "6B", nameZh: "下行线（新联）", nameEn: "Downward (NA / UC)", color: "#B34E72", groupKey: "meet-class", groupLabel: "转堂校巴 / Meet-class" },
    { routeId: "7", nameZh: "下行线（逸夫）", nameEn: "Downward (Shaw)", color: "#C1534D", groupKey: "meet-class", groupLabel: "转堂校巴 / Meet-class" },
    { routeId: "N", nameZh: "晚间线", nameEn: "Night", color: "#334B6E", groupKey: "special", groupLabel: "晚间及假日 / Night & holiday" },
    { routeId: "H", nameZh: "假日线", nameEn: "Holiday", color: "#5D6470", groupKey: "special", groupLabel: "晚间及假日 / Night & holiday" },
  ];

  function publicRouteCatalog() {
    return PUBLIC_ROUTES.map((route) => ({
      ...route,
      label: `${route.routeId} · ${route.nameZh} / ${route.nameEn}`,
      badgeLabel: route.routeId,
    }));
  }

  function publicRoute(selection) {
    return PUBLIC_ROUTES.find((route) => route.routeId === String(selection));
  }

  function routeColor(selection) {
    const route = publicRoute(selection);
    return route ? route.color : ["get", "color"];
  }

  function routeFilter(selection) {
    if (selection === "all") return null;
    if (!selection || selection === "off") return noRoute();
    return ["==", ["get", "route_id"], String(selection)];
  }

  function routeVariantFilter(selection, conditional) {
    const variant = ["==", ["get", "is_conditional"], Boolean(conditional)];
    const route = routeFilter(selection);
    return route ? ["all", variant, route] : variant;
  }

  function stopFilter(selection) {
    if (selection === "all") return null;
    if (!selection || selection === "off") return noStop();
    return ["in", `|${String(selection)}|`, ["get", "route_ids"]];
  }

  function routeConditions(geojson, routeId) {
    const unique = new Map();
    for (const feature of (geojson && geojson.features) || []) {
      const props = feature.properties || {};
      if (String(props.route_id) !== String(routeId) || !props.is_conditional) continue;
      const zh = String(props.condition_zh || "").trim();
      const en = String(props.condition_en || "").trim();
      const key = `${zh}\n${en}`;
      if ((zh || en) && !unique.has(key)) unique.set(key, { zh, en });
    }
    return Array.from(unique.values());
  }

  function routeOptions() {
    // Public route identifiers are the user-facing API. The archived GeoJSON
    // route_id values are only geometry components and must never become labels.
    return publicRouteCatalog();
  }

  function routeGroups(routes) {
    const groups = new Map();
    for (const route of routes || []) {
      if (!groups.has(route.groupKey)) {
        groups.set(route.groupKey, { key: route.groupKey, label: route.groupLabel, routes: [] });
      }
      groups.get(route.groupKey).routes.push(route);
    }
    return Array.from(groups.values());
  }

  const HIGH_PRIORITY_IDS = new Set([
    "yia", "ul", "science-centre", "chung-chi", "new-asia", "united", "shaw",
    "sports-centre", "haddon-cave", "swimming-pool", "university-station-north",
    "university-station-west", "bus-terminus", "mall", "harmony", "uadmin",
  ]);

  function labelPriority(props) {
    if (HIGH_PRIORITY_IDS.has(String(props.id || ""))) return 1;
    const categoryRank = {
      transport: 2,
      study: 3,
      sports: 4,
      landmark: 5,
      life: 6,
    };
    return categoryRank[props.category] || 7;
  }

  function boxesOverlap(a, b, padding) {
    return !(
      a[2] + padding <= b[0] || b[2] + padding <= a[0] ||
      a[3] + padding <= b[1] || b[3] + padding <= a[1]
    );
  }

  function selectNonOverlappingLabels(candidates, padding = 4) {
    const ordered = [...candidates].sort(
      (a, b) => a.priority - b.priority || String(a.id).localeCompare(String(b.id))
    );
    const accepted = [];
    for (const candidate of ordered) {
      if (accepted.some((item) => boxesOverlap(candidate.box, item.box, padding))) continue;
      accepted.push(candidate);
    }
    return accepted.map((item) => item.id);
  }

  function normalizeLabelName(value) {
    return String(value || "")
      .normalize("NFKC")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, "");
  }

  function buildingLabelsEnabled(zoom) {
    return Number(zoom) >= 15.8;
  }

  function labelCollisionPadding(zoom) {
    return Number(zoom) >= 16 ? 1 : 5;
  }

  function officialBuildingPriority(props) {
    const type = String((props && props.type) || "").trim().toLowerCase();
    const rank = { "": 20, others: 22, student: 24, staff: 25, guest: 26 };
    return rank[type] || 23;
  }

  function dedupeBuildingFeatures(buildingFeatures, poiFeatures) {
    const used = new Set();
    for (const feature of poiFeatures || []) {
      const props = feature.properties || {};
      for (const name of [props.name_zh, props.name_en]) {
        const key = normalizeLabelName(name);
        if (key) used.add(key);
      }
    }
    const result = [];
    for (const feature of buildingFeatures || []) {
      const props = feature.properties || {};
      const keys = [props.name_zh, props.name_en]
        .map(normalizeLabelName)
        .filter(Boolean);
      if (!keys.length || keys.some((key) => used.has(key))) continue;
      result.push(feature);
      for (const key of keys) used.add(key);
    }
    return result;
  }

  function routeRecordingGeoJSON(routeId, points) {
    const normalized = (points || []).map((point, index) => ({
      type: "Feature",
      properties: {
        route_id: String(routeId),
        sequence: index + 1,
        kind: point.kind || "waypoint",
        stop_id: point.stopId || point.stop_id || "",
        name_zh: point.nameZh || point.name_zh || "",
        name_en: point.nameEn || point.name_en || "",
      },
      geometry: { type: "Point", coordinates: [...point.coordinates] },
    }));
    const line = {
      type: "Feature",
      properties: { route_id: String(routeId), kind: "preview" },
      geometry: {
        type: "LineString",
        coordinates: normalized.length >= 2
          ? normalized.map((feature) => feature.geometry.coordinates)
          : [],
      },
    };
    return { type: "FeatureCollection", features: [line, ...normalized] };
  }

  function exportRouteRecording(routeId, points) {
    return {
      format: "cuhk-shuttle-recording-v1",
      route_id: String(routeId),
      points: (points || []).map((point, index) => ({
        sequence: index + 1,
        kind: point.kind || "waypoint",
        coordinates: [...point.coordinates],
        ...(point.stopId || point.stop_id ? { stop_id: point.stopId || point.stop_id } : {}),
        ...(point.nameZh || point.name_zh ? { name_zh: point.nameZh || point.name_zh } : {}),
        ...(point.nameEn || point.name_en ? { name_en: point.nameEn || point.name_en } : {}),
      })),
    };
  }

  return {
    publicRouteCatalog,
    routeColor,
    routeFilter,
    routeVariantFilter,
    stopFilter,
    routeConditions,
    routeOptions,
    routeGroups,
    labelPriority,
    selectNonOverlappingLabels,
    normalizeLabelName,
    buildingLabelsEnabled,
    labelCollisionPadding,
    officialBuildingPriority,
    dedupeBuildingFeatures,
    routeRecordingGeoJSON,
    exportRouteRecording,
  };
});
