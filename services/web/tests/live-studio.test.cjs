const assert = require("node:assert/strict");
const { afterEach, mock, test } = require("node:test");
const { runLivePipeline } = require("../lib/liveStudio.ts");
const { uploadRunRich } = require("../lib/studio.ts");

const report = {
  domain: "striated",
  score: 0.2,
  score_kind: "bullet-contrast",
  likelihood_ratio: 10,
  log10_lr: 1,
  direction: "same source",
  verbal: "support for same source",
  lr_bound_log10: 2,
  reference: { name: "test reference", n_km: 10, n_knm: 10, cllr: 0.4, cllr_min: 0.3, auc: 0.9 },
  attribution: [],
  attribution_b: [],
  provenance: { best_land_a: 1, best_land_b: 2 },
  scope_note: "Test fixture only.",
  recipe: { scorer_config_hash: "recorded-comparison-config" },
  previews: { a: [[1, 2], [3, 4]], b: [[2, 4], [6, 8]] },
};

function scans(prefix, count) {
  return Array.from({ length: count }, (_, i) => new File([`${prefix}-${i}`], `${prefix}-${i}.x3p`));
}

afterEach(() => mock.restoreAll());

test("a multi-land walkthrough uses the report's selected lands and recorded recipe", async () => {
  const ingested = [];
  mock.method(globalThis, "fetch", async (input, init) => {
    const url = new URL(input);
    if (url.pathname === "/v1/compare") {
      assert.equal(url.search, "");
      assert.equal(init.body.get("include"), "recipe");
      assert.equal(init.body.getAll("mark_a").length, 3);
      assert.equal(init.body.getAll("mark_b").length, 3);
      return Response.json(report);
    }
    if (url.pathname === "/v1/artifacts") {
      ingested.push(init.body.get("scan").name);
      return Response.json({ handle: "test-surface", kind: "surface" });
    }
    if (url.pathname === "/v1/steps/signature") {
      return Response.json({
        handle: "test-signature",
        preview: {
          raw_preview: [[10, 20], [30, 40]],
          bandpassed_preview: [[1, 3], [5, 7]],
          signature: [1, 2, 3],
          tilt_deg: 0,
        },
      });
    }
    if (url.pathname === "/v1/steps/align") return Response.json({ lag: 0, ccf: 0.9 });
    throw new Error(`Unexpected request: ${url}`);
  });

  const result = await runLivePipeline("striated", scans("a", 3), scans("b", 3));
  assert.equal(result.kind, "run");
  assert.deepEqual(ingested, ["a-1.x3p", "b-2.x3p"]);
  assert.equal(result.run.configHash, "recorded-comparison-config");
  assert.equal(result.run.preprocessIllustrative, false);
  // The raw scan is for ingestion. Attribution stays on the processed report preview.
  assert.deepEqual(result.run.gridA, [[-2.55, -0.85], [0.85, 2.55]]);
  assert.deepEqual(result.run.rawFormA, [[-25.5, -8.5], [8.5, 25.5]]);
});

test("missing multi-land provenance keeps report previews without guessing a land pair", async () => {
  let requests = 0;
  mock.method(globalThis, "fetch", async () => {
    requests += 1;
    return Response.json({ ...report, provenance: {} });
  });
  const result = await runLivePipeline("striated", scans("a", 3), scans("b", 3));
  assert.equal(result.kind, "run");
  assert.equal(requests, 1);
  assert.deepEqual(result.run.gridA, [[-2.55, -0.85], [0.85, 2.55]]);
});

test("an unavailable optional step does not discard a valid comparison", async () => {
  mock.method(globalThis, "fetch", async (input) => new URL(input).pathname === "/v1/compare"
    ? Response.json(report)
    : Response.json({ detail: "step unavailable" }, { status: 503 }));
  const result = await runLivePipeline("striated", scans("a", 1), scans("b", 1));
  assert.equal(result.kind, "run");
  assert.equal(result.run.report.likelihood_ratio, 10);
  assert.equal(result.run.configHash, "recorded-comparison-config");
  assert.equal(result.run.preprocessIllustrative, true);
  assert.match(result.run.stages.find((stage) => stage.id === "preprocess").caption, /illustrative/);
});

test("an upload without a recorded recipe never claims the gallery's configuration", () => {
  const run = uploadRunRich({ ...report, recipe: undefined }, "striated");
  assert.equal(run.configHash, null);
});

test("a refusal returns immediately without ingesting scans", async () => {
  const refusal = { refused: true, domain: "striated", reason: "out of scope" };
  let requests = 0;
  mock.method(globalThis, "fetch", async () => {
    requests += 1;
    return Response.json(refusal);
  });
  assert.deepEqual(await runLivePipeline("striated", scans("a", 1), scans("b", 1)), {
    kind: "refused", refusal,
  });
  assert.equal(requests, 1);
});
