// snippet: sitemap
// Collect a site's sitemap URLs, following sitemap-index files one level.
//
// Tried before link-following because a sitemap is the site telling you what it has,
// which is both cheaper and more complete than crawling to discover it. Absent or
// forbidden is an ordinary answer here, not an error: plenty of sites have none.

const { roots, perUrlTimeoutMs, budgetMs } = ARGS;

function say(obj) {
  console.log(JSON.stringify(obj));
}

// The sandbox has no AbortController; a slow fetch is raced against a timer instead.
const TIMED_OUT = Symbol('timeout');

function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(TIMED_OUT), ms))]);
}

async function get(u) {
  try {
    const res = await withTimeout(fetch(u, { redirect: 'follow' }), perUrlTimeoutMs);
    if (res === TIMED_OUT) return { ok: false, status: 0, error: 'timeout' };
    if (!res.ok) return { ok: false, status: res.status };
    const body = await withTimeout(res.text(), perUrlTimeoutMs);
    if (body === TIMED_OUT) return { ok: false, status: res.status, error: 'timeout reading body' };
    return { ok: true, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, error: String(e && e.message ? e.message : e) };
  }
}

function tagValues(xml, tag) {
  const out = [];
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'gi');
  let m;
  while ((m = re.exec(xml)) !== null) out.push(m[1].trim());
  return out;
}

// XML escapes its ampersands, so a query string arrives as ?a=1&amp;b=2. Fetching that
// verbatim requests a URL the site does not have.
function unescapeXml(s) {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
    .replace(/&amp;/g, '&');
}

function locs(xml) {
  return tagValues(xml, 'loc')
    .map((s) => unescapeXml(s.replace(/^<!\[CDATA\[/, '').replace(/\]\]>$/, '').trim()))
    .filter(Boolean);
}

// robots.txt is where a site that does not use the conventional sitemap path says where
// its sitemap actually is. Reading it for <loc> finds nothing, so the directive has to be
// parsed on its own terms.
function robotsSitemaps(body) {
  const out = [];
  for (const line of String(body).split(/\r?\n/)) {
    const m = /^\s*sitemap\s*:\s*(\S+)/i.exec(line);
    if (m) out.push(m[1].trim());
  }
  return out;
}

const start = Date.now();
const seen = new Set();
// Stopping at the budget leaves a partial list, and the closing record says so: without it
// a sitemap cut short reads exactly like a complete one.
let hitBudget = false;
function overBudget() {
  if (Date.now() - start > budgetMs) hitBudget = true;
  return hitBudget;
}

for (const root of roots) {
  if (overBudget()) break;
  const res = await get(root);
  if (!res.ok) {
    say({ kind: 'sitemap_miss', url: root, status: res.status });
    continue;
  }
  if (/^\s*(user-agent|sitemap|disallow|allow)\s*:/im.test(res.body) && !/<loc/i.test(res.body)) {
    for (const child of robotsSitemaps(res.body)) {
      if (overBudget()) break;
      const sub = await get(child);
      if (!sub.ok) continue;
      const nested = /<sitemapindex/i.test(sub.body);
      for (const u of locs(sub.body)) {
        if (nested) {
          const leaf = await get(u);
          if (!leaf.ok) continue;
          for (const v of locs(leaf.body)) {
            if (!seen.has(v)) { seen.add(v); say({ kind: 'url', url: v, source: u }); }
          }
        } else if (!seen.has(u)) {
          seen.add(u);
          say({ kind: 'url', url: u, source: child });
        }
      }
    }
    continue;
  }

  const isIndex = /<sitemapindex/i.test(res.body);
  if (isIndex) {
    for (const child of locs(res.body)) {
      if (overBudget()) break;
      const sub = await get(child);
      if (!sub.ok) continue;
      for (const u of locs(sub.body)) {
        if (!seen.has(u)) {
          seen.add(u);
          say({ kind: 'url', url: u, source: child });
        }
      }
    }
  } else {
    for (const u of locs(res.body)) {
      if (!seen.has(u)) {
        seen.add(u);
        say({ kind: 'url', url: u, source: root });
      }
    }
  }
}

say({ kind: 'sitemap_done', count: seen.size, elapsed_ms: Date.now() - start, hit_budget: hitBudget });
