/**
 * Coverage manifest builder.
 *
 * Enumerates all Commonwealth Acts from legislation.gov.au, cross-checks each
 * against LEGISLATION_INDEX via Vectorize getByIds (batches of 100), merges
 * the result with the persistent first_seen map, and writes the resulting
 * manifest to KV.
 */

import type { Env } from "../env";
import { iterateSourceActs } from "./source";
import {
  type CoverageManifest,
  type CoverageRecord,
  type FirstSeenMap,
  type SourceAct,
  KV_KEYS,
} from "./types";

const AU_WEB_BASE = "https://www.legislation.gov.au";
const VECTORIZE_BATCH_SIZE = 100;
/** Dated manifest snapshots live for 90 days. */
const SNAPSHOT_TTL_SECONDS = 90 * 86400;

function chunk<T>(arr: readonly T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    out.push(arr.slice(i, i + size));
  }
  return out;
}

/** Look up which of the given title_ids exist in LEGISLATION_INDEX. */
async function lookupPresentIds(
  index: VectorizeIndex,
  titleIds: readonly string[],
): Promise<Set<string>> {
  const present = new Set<string>();
  for (const batch of chunk(titleIds, VECTORIZE_BATCH_SIZE)) {
    // getByIds is the cheapest Vectorize read — no embedding, no query.
    const vectors = await index.getByIds(batch);
    for (const vec of vectors) {
      if (vec?.id) present.add(vec.id);
    }
  }
  return present;
}

function buildRecord(
  act: SourceAct,
  present: Set<string>,
  firstSeen: FirstSeenMap,
  today: string,
): CoverageRecord {
  const in_db = present.has(act.title_id);
  return {
    title_id: act.title_id,
    title: act.title,
    year: act.year,
    number: act.number,
    status: act.status,
    in_db,
    first_seen: in_db ? (firstSeen[act.title_id] ?? today) : null,
    source_url: `${AU_WEB_BASE}/${act.title_id}`,
    proxy_url: `/proxy/${act.title_id}`,
  };
}

function isoDate(now: Date): string {
  return now.toISOString().slice(0, 10);
}

/**
 * Build and persist a fresh coverage manifest. Returns the manifest so the
 * caller can log counts / warnings. Safe to call from `waitUntil()`.
 */
export async function buildCoverageManifest(
  env: Env,
  now: Date,
): Promise<CoverageManifest> {
  const today = isoDate(now);
  const warnings: string[] = [];

  // Load the previous first_seen map (if any).
  const prev =
    (await env.KV_BINDING.get<FirstSeenMap>(KV_KEYS.firstSeen, "json")) ?? {};

  // 1. Collect all source Acts. Bail out safely on source-side errors so we
  //    don't corrupt first_seen with a partial or empty list.
  const sourceActs: SourceAct[] = [];
  try {
    for await (const act of iterateSourceActs()) {
      sourceActs.push(act);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`Coverage refresh failed while fetching source: ${message}`);
  }

  if (sourceActs.length === 0) {
    warnings.push(
      "Source API returned zero Acts — refusing to overwrite the manifest.",
    );
    // Surface an empty-but-honest manifest without touching KV.
    return {
      generated_at: now.toISOString(),
      source_total: 0,
      indexed_total: 0,
      missing_total: 0,
      acts: [],
      warnings,
    };
  }

  // 2. Batch-lookup each title_id in LEGISLATION_INDEX.
  const titleIds = sourceActs.map((a) => a.title_id);
  const present = await lookupPresentIds(env.LEGISLATION_INDEX, titleIds);

  // 3. Compose the records and the updated first_seen map.
  const acts: CoverageRecord[] = sourceActs.map((a) =>
    buildRecord(a, present, prev, today),
  );

  const merged: FirstSeenMap = { ...prev };
  for (const record of acts) {
    if (record.in_db && !merged[record.title_id]) {
      merged[record.title_id] = record.first_seen ?? today;
    }
  }

  // 4. Safety guard — if the new run found far fewer present Acts than the
  //    previous map recorded, keep the old map as-is so a transient source or
  //    Vectorize outage can't erase history.
  const prevSeenCount = Object.keys(prev).length;
  const nowSeenCount = Object.keys(merged).length;
  const shrankSignificantly =
    prevSeenCount > 0 && nowSeenCount < Math.floor(prevSeenCount * 0.9);

  if (shrankSignificantly) {
    warnings.push(
      `first_seen map shrank from ${prevSeenCount} to ${nowSeenCount} — ` +
        `keeping previous map to preserve history.`,
    );
  } else {
    await env.KV_BINDING.put(KV_KEYS.firstSeen, JSON.stringify(merged));
  }

  const indexed_total = acts.reduce((n, r) => n + (r.in_db ? 1 : 0), 0);
  const manifest: CoverageManifest = {
    generated_at: now.toISOString(),
    source_total: acts.length,
    indexed_total,
    missing_total: acts.length - indexed_total,
    acts,
    warnings,
  };

  // 5. Persist the manifest: latest + dated snapshot.
  const manifestJson = JSON.stringify(manifest);
  await env.KV_BINDING.put(KV_KEYS.manifestLatest, manifestJson);
  await env.KV_BINDING.put(KV_KEYS.manifestDated(today), manifestJson, {
    expirationTtl: SNAPSHOT_TTL_SECONDS,
  });

  return manifest;
}
