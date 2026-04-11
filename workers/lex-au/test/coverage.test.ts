/**
 * Tests for the /coverage endpoint, the manifest builder, and the HTML view.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import app from "../src/index";
import type { Env } from "../src/env";
import { buildCoverageManifest } from "../src/coverage/builder";
import {
  type CoverageManifest,
  type FirstSeenMap,
  KV_KEYS,
} from "../src/coverage/types";
import { renderCoverageHtml } from "../src/coverage/view";

// ── KV fake ──────────────────────────────────────────────────────────

/**
 * Minimal in-memory KV stub that implements the methods the coverage code
 * actually uses: `get(key, "json")`, `put(key, value, options?)`.
 */
function createMockKV() {
  const store = new Map<string, string>();
  const kv = {
    store,
    get: vi.fn(async (key: string, type?: string) => {
      const v = store.get(key);
      if (v === undefined) return null;
      return type === "json" ? JSON.parse(v) : v;
    }),
    put: vi.fn(async (key: string, value: string, _opts?: unknown) => {
      store.set(key, value);
    }),
  };
  return kv;
}

type MockKV = ReturnType<typeof createMockKV>;

// ── Vectorize fake ───────────────────────────────────────────────────

/**
 * Vectorize mock whose `getByIds` returns vectors for a configurable subset
 * of ids — letting tests exercise the in_db: true / false branches.
 */
function createMockVectorize(presentIds: Set<string>) {
  return {
    query: vi.fn().mockResolvedValue({ matches: [], count: 0 }),
    getByIds: vi.fn(async (ids: string[]) =>
      ids
        .filter((id) => presentIds.has(id))
        .map((id) => ({ id, values: [] as number[] })),
    ),
  } as unknown as VectorizeIndex;
}

// ── Env fake ─────────────────────────────────────────────────────────

interface MockEnvHandles {
  env: Env;
  kv: MockKV;
  getByIds: ReturnType<typeof vi.fn>;
}

function createCoverageMockEnv(options: {
  presentIds?: Iterable<string>;
  refreshToken?: string;
} = {}): MockEnvHandles {
  const kv = createMockKV();
  const present = new Set(options.presentIds ?? []);
  const legislation = createMockVectorize(present);

  const env = {
    AI: { run: vi.fn() } as unknown as Ai,
    LEGISLATION_INDEX: legislation,
    LEGISLATION_SECTION_INDEX: {
      query: vi.fn().mockResolvedValue({ matches: [], count: 0 }),
    } as unknown as VectorizeIndex,
    RATE_LIMITER: {
      limit: vi.fn().mockResolvedValue({ success: true }),
    } as unknown as RateLimit,
    KV_BINDING: kv as unknown as KVNamespace,
    COVERAGE_REFRESH_TOKEN: options.refreshToken ?? "",
  };

  return {
    env,
    kv,
    getByIds: (legislation as unknown as { getByIds: ReturnType<typeof vi.fn> })
      .getByIds,
  };
}

/**
 * Build a waitUntil-aware execution context for Hono's `app.request`. We
 * collect the promises passed to waitUntil so tests can await them before
 * asserting on side effects.
 */
function createCtx() {
  const pending: Promise<unknown>[] = [];
  const ctx = {
    waitUntil(p: Promise<unknown>) {
      pending.push(p);
    },
    passThroughOnException() {
      /* no-op */
    },
  };
  return {
    ctx: ctx as unknown as ExecutionContext,
    waitForBackground: () => Promise.all(pending),
  };
}

// ── Source-API fetch stub ────────────────────────────────────────────

interface FakeSourceAct {
  id: string;
  name: string;
  year: number;
  number: number | null;
  status: string;
}

/**
 * Install a global `fetch` stub that returns paginated pages of the given
 * acts from api.prod.legislation.gov.au. Respects `$top` / `$skip` so the
 * builder's pagination loop terminates correctly.
 */
function installSourceFetchStub(acts: FakeSourceAct[]) {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string"
      ? new URL(input)
      : input instanceof URL
        ? input
        : new URL((input as Request).url);
    if (!url.host.includes("api.prod.legislation.gov.au")) {
      throw new Error(`Unexpected fetch host: ${url.host}`);
    }
    const top = Number(url.searchParams.get("$top") ?? "100");
    const skip = Number(url.searchParams.get("$skip") ?? "0");
    const slice = acts.slice(skip, skip + top);
    return new Response(JSON.stringify({ value: slice }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchSpy);
  return fetchSpy;
}

// Three fake Acts, enough to span the two in_db branches.
const FAKE_ACTS: FakeSourceAct[] = [
  { id: "C1901A00001", name: "Consolidated Revenue Act 1901", year: 1901, number: 1, status: "Repealed" },
  { id: "C1901A00002", name: "Acts Interpretation Act 1901", year: 1901, number: 2, status: "InForce" },
  { id: "C2022A00007", name: "Example Act 2022", year: 2022, number: 7, status: "InForce" },
];

// ── Tests: builder ────────────────────────────────────────────────────

describe("buildCoverageManifest", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  /** Run the builder to completion while fake timers burn through pacing sleeps. */
  async function runBuilder(env: Env, now: Date): Promise<CoverageManifest> {
    const promise = buildCoverageManifest(env, now);
    // Pump fake timers until the promise settles. Each page in source.ts
    // awaits setTimeout(1100) — runAllTimersAsync flushes them.
    await vi.runAllTimersAsync();
    return promise;
  }

  it("produces a manifest with accurate counts and tick/cross branches", async () => {
    installSourceFetchStub(FAKE_ACTS);
    const { env } = createCoverageMockEnv({
      presentIds: ["C1901A00002", "C2022A00007"], // 2 of 3 present
    });

    const manifest = await runBuilder(env, new Date("2026-04-11T02:00:00Z"));

    expect(manifest.source_total).toBe(3);
    expect(manifest.indexed_total).toBe(2);
    expect(manifest.missing_total).toBe(1);
    expect(manifest.acts).toHaveLength(3);

    const repealedMissing = manifest.acts.find((a) => a.title_id === "C1901A00001")!;
    expect(repealedMissing.in_db).toBe(false);
    expect(repealedMissing.first_seen).toBeNull();
    expect(repealedMissing.source_url).toBe("https://www.legislation.gov.au/C1901A00001");
    expect(repealedMissing.proxy_url).toBe("/proxy/C1901A00001");

    const present = manifest.acts.find((a) => a.title_id === "C1901A00002")!;
    expect(present.in_db).toBe(true);
    expect(present.first_seen).toBe("2026-04-11");
  });

  it("preserves historical first_seen dates across runs", async () => {
    // Seed the KV with an earlier first_seen for one of the Acts.
    installSourceFetchStub(FAKE_ACTS);
    const { env, kv } = createCoverageMockEnv({
      presentIds: ["C1901A00002", "C2022A00007"],
    });
    const earlier: FirstSeenMap = { C1901A00002: "2025-01-01" };
    kv.store.set(KV_KEYS.firstSeen, JSON.stringify(earlier));

    const manifest = await runBuilder(env, new Date("2026-04-11T02:00:00Z"));

    const interp = manifest.acts.find((a) => a.title_id === "C1901A00002")!;
    expect(interp.first_seen).toBe("2025-01-01"); // preserved
    const example = manifest.acts.find((a) => a.title_id === "C2022A00007")!;
    expect(example.first_seen).toBe("2026-04-11"); // newly observed

    // Merged map persisted back.
    const stored = JSON.parse(kv.store.get(KV_KEYS.firstSeen) ?? "{}");
    expect(stored.C1901A00002).toBe("2025-01-01");
    expect(stored.C2022A00007).toBe("2026-04-11");
  });

  it("writes latest + dated snapshot to KV", async () => {
    installSourceFetchStub(FAKE_ACTS);
    const { env, kv } = createCoverageMockEnv({
      presentIds: ["C1901A00002"],
    });

    await runBuilder(env, new Date("2026-04-11T02:00:00Z"));

    expect(kv.store.has(KV_KEYS.manifestLatest)).toBe(true);
    expect(kv.store.has(KV_KEYS.manifestDated("2026-04-11"))).toBe(true);
  });

  it("does not overwrite first_seen when the source returns zero rows", async () => {
    installSourceFetchStub([]);
    const { env, kv } = createCoverageMockEnv();
    const historical: FirstSeenMap = { C1901A00002: "2025-01-01" };
    kv.store.set(KV_KEYS.firstSeen, JSON.stringify(historical));

    const manifest = await runBuilder(env, new Date("2026-04-11T02:00:00Z"));

    expect(manifest.source_total).toBe(0);
    expect(manifest.warnings.length).toBeGreaterThan(0);
    // first_seen preserved exactly as before.
    expect(kv.store.get(KV_KEYS.firstSeen)).toBe(JSON.stringify(historical));
    // No manifest written on empty source.
    expect(kv.store.has(KV_KEYS.manifestLatest)).toBe(false);
  });
});

// ── Tests: routes ─────────────────────────────────────────────────────

describe("GET /coverage (JSON)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns 404 with helpful error when no manifest exists", async () => {
    const { env } = createCoverageMockEnv();
    const { ctx } = createCtx();
    const res = await app.request("/coverage", {}, env, ctx);
    expect(res.status).toBe(404);
    const body = (await res.json()) as { error: string };
    expect(body.error).toContain("/coverage/refresh");
  });

  it("returns the cached manifest when present", async () => {
    const { env, kv } = createCoverageMockEnv();
    const manifest: CoverageManifest = {
      generated_at: "2026-04-11T02:00:00.000Z",
      source_total: 1,
      indexed_total: 1,
      missing_total: 0,
      acts: [
        {
          title_id: "C1901A00002",
          title: "Acts Interpretation Act 1901",
          year: 1901,
          number: 2,
          status: "InForce",
          in_db: true,
          first_seen: "2026-04-11",
          source_url: "https://www.legislation.gov.au/C1901A00002",
          proxy_url: "/proxy/C1901A00002",
        },
      ],
      warnings: [],
    };
    kv.store.set(KV_KEYS.manifestLatest, JSON.stringify(manifest));

    const { ctx } = createCtx();
    const res = await app.request("/coverage", {}, env, ctx);
    expect(res.status).toBe(200);
    const body = (await res.json()) as CoverageManifest;
    expect(body.source_total).toBe(1);
    expect(body.acts[0].title_id).toBe("C1901A00002");
  });

  it("rejects collection=LegislativeInstrument with 400 (v1 stub)", async () => {
    const { env } = createCoverageMockEnv();
    const { ctx } = createCtx();
    const res = await app.request(
      "/coverage?collection=LegislativeInstrument",
      {},
      env,
      ctx,
    );
    expect(res.status).toBe(400);
  });

  it("accepts the explicit collection=Act pass-through", async () => {
    const { env, kv } = createCoverageMockEnv();
    kv.store.set(
      KV_KEYS.manifestLatest,
      JSON.stringify({
        generated_at: "2026-04-11T02:00:00.000Z",
        source_total: 0,
        indexed_total: 0,
        missing_total: 0,
        acts: [],
        warnings: [],
      }),
    );
    const { ctx } = createCtx();
    const res = await app.request("/coverage?collection=Act", {}, env, ctx);
    expect(res.status).toBe(200);
  });
});

describe("GET /coverage/view (HTML)", () => {
  it("renders ticks, crosses, and click-through links", async () => {
    const { env, kv } = createCoverageMockEnv();
    const manifest: CoverageManifest = {
      generated_at: "2026-04-11T02:00:00.000Z",
      source_total: 2,
      indexed_total: 1,
      missing_total: 1,
      acts: [
        {
          title_id: "C1901A00001",
          title: "Consolidated Revenue Act 1901",
          year: 1901,
          number: 1,
          status: "Repealed",
          in_db: false,
          first_seen: null,
          source_url: "https://www.legislation.gov.au/C1901A00001",
          proxy_url: "/proxy/C1901A00001",
        },
        {
          title_id: "C1901A00002",
          title: "Acts Interpretation Act 1901",
          year: 1901,
          number: 2,
          status: "InForce",
          in_db: true,
          first_seen: "2026-04-11",
          source_url: "https://www.legislation.gov.au/C1901A00002",
          proxy_url: "/proxy/C1901A00002",
        },
      ],
      warnings: [],
    };
    kv.store.set(KV_KEYS.manifestLatest, JSON.stringify(manifest));

    const { ctx } = createCtx();
    const res = await app.request("/coverage/view", {}, env, ctx);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type") ?? "").toContain("text/html");
    const body = await res.text();
    // Ticks and crosses are rendered.
    expect(body).toContain("&#10003;"); // green tick
    expect(body).toContain("&#10007;"); // red cross
    // Click-through link to legislation.gov.au for each row.
    expect(body).toContain("https://www.legislation.gov.au/C1901A00002");
    // Header row.
    expect(body).toContain("<th>Title ID</th>");
    // First-seen disclosure is explicit.
    expect(body).toContain("does not retain historical");
  });
});

describe("POST /coverage/refresh", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects missing or wrong token with 401", async () => {
    const { env } = createCoverageMockEnv({ refreshToken: "super-secret" });
    const { ctx } = createCtx();

    const noToken = await app.request(
      "/coverage/refresh",
      { method: "POST" },
      env,
      ctx,
    );
    expect(noToken.status).toBe(401);

    const wrongToken = await app.request(
      "/coverage/refresh",
      { method: "POST", headers: { "X-Refresh-Token": "wrong" } },
      env,
      ctx,
    );
    expect(wrongToken.status).toBe(401);
  });

  it("returns 503 when COVERAGE_REFRESH_TOKEN is not configured", async () => {
    const { env } = createCoverageMockEnv({ refreshToken: "" });
    const { ctx } = createCtx();
    const res = await app.request(
      "/coverage/refresh",
      { method: "POST", headers: { "X-Refresh-Token": "anything" } },
      env,
      ctx,
    );
    expect(res.status).toBe(503);
  });

  it("accepts a valid token and schedules the background refresh", async () => {
    installSourceFetchStub(FAKE_ACTS);
    vi.useFakeTimers();
    try {
      const { env, kv } = createCoverageMockEnv({
        presentIds: ["C1901A00002"],
        refreshToken: "super-secret",
      });
      const { ctx, waitForBackground } = createCtx();

      const res = await app.request(
        "/coverage/refresh",
        { method: "POST", headers: { "X-Refresh-Token": "super-secret" } },
        env,
        ctx,
      );
      expect(res.status).toBe(202);
      const body = (await res.json()) as { status: string };
      expect(body.status).toBe("refresh-started");

      // Drain the background promise (drives the fake timers in source.ts).
      const done = waitForBackground();
      await vi.runAllTimersAsync();
      await done;

      // The manifest and first_seen map should both be written.
      expect(kv.store.has(KV_KEYS.manifestLatest)).toBe(true);
      expect(kv.store.has(KV_KEYS.firstSeen)).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});

// ── Tests: view pagination ────────────────────────────────────────────

describe("renderCoverageHtml pagination", () => {
  function fakeManifest(n: number): CoverageManifest {
    return {
      generated_at: "2026-04-11T02:00:00.000Z",
      source_total: n,
      indexed_total: n,
      missing_total: 0,
      acts: Array.from({ length: n }, (_, i) => ({
        title_id: `C1901A${String(i).padStart(5, "0")}`,
        title: `Act ${i}`,
        year: 1901,
        number: i,
        status: "InForce",
        in_db: true,
        first_seen: "2026-04-11",
        source_url: `https://www.legislation.gov.au/C1901A${String(i).padStart(5, "0")}`,
        proxy_url: `/proxy/C1901A${String(i).padStart(5, "0")}`,
      })),
      warnings: [],
    };
  }

  it("paginates at 50 rows per page and clamps out-of-range pages", () => {
    const manifest = fakeManifest(120);
    const page1 = renderCoverageHtml(manifest, { page: 1, baseUrl: "/coverage/view" });
    const page3 = renderCoverageHtml(manifest, { page: 3, baseUrl: "/coverage/view" });
    const pageHuge = renderCoverageHtml(manifest, { page: 999, baseUrl: "/coverage/view" });

    expect(page1).toContain("Page 1 of 3");
    expect(page3).toContain("Page 3 of 3");
    // Clamped: 999 → 3.
    expect(pageHuge).toContain("Page 3 of 3");
  });
});
