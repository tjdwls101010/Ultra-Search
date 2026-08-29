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

function locs(xml) {
  return tagValues(xml, 'loc')
    .map((s) => s.replace(/^<!\[CDATA\[/, '').replace(/\]\]>$/, '').trim())
    .filter(Boolean);
}

const start = Date.now();
const seen = new Set();

for (const root of roots) {
  if (Date.now() - start > budgetMs) break;
  const res = await get(root);
  if (!res.ok) {
    say({ kind: 'sitemap_miss', url: root, status: res.status });
    continue;
  }
  const isIndex = /<sitemapindex/i.test(res.body);
  if (isIndex) {
    for (const child of locs(res.body)) {
      if (Date.now() - start > budgetMs) break;
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

say({ kind: 'sitemap_done', count: seen.size, elapsed_ms: Date.now() - start });
