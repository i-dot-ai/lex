/**
 * HTML renderer for the /coverage/view endpoint.
 *
 * Server-side paginated table. Each row shows a green tick or red cross,
 * the first-seen date, and links straight back to legislation.gov.au.
 * Includes a small inline-JS refresh panel so triggering a rebuild is a
 * pure in-browser action — the user types the shared token once, the
 * page POSTs /coverage/refresh with the `X-Refresh-Token` header, and
 * auto-reloads after the background job has had time to finish.
 * Pages of 50 rows keep the body well under 100 KB even for the full
 * ~8,000-Act corpus.
 */

import type { CoverageManifest, CoverageRecord } from "./types";

const PAGE_SIZE = 50;
/** Wait this many seconds after a refresh is accepted before auto-reloading. */
const RELOAD_COUNTDOWN_SECONDS = 100;

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

/** Refresh panel HTML. Same markup on both populated and empty-state pages. */
function renderRefreshPanel(): string {
  return `<section class="refresh-panel" aria-labelledby="refresh-heading">
    <button id="refresh-btn" type="button" class="btn-primary">Refresh report</button>
    <form id="refresh-form" class="refresh-form" hidden>
      <h2 id="refresh-heading" class="sr-only">Refresh coverage report</h2>
      <label for="refresh-token" class="refresh-label">
        Refresh token
        <input id="refresh-token" name="refresh-token" type="password"
               autocomplete="current-password" spellcheck="false"
               aria-describedby="refresh-help" required>
      </label>
      <div class="refresh-actions">
        <button id="refresh-submit" type="submit" class="btn-primary">Start refresh</button>
        <button id="refresh-cancel" type="button" class="btn-secondary">Cancel</button>
      </div>
      <p id="refresh-help" class="refresh-help">
        The token is the <code>COVERAGE_REFRESH_TOKEN</code> secret set on
        the worker. Set or rotate it in the Cloudflare dashboard under
        <em>Workers &amp; Pages &rarr; lex-au &rarr; Settings &rarr; Variables and Secrets</em>,
        or via <code>wrangler secret put COVERAGE_REFRESH_TOKEN</code>.
      </p>
    </form>
    <p id="refresh-status" class="refresh-status" role="status" aria-live="polite"></p>
  </section>`;
}

/**
 * Inline refresh script — vanilla DOM, no build step, stored in
 * sessionStorage so the token only has to be typed once per browser tab.
 * Written without template-literal interpolation so it can be embedded
 * inside a backtick-template without escape headaches.
 */
const REFRESH_SCRIPT = [
  "(function(){",
  "  var STORAGE_KEY='lex-au-coverage-token';",
  "  var btn=document.getElementById('refresh-btn');",
  "  var form=document.getElementById('refresh-form');",
  "  var token=document.getElementById('refresh-token');",
  "  var status=document.getElementById('refresh-status');",
  "  var submit=document.getElementById('refresh-submit');",
  "  var cancel=document.getElementById('refresh-cancel');",
  "  if(!btn||!form||!token||!status||!submit||!cancel)return;",
  "  var saved='';",
  "  try{saved=sessionStorage.getItem(STORAGE_KEY)||'';}catch(e){}",
  "  function setStatus(text,cls){status.textContent=text;status.className='refresh-status '+(cls||'');}",
  "  function showForm(){form.hidden=false;btn.hidden=true;token.value=saved;token.disabled=false;submit.disabled=false;setStatus('','');token.focus();}",
  "  function hideForm(){form.hidden=true;btn.hidden=false;}",
  "  btn.addEventListener('click',showForm);",
  "  cancel.addEventListener('click',function(e){e.preventDefault();hideForm();});",
  "  form.addEventListener('submit',function(e){",
  "    e.preventDefault();",
  "    var value=(token.value||'').trim();",
  "    if(!value){setStatus('Enter a refresh token.','status-error');return;}",
  "    submit.disabled=true;",
  "    setStatus('Sending refresh request...','status-pending');",
  "    fetch('/coverage/refresh',{method:'POST',headers:{'X-Refresh-Token':value}})",
  "      .then(function(res){",
  "        if(res.status===202){",
  "          try{sessionStorage.setItem(STORAGE_KEY,value);}catch(e){}",
  "          saved=value;token.disabled=true;",
  "          var remaining=" + RELOAD_COUNTDOWN_SECONDS + ";",
  "          status.className='refresh-status status-ok';",
  "          status.innerHTML='Refresh started. This page will reload in <strong id=\"reload-count\">'+remaining+'</strong> seconds.';",
  "          var count=document.getElementById('reload-count');",
  "          var tick=setInterval(function(){",
  "            remaining--;",
  "            if(count)count.textContent=String(remaining);",
  "            if(remaining<=0){clearInterval(tick);location.reload();}",
  "          },1000);",
  "          return;",
  "        }",
  "        submit.disabled=false;",
  "        if(res.status===401){setStatus('Unauthorized \\u2014 token did not match. Try again.','status-error');token.focus();token.select();return;}",
  "        if(res.status===503){setStatus('Refresh endpoint not configured. Set COVERAGE_REFRESH_TOKEN as a secret in the Cloudflare dashboard.','status-error');return;}",
  "        if(res.status===429){setStatus('Rate limited. Wait a minute and retry.','status-error');return;}",
  "        setStatus('Unexpected response '+res.status+'.','status-error');",
  "      })",
  "      .catch(function(err){",
  "        submit.disabled=false;",
  "        setStatus('Network error: '+((err&&err.message)||String(err)),'status-error');",
  "      });",
  "  });",
  "  if(saved){btn.textContent='Refresh report \\u00b7 token saved';}",
  "})();",
].join("\n");

const STYLES = `
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
.refresh-panel {
  margin: 0 0 1rem 0; padding: .75rem 1rem;
  background: #f2f6fb; border: 1px solid #d6e2f1; border-radius: 6px;
}
.refresh-form { display: block; margin-top: .5rem; }
.refresh-form[hidden] { display: none; }
.refresh-label { display: block; font-size: .9rem; color: #333; }
.refresh-label input {
  display: block; width: 100%; max-width: 22rem; margin-top: .25rem;
  padding: .4rem .5rem; font: inherit;
  border: 1px solid #b4c7e0; border-radius: 4px; background: #fff;
}
.refresh-actions { margin-top: .5rem; display: flex; gap: .5rem; flex-wrap: wrap; }
.refresh-help { font-size: .8rem; color: #555; margin: .5rem 0 0 0; }
.refresh-status { margin: .5rem 0 0 0; font-size: .9rem; min-height: 1em; }
.refresh-status.status-pending { color: #555; }
.refresh-status.status-ok { color: #087c3e; }
.refresh-status.status-error { color: #b3261e; }
.btn-primary, .btn-secondary {
  font: inherit; padding: .4rem .9rem; border-radius: 4px;
  border: 1px solid transparent; cursor: pointer;
}
.btn-primary { background: #1755b8; color: #fff; border-color: #1755b8; }
.btn-primary:hover { background: #13479c; }
.btn-primary:disabled { background: #7ea1d4; border-color: #7ea1d4; cursor: not-allowed; }
.btn-secondary { background: #fff; color: #1755b8; border-color: #b4c7e0; }
.btn-secondary:hover { background: #eaf1fb; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}
.empty-state { padding: 1.5rem 0; color: #555; }
.empty-state h2 { font-size: 1.1rem; margin: 0 0 .5rem 0; }
@media (prefers-color-scheme: dark) {
  body { background: #111; color: #eee; }
  .caption { background: #1b1b1b; border-left-color: #555; color: #bbb; }
  .warnings { background: #2a1d05; border-left-color: #cc6600; color: #ffcb7a; }
  th { background: #1b1b1b; }
  th, td { border-bottom-color: #2a2a2a; }
  .row-missing td { background: #2a1a1a; }
  code { background: #222; }
  a { color: #7eb3ff; }
  .refresh-panel { background: #16202d; border-color: #2a3a52; }
  .refresh-label { color: #ddd; }
  .refresh-label input { background: #0e1620; color: #eee; border-color: #2a3a52; }
  .refresh-help { color: #aaa; }
  .btn-primary { background: #2768c9; border-color: #2768c9; }
  .btn-primary:hover { background: #1f56a8; }
  .btn-secondary { background: #0e1620; color: #8bb4f0; border-color: #2a3a52; }
  .btn-secondary:hover { background: #16202d; }
  .empty-state { color: #bbb; }
}
`.trim();

function renderShell(bodyInner: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>lex-au &middot; Coverage Report</title>
  <style>${STYLES}</style>
</head>
<body>
  <h1>Coverage report &middot; Commonwealth Acts</h1>
${bodyInner}
  <footer>
    Content sourced from the Federal Register of Legislation at
    <a href="https://www.legislation.gov.au" target="_blank" rel="noopener">legislation.gov.au</a>
    under its
    <a href="https://www.legislation.gov.au/terms-of-use" target="_blank" rel="noopener">terms of use</a>.
  </footer>
  <script>${REFRESH_SCRIPT}</script>
</body>
</html>`;
}

/**
 * Render the coverage manifest as a self-contained HTML page for the
 * `/coverage/view` endpoint. Pass `null` to render the empty state with
 * just the refresh panel (used before the first manifest has been built).
 * Clamps `page` into range when the manifest has more than one page.
 */
export function renderCoverageHtml(
  manifest: CoverageManifest | null,
  options: RenderOptions,
): string {
  if (!manifest) {
    return renderShell(
      `  ${renderRefreshPanel()}
  <section class="empty-state">
    <h2>No coverage manifest yet</h2>
    <p>Click <strong>Refresh report</strong> above, enter the refresh token,
    and the background job will pull the full list of Commonwealth Acts
    from legislation.gov.au and compare them against what we have indexed.
    The page will reload automatically when the job should be done.</p>
  </section>`,
    );
  }

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

  const body = `  <p class="summary">
    <strong>${manifest.indexed_total.toLocaleString()}</strong> of
    <strong>${manifest.source_total.toLocaleString()}</strong> Acts indexed
    (<strong>${coveragePct}%</strong>) &middot;
    <strong>${manifest.missing_total.toLocaleString()}</strong> missing &middot;
    generated ${escapeHtml(manifest.generated_at)}
  </p>
  ${renderRefreshPanel()}
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
  ${renderPaginator(page, totalPages, options.baseUrl)}`;

  return renderShell(body);
}

export { PAGE_SIZE as COVERAGE_VIEW_PAGE_SIZE };
