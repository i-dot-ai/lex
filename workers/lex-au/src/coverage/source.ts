/**
 * Pagination helper for the legislation.gov.au /v1/titles endpoint.
 *
 * Rate limit: 1 request/second (burst 3) per docs/legislation-gov-au-api.md.
 * We pace at 1.1s between pages with a single retry on 429/5xx. Wall-time
 * pacing via `setTimeout` is fine inside `scheduled()` / `waitUntil()` —
 * CPU budget is only consumed while JS is actually running.
 */

import type { SourceAct } from "./types";

const AU_API_BASE = "https://api.prod.legislation.gov.au/v1";
const PAGE_SIZE = 100;
const PAGE_PACING_MS = 1100;
const USER_AGENT = "lex-au/0.1 (coverage-check)";
const MAX_PAGES = 500; // hard safety stop (~50,000 records)

interface TitlesPage {
  value: Array<{
    id: string;
    name?: string;
    year?: number;
    number?: number | null;
    status?: string;
  }>;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Fetch a single page of /v1/titles with one retry on 429/5xx, honouring
 * `Retry-After` when present. Throws on any other non-2xx response.
 */
async function fetchPage(skip: number): Promise<TitlesPage> {
  const params = new URLSearchParams({
    "$top": String(PAGE_SIZE),
    "$skip": String(skip),
    "$orderby": "id",
    "$filter": "collection eq 'Act' and isPrincipal eq true",
    "$select": "id,name,year,number,status,collection,seriesType,isPrincipal,makingDate",
  });
  const url = `${AU_API_BASE}/titles?${params.toString()}`;

  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(url, {
      headers: {
        "User-Agent": USER_AGENT,
        Accept: "application/json",
      },
    });

    if (response.ok) {
      return (await response.json()) as TitlesPage;
    }

    // Retry 429 and 5xx once.
    const retriable = response.status === 429 || response.status >= 500;
    if (retriable && attempt === 0) {
      const retryAfter = Number(response.headers.get("Retry-After"));
      const backoff = Number.isFinite(retryAfter) && retryAfter > 0
        ? retryAfter * 1000
        : 2000;
      await sleep(backoff);
      continue;
    }

    throw new Error(
      `legislation.gov.au /v1/titles returned ${response.status} at skip=${skip}`,
    );
  }

  // Unreachable — the loop either returns or throws.
  throw new Error("fetchPage: exhausted retries");
}

function toSourceAct(item: TitlesPage["value"][number]): SourceAct | null {
  if (!item.id) return null;
  return {
    title_id: item.id,
    title: item.name ?? "",
    year: typeof item.year === "number" ? item.year : 0,
    number: typeof item.number === "number" ? item.number : null,
    status: item.status ?? "",
  };
}

/**
 * Asynchronously iterate over all Commonwealth Acts from legislation.gov.au.
 * Yields one SourceAct at a time, paginated 100 per request, paced at 1.1s
 * between pages. Stops when a short page (< PAGE_SIZE) is returned or the
 * MAX_PAGES safety stop is reached.
 */
export async function* iterateSourceActs(): AsyncIterable<SourceAct> {
  let skip = 0;
  for (let page = 0; page < MAX_PAGES; page++) {
    if (page > 0) {
      await sleep(PAGE_PACING_MS);
    }
    const payload = await fetchPage(skip);
    const items = payload.value ?? [];
    if (items.length === 0) return;

    for (const item of items) {
      const act = toSourceAct(item);
      if (act) yield act;
    }

    if (items.length < PAGE_SIZE) return;
    skip += items.length;
  }
}
