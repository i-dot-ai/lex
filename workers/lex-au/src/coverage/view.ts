/**
 * HTML renderer for the /coverage/view endpoint.
 *
 * Server-side paginated table. Each row shows a green tick or red cross,
 * the first-seen date, and links straight back to legislation.gov.au.
 * Plain HTML + inline CSS, no client JS. Pages of 50 rows keep the body
 * well under 100 KB even for the full ~8,000-Act corpus.
 */

import type { CoverageManifest, CoverageRecord } from "./types";

const PAGE_SIZE = 50;

export interface RenderOptions {
  page: number;
  baseUrl: string;
}

function escapeHtml(s: string | number | null | undefined): string {
  if (s === null || s === undefined) return "";
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderRow(record: CoverageRecord): string {
  const tick = record.in_db
    ? '<span class="ok" aria-label="Present in DB">&#10003;</span>'
    : '<span class="missing" aria-label="Missing from DB">&#10007;</span>';
  const firstSeen = record.first_seen ?? "&mdash;";
  return `<tr class="${record.in_db ? "row-ok" : "row-missing"}">
  <td class="status-cell">${tick}</td>
  <td>${escapeHtml(record.year)}</td>
  <td>${escapeHtml(record.number ?? "")}</td>
  <td><code>${escapeHtml(record.title_id)}</code></td>
  <td><a href="${escapeHtml(record.source_url)}" target="_blank" rel="noopener">${escapeHtml(record.title)}</a></td>
  <td>${escapeHtml(record.status)}</td>
  <td>${firstSeen}</td>
</tr>`;
}

function renderPaginator(
  page: number,
  totalPages: number,
  baseUrl: string,
): string {
  if (totalPages <= 1) return "";
  const prev = page > 1
    ? `<a href="${escapeHtml(baseUrl)}?page=${page - 1}">&larr; Prev</a>`
    : "<span class=\"disabled\">&larr; Prev</span>";
  const next = page < totalPages
    ? `<a href="${escapeHtml(baseUrl)}?page=${page + 1}">Next &rarr;</a>`
    : "<span class=\"disabled\">Next &rarr;</span>";
  return `<nav class="pager">${prev} &nbsp; Page ${page} of ${totalPages} &nbsp; ${next}</nav>`;
}

/**
 * Render the coverage manifest as a self-contained HTML page for the
 * `/coverage/view` endpoint. Clamps `page` into range and handles empty
 * manifests gracefully.
 */
export function renderCoverageHtml(
  manifest: CoverageManifest,
  options: RenderOptions,
): string {
  const totalPages = Math.max(1, Math.ceil(manifest.acts.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, options.page), totalPages);
  const start = (page - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  const rows = manifest.acts.slice(start, end).map(renderRow).join("\n");

  const coveragePct = manifest.source_total > 0
    ? ((manifest.indexed_total / manifest.source_total) * 100).toFixed(1)
    : "0.0";

  const warningsHtml = manifest.warnings.length > 0
    ? `<ul class="warnings">${manifest.warnings
        .map((w) => `<li>${escapeHtml(w)}</li>`)
        .join("")}</ul>`
    : "";

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>lex-au &middot; Coverage Report</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      margin: 0; padding: 1.25rem; max-width: 1100px;
    }
    h1 { font-size: 1.25rem; margin: 0 0 .25rem 0; }
    .summary { margin: 0 0 1rem 0; color: #555; }
    .summary strong { color: inherit; }
    .caption {
      font-size: .85rem; color: #666; margin-bottom: 1rem;
      padding: .5rem .75rem; border-left: 3px solid #ccc; background: #f7f7f7;
    }
    .warnings { color: #994400; background: #fff5e6; padding: .5rem 1rem;
      border-left: 3px solid #cc6600; margin: .5rem 0 1rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { padding: .4rem .6rem; border-bottom: 1px solid #e5e5e5;
      text-align: left; vertical-align: top; }
    th { background: #f2f2f2; font-weight: 600; position: sticky; top: 0; }
    .status-cell { text-align: center; font-size: 1.1rem; width: 2rem; }
    .ok { color: #087c3e; }
    .missing { color: #b3261e; }
    .row-missing td { background: #fff4f4; }
    code { font: 12px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
      background: #eee; padding: 1px 4px; border-radius: 3px; }
    a { color: #1755b8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .pager { margin: 1rem 0; font-size: .95rem; }
    .pager .disabled { color: #aaa; }
    footer { margin-top: 2rem; font-size: .8rem; color: #888; }
    @media (prefers-color-scheme: dark) {
      body { background: #111; color: #eee; }
      .caption { background: #1b1b1b; border-left-color: #555; color: #bbb; }
      .warnings { background: #2a1d05; border-left-color: #cc6600; color: #ffcb7a; }
      th { background: #1b1b1b; }
      th, td { border-bottom-color: #2a2a2a; }
      .row-missing td { background: #2a1a1a; }
      code { background: #222; }
      a { color: #7eb3ff; }
    }
  </style>
</head>
<body>
  <h1>Coverage report &middot; Commonwealth Acts</h1>
  <p class="summary">
    <strong>${manifest.indexed_total.toLocaleString()}</strong> of
    <strong>${manifest.source_total.toLocaleString()}</strong> Acts indexed
    (<strong>${coveragePct}%</strong>) &middot;
    <strong>${manifest.missing_total.toLocaleString()}</strong> missing &middot;
    generated ${escapeHtml(manifest.generated_at)}
  </p>
  <p class="caption">
    Source: <a href="https://www.legislation.gov.au" target="_blank" rel="noopener">legislation.gov.au</a>,
    filter <code>collection eq 'Act' and isPrincipal eq true</code>.
    The <em>First seen</em> column records the first coverage run that saw each
    Act in our database &mdash; the database does not retain historical
    ingestion timestamps, so this value is a forward-looking observation, not
    the original ingest date. Each Act title links directly to its page on
    legislation.gov.au.
  </p>
  ${warningsHtml}
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Year</th>
        <th>No.</th>
        <th>Title ID</th>
        <th>Title</th>
        <th>Status</th>
        <th>First seen</th>
      </tr>
    </thead>
    <tbody>
${rows}
    </tbody>
  </table>
  ${renderPaginator(page, totalPages, options.baseUrl)}
  <footer>
    Content sourced from the Federal Register of Legislation at
    <a href="https://www.legislation.gov.au" target="_blank" rel="noopener">legislation.gov.au</a>
    under its
    <a href="https://www.legislation.gov.au/terms-of-use" target="_blank" rel="noopener">terms of use</a>.
  </footer>
</body>
</html>`;
}

export { PAGE_SIZE as COVERAGE_VIEW_PAGE_SIZE };
