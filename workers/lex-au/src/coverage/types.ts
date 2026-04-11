/**
 * Shared types for the /coverage endpoint — the manifest that compares
 * our Vectorize index against the authoritative list of Commonwealth Acts
 * on legislation.gov.au.
 */

/** A single Act as returned by `GET /v1/titles` on api.prod.legislation.gov.au. */
export interface SourceAct {
  title_id: string;
  title: string;
  year: number;
  number: number | null;
  status: string;
}

/** A single row in the coverage report. */
export interface CoverageRecord {
  title_id: string;
  title: string;
  year: number;
  number: number | null;
  status: string;
  /** True if this title_id is present in LEGISLATION_INDEX. */
  in_db: boolean;
  /**
   * ISO-8601 date (YYYY-MM-DD) of the first coverage run that saw this Act
   * in the DB. Not a real ingestion timestamp — the metadata predates any
   * `ingested_at` field. Null when the Act is absent from the DB.
   */
  first_seen: string | null;
  /** Canonical legislation.gov.au URL, stable across compilations. */
  source_url: string;
  /** Worker proxy URL (24h cached) for click-through without extra lookups. */
  proxy_url: string;
}

/** The top-level manifest persisted in KV. */
export interface CoverageManifest {
  /** ISO-8601 timestamp of when this manifest was built. */
  generated_at: string;
  /** Total Acts returned by the source API. */
  source_total: number;
  /** Count of source Acts also present in our DB. */
  indexed_total: number;
  /** Count of source Acts absent from our DB (`source_total - indexed_total`). */
  missing_total: number;
  acts: CoverageRecord[];
  /** Non-fatal notes from the builder (API glitches, truncation, etc.). */
  warnings: string[];
}

/** Persistent map of title_id → first-observed ISO date. */
export type FirstSeenMap = Record<string, string>;

/** KV key constants — kept in one place so tests can import them. */
export const KV_KEYS = {
  manifestLatest: "coverage:manifest:latest",
  firstSeen: "coverage:first_seen",
  manifestDated: (isoDate: string): string => `coverage:manifest:${isoDate}`,
} as const;
