(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.CUHKAppCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const noRoute = () => ["==", ["get", "route_id"], "__none__"];
  const noStop = () => ["==", ["get", "route_ids"], "__none__"];

  function routeFilter(selection) {
    if (selection === "all") return null;
    if (!selection || selection === "off") return noRoute();
    return ["==", ["get", "route_id"], String(selection)];
  }

  function stopFilter(selection) {
    if (selection === "all") return null;
    if (!selection || selection === "off") return noStop();
    return ["in", `|${String(selection)}|`, ["get", "route_ids"]];
  }

  function routeOptions(geojson) {
    const unique = new Map();
    for (const feature of (geojson && geojson.features) || []) {
      const props = feature.properties || {};
      const routeId = String(props.route_id || "").trim();
      if (!routeId || unique.has(routeId)) continue;
      const zh = String(props.name_zh || "").trim();
      const en = String(props.name_en || "").trim();
      unique.set(routeId, {
        routeId,
        label: [zh, en].filter(Boolean).join(" · ") || routeId,
      });
    }
    return Array.from(unique.values()).sort((a, b) =>
      a.routeId.localeCompare(b.routeId, undefined, { numeric: true })
    );
  }

  return { routeFilter, stopFilter, routeOptions };
});
