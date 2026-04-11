/** Cloudflare Worker bindings for lex-au. */

export interface Env {
  /** Vectorize index for legislation-level vectors. */
  LEGISLATION_INDEX: VectorizeIndex;

  /** Vectorize index for section-level vectors. */
  LEGISLATION_SECTION_INDEX: VectorizeIndex;

  /** Workers AI binding for embeddings. */
  AI: Ai;

  /** Rate limiter binding. */
  RATE_LIMITER: RateLimit;

  /**
   * KV namespace backing the /coverage endpoint. Stores the most recent
   * coverage manifest, dated snapshots, and the `first_seen` map.
   */
  KV_BINDING: KVNamespace;

  /**
   * Shared secret required on `X-Refresh-Token` for POST /coverage/refresh.
   * Set via `wrangler secret put COVERAGE_REFRESH_TOKEN`.
   */
  COVERAGE_REFRESH_TOKEN: string;
}
