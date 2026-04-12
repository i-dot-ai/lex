/**
 * Coverage report endpoint.
 *
 *   GET  /coverage            — JSON manifest from KV (cached; no source calls)
 *   GET  /coverage/view       — HTML table view with green-tick / red-cross
 *   POST /coverage/refresh    — rebuild the manifest (shared-secret protected)
 *
 * The manifest is built by `buildCoverageManifest` in ../coverage/builder.ts
 * and persisted to the KV_BINDING namespace. The refresh endpoint kicks the
 * builder off inside `executionCtx.waitUntil` so clients get a 202 immediately
 * and the long-running work (paginated source fetches + Vectorize lookups)
 * continues in the background.
 */

import { Hono } from "hono";
import type { Context } from "hono";
import type { Env } from "../env";
import { buildCoverageManifest } from "../coverage/builder";
import type { CoverageManifest } from "../coverage/types";
import { KV_KEYS } from "../coverage/types";
import { renderCoverageHtml } from "../coverage/view";

type CoverageContext = Context<{ Bindings: Env }>;

const coverage = new Hono<{ Bindings: Env }>();

/**
 * Constant-time string comparison for secret token verification.
 * Rejects length mismatches early and XORs the remainder so timing leaks
 * can't reveal how many characters matched.
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Shared pre-flight for /coverage and /coverage/view — enforces the
 * forward-compat `?collection=Act` stub so adding LI/NI later is additive.
 */
function validateCollectionParam(
  c: CoverageContext,
): { ok: true } | { ok: false; response: Response } {
  const collection = c.req.query("collection");
  if (collection && collection !== "Act") {
    return {
      ok: false,
      response: c.json(
        {
          error:
            "Only collection=Act is supported in v1. Leave the parameter unset or pass collection=Act.",
        },
        400,
      ),
    };
  }
  return { ok: true };
}

/** GET /coverage — JSON manifest (latest snapshot from KV). */
coverage.get("/", async (c) => {
  const guard = validateCollectionParam(c);
  if (!guard.ok) return guard.response;

  const manifest = await c.env.KV_BINDING.get<CoverageManifest>(
    KV_KEYS.manifestLatest,
    "json",
  );
  if (!manifest) {
    return c.json(
      {
        error:
          "No coverage manifest yet. Trigger POST /coverage/refresh with X-Refresh-Token to build one.",
      },
      404,
    );
  }
  return c.json(manifest);
});

/** GET /coverage/view — HTML table view with inline refresh button. */
coverage.get("/view", async (c) => {
  const guard = validateCollectionParam(c);
  if (!guard.ok) return guard.response;

  const manifest = await c.env.KV_BINDING.get<CoverageManifest>(
    KV_KEYS.manifestLatest,
    "json",
  );

  const pageParam = Number(c.req.query("page") ?? "1");
  const page = Number.isFinite(pageParam) && pageParam >= 1 ? pageParam : 1;
  const url = new URL(c.req.url);
  const baseUrl = `${url.origin}${url.pathname}`;

  // Always render via the same template so the in-browser Refresh button is
  // available even before the first manifest has been built. A missing
  // manifest renders the empty-state page with just the refresh panel.
  return c.html(renderCoverageHtml(manifest, { page, baseUrl }));
});

/**
 * POST /coverage/refresh — rebuild the manifest in the background.
 *
 * Requires `X-Refresh-Token` matching `env.COVERAGE_REFRESH_TOKEN`.
 * Returns 202 Accepted immediately; the builder continues via
 * `executionCtx.waitUntil`.
 */
coverage.post("/refresh", async (c) => {
  const expected = c.env.COVERAGE_REFRESH_TOKEN;
  if (!expected) {
    return c.json(
      {
        error:
          "Refresh endpoint not configured. Set COVERAGE_REFRESH_TOKEN as a wrangler secret.",
      },
      503,
    );
  }

  const provided = c.req.header("X-Refresh-Token") ?? "";
  if (!timingSafeEqual(provided, expected)) {
    return c.json({ error: "Unauthorized" }, 401);
  }

  const now = new Date();
  c.executionCtx.waitUntil(
    buildCoverageManifest(c.env, now).catch((err) => {
      console.error("Coverage refresh failed:", err);
    }),
  );

  return c.json(
    {
      status: "refresh-started",
      started_at: now.toISOString(),
      note:
        "Background refresh in progress. Poll GET /coverage after ~90s for the updated manifest.",
    },
    202,
  );
});

export { coverage };
