const assert = require("node:assert/strict");
const { afterEach, mock, test } = require("node:test");

process.env.NEXT_PUBLIC_SUPABASE_URL = "https://catalog.example.test";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-publishable-key";
const { getInstruments, getStudies, getScans } = require("../lib/catalog.ts");
const { getBenchmarkData } = require("../lib/benchmark.ts");

afterEach(() => mock.restoreAll());

test("catalog network failures leave filters empty and scans explicitly unavailable", async () => {
  mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  assert.deepEqual(await getInstruments(), []);
  assert.deepEqual(await getStudies(), []);
  assert.deepEqual(await getScans({}), { scans: [], total: 0, error: true });
});

test("an HTTP failure cannot masquerade as an empty benchmark leaderboard", async () => {
  mock.method(globalThis, "fetch", async () => Response.json({ message: "unavailable" }, { status: 503 }));
  assert.deepEqual(await getBenchmarkData(), { splits: [], submissions: [], error: true });
});

test("benchmark network failures preserve the page's unavailable state", async () => {
  mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  assert.equal((await getBenchmarkData()).error, true);
});

test("a successful empty benchmark remains distinguishable from an outage", async () => {
  mock.method(globalThis, "fetch", async () => Response.json([]));
  assert.deepEqual(await getBenchmarkData(), { splits: [], submissions: [], error: false });
});
