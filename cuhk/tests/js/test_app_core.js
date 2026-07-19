const assert = require("node:assert/strict");
const core = require("../../site/app-core.js");

assert.deepEqual(
  core.publicRouteCatalog().map((route) => route.routeId),
  ["1A", "1B", "2", "3", "4", "8", "5", "6A", "6B", "7", "N", "H"]
);
assert.deepEqual(
  core.routeFilter("N"),
  ["==", ["get", "route_id"], "N"]
);
assert.equal(core.routeColor("2"), "#D79C2F");
assert.deepEqual(core.routeColor("all"), ["get", "color"]);
assert.deepEqual(
  core.stopFilter("H"),
  ["in", "|H|", ["get", "route_ids"]]
);

assert.deepEqual(core.routeFilter("off"), ["==", ["get", "route_id"], "__none__"]);
assert.equal(core.routeFilter("all"), null);
assert.deepEqual(core.routeFilter("2"), ["==", ["get", "route_id"], "2"]);
assert.deepEqual(
  core.routeVariantFilter("2", false),
  ["all", ["==", ["get", "is_conditional"], false], ["==", ["get", "route_id"], "2"]]
);
assert.deepEqual(
  core.routeVariantFilter("all", true),
  ["==", ["get", "is_conditional"], true]
);

assert.deepEqual(core.stopFilter("off"), ["==", ["get", "route_ids"], "__none__"]);
assert.equal(core.stopFilter("all"), null);
assert.deepEqual(core.stopFilter("2"), ["in", "|2|", ["get", "route_ids"]]);

assert.deepEqual(
  core.routeConditions({features: [
    {properties: {route_id: "N", is_conditional: true, condition_zh: "逢00分停一座", condition_en: "Minute 00 via PGH1"}},
    {properties: {route_id: "N", is_conditional: true, condition_zh: "逢00分停一座", condition_en: "Minute 00 via PGH1"}},
    {properties: {route_id: "H", is_conditional: true, condition_zh: "假日条件", condition_en: "Holiday condition"}},
  ]}, "N"),
  [{zh: "逢00分停一座", en: "Minute 00 via PGH1"}]
);

const options = core.routeOptions({
  features: [
    { properties: { route_id: "10", name_zh: "逸夫書院 > 大學站", name_en: "Shaw College > University Station", service_type_id: "3", service_type_zh: "星期日及公眾假期", service_type_en: "Sundays & Public Holidays" } },
    { properties: { route_id: "2", name_zh: "大學站 > 新亞書院", name_en: "University Station > NA College", service_type_id: "1", service_time_id: "1", service_type_zh: "星期一至六", service_type_en: "Monday to Saturday", service_time_zh: "上午9時前", service_time_en: "Before 9:00 a.m." } },
    { properties: { route_id: "2", name_zh: "重複", name_en: "Duplicate" } },
  ],
});
assert.deepEqual(options, core.publicRouteCatalog());
assert.deepEqual(
  core.routeGroups(options).map((group) => ({ label: group.label, routeIds: group.routes.map((route) => route.routeId) })),
  [
    { label: "穿梭校巴 / Campus shuttle", routeIds: ["1A", "1B", "2", "3", "4", "8"] },
    { label: "转堂校巴 / Meet-class", routeIds: ["5", "6A", "6B", "7"] },
    { label: "晚间及假日 / Night & holiday", routeIds: ["N", "H"] },
  ]
);
assert.ok(options.every((route) => route.label.startsWith(route.routeId)));
assert.ok(options.every((route) => !(route.sourceRouteIds || []).length));

assert.deepEqual(
  core.selectNonOverlappingLabels([
    { id: "study", priority: 1, box: [0, 0, 100, 30] },
    { id: "life-overlap", priority: 2, box: [50, 0, 150, 30] },
    { id: "sports", priority: 3, box: [160, 0, 240, 30] },
  ]),
  ["study", "sports"]
);

assert.ok(core.labelPriority({ id: "yia", category: "study" }) < core.labelPriority({ id: "orchid-lodge", category: "life" }));

assert.equal(core.normalizeLabelName(" University-Station (North) "), "universitystationnorth");
assert.equal(core.buildingLabelsEnabled(14.9), false);
assert.equal(core.buildingLabelsEnabled(15), true);
assert.equal(core.labelCollisionPadding(15.5), 5);
assert.equal(core.labelCollisionPadding(16), 1);
assert.ok(core.officialBuildingPriority({ type: "" }) < core.officialBuildingPriority({ type: "student" }));

const buildingFeatures = [
  { properties: { name_zh: "大學圖書館", name_en: "University Library" } },
  { properties: { name_zh: "科學館", name_en: "University Science Centre" } },
  { properties: { name_zh: "科學館", name_en: "University Science Centre" } },
];
const poiFeatures = [
  { properties: { name_zh: "大學圖書館", name_en: "University Library" } },
];
assert.deepEqual(
  core.dedupeBuildingFeatures(buildingFeatures, poiFeatures).map((feature) => feature.properties.name_en),
  ["University Science Centre"]
);

const recording = core.routeRecordingGeoJSON("3", [
  { coordinates: [114.2, 22.4], kind: "stop", stopId: "shaw", nameZh: "逸夫書院" },
  { coordinates: [114.21, 22.41], kind: "waypoint" },
]);
assert.equal(recording.features[0].geometry.type, "LineString");
assert.deepEqual(recording.features[0].geometry.coordinates, [[114.2, 22.4], [114.21, 22.41]]);
assert.equal(recording.features[1].properties.sequence, 1);
assert.equal(recording.features[2].properties.kind, "waypoint");
assert.deepEqual(
  core.routeRecordingGeoJSON("3", [{ coordinates: [114.2, 22.4], kind: "waypoint" }]).features[0].geometry.coordinates,
  []
);

const exported = core.exportRouteRecording("3", recording.features.slice(1).map((feature) => ({
  coordinates: feature.geometry.coordinates,
  ...feature.properties,
})));
assert.equal(exported.route_id, "3");
assert.deepEqual(exported.points.map((point) => point.sequence), [1, 2]);
assert.equal(exported.points[0].stop_id, "shaw");
assert.equal(exported.points[1].kind, "waypoint");

console.log("app-core tests passed");
