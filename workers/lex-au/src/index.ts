/**
 * lex-au — Cloudflare Worker MCP server for Australian federal legislation.
 *
 * Routes:
 *   GET  /                           — mobile-optimised landing page
 *   POST /mcp                        — MCP JSON-RPC endpoint
 *   GET  /mcp                        — MCP SSE stream
 *   POST /legislation/search         — search acts
 *   POST /legislation/section/search — search sections
 *   POST /legislation/lookup         — exact lookup
 *   POST /legislation/section/lookup — sections by legislation_id
 *   POST /legislation/text           — full text
 *   GET  /proxy/:id                  — legislation.gov.au proxy
 *   GET  /coverage                   — JSON coverage report (acts in DB vs source)
 *   GET  /coverage/view              — HTML coverage report with click-through links
 *   POST /coverage/refresh           — rebuild coverage manifest (shared secret)
 *   GET  /health                     — health check
 *
 * Source & attribution:
 *   All substantive content served by this worker is derived from the
 *   Federal Register of Legislation at https://www.legislation.gov.au and is
 *   reused under its Terms of Use at https://www.legislation.gov.au/terms-of-use.
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Env } from "./env";
import { legislation } from "./routes/legislation";
import { proxy } from "./routes/proxy";
import { coverage } from "./routes/coverage";
import {
  landing,
  LEGISLATION_SOURCE_URL,
  LEGISLATION_TERMS_URL,
} from "./routes/landing";
import { mcp } from "./mcp/server";
import { rateLimit } from "./middleware/rateLimit";

const app = new Hono<{ Bindings: Env }>();

// CORS for all routes
app.use("*", cors());

// Small default hardening headers for public API responses.
app.use("*", async (c, next) => {
  await next();
  c.res.headers.set("Referrer-Policy", "no-referrer");
  c.res.headers.set("X-Content-Type-Options", "nosniff");
});

// Rate limiting on API routes (not health check or landing page)
app.use("/legislation/*", rateLimit);
app.use("/proxy/*", rateLimit);
app.use("/coverage", rateLimit);
app.use("/coverage/*", rateLimit);
app.use("/mcp", rateLimit);
app.use("/mcp/*", rateLimit);

// Mount routes
app.route("/", landing);
app.route("/legislation", legislation);
app.route("/proxy", proxy);
app.route("/coverage", coverage);
app.route("/mcp", mcp);

// Health check — also advertises source + terms so MCP clients and monitors
// can surface attribution without scraping the landing page.
app.get("/health", (c) =>
  c.json({
    status: "ok",
    service: "lex-au",
    version: "0.1.0",
    source: {
      name: "Federal Register of Legislation",
      url: LEGISLATION_SOURCE_URL,
      terms_of_use: LEGISLATION_TERMS_URL,
    },
  }),
);

// 404 fallback
app.notFound((c) =>
  c.json({ error: "Not found" }, 404),
);

// Global error handler
app.onError((err, c) => {
  console.error("Unhandled error:", err);
  return c.json(
    { error: err.message ?? "Internal server error" },
    500,
  );
});

export default app;
