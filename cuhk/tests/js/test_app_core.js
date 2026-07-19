const assert = require("node:assert/strict");
const core = require("../../site/app-core.js");

assert.deepEqual(core.routeFilter("off"), ["==", ["get", "route_id"], "__none__"]);
assert.equal(core.routeFilter("all"), null);
assert.deepEqual(core.routeFilter("2"), ["==", ["get", "route_id"], "2"]);

assert.deepEqual(core.stopFilter("off"), ["==", ["get", "route_ids"], "__none__"]);
assert.equal(core.stopFilter("all"), null);
assert.deepEqual(core.stopFilter("2"), ["in", "|2|", ["get", "route_ids"]]);

const options = core.routeOptions({
  features: [
    { properties: { route_id: "10", name_zh: "十號", name_en: "Ten" } },
    { properties: { route_id: "2", name_zh: "二號", name_en: "Two" } },
    { properties: { route_id: "2", name_zh: "重複", name_en: "Duplicate" } },
  ],
});
assert.deepEqual(options, [
  { routeId: "2", label: "二號 · Two" },
  { routeId: "10", label: "十號 · Ten" },
]);

console.log("app-core tests passed");
