// Collect the raw href attributes of a set of pages. Nothing is resolved or filtered here.
//
// The sandbox has no URL constructor, so joining a relative href to its base and deciding
// whether the result is same-origin would mean hand-rolling a URL parser in a place with
// no way to test one. Python has that parser; hrefs are small; so this returns strings and
// lets the caller do it.

const { pages, perUrlTimeoutMs, budgetMs } = ARGS;

function say(obj) {
  console.log(JSON.stringify(obj));
}

const TIMED_OUT = Symbol('timeout');

function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(TIMED_OUT), ms))]);
}

async function hrefsOf(pageUrl) {
  const t0 = Date.now();
  try {
    const res = await withTimeout(fetch(pageUrl, { redirect: 'follow' }), perUrlTimeoutMs);
    if (res === TIMED_OUT) {
      say({ kind: 'link_miss', url: pageUrl, error: 'timeout' });
      return;
    }
    if (!res.ok) {
      say({ kind: 'link_miss', url: pageUrl, status: res.status });
      return;
    }
    const html = await withTimeout(res.text(), Math.max(1000, perUrlTimeoutMs - (Date.now() - t0)));
    if (html === TIMED_OUT) {
      say({ kind: 'link_miss', url: pageUrl, error: 'timeout reading body' });
      return;
    }
    const hrefs = [];
    const seen = new Set();
    const re = /<a\b[^>]*?href\s*=\s*["']([^"']+)["']/gi;
    let m;
    while ((m = re.exec(html)) !== null) {
      const h = m[1];
      if (!h || h.startsWith('#') || seen.has(h)) continue;
      seen.add(h);
      hrefs.push(h);
      if (hrefs.length >= 2000) break;
    }
    say({ kind: 'hrefs', url: pageUrl, final_url: res.url || pageUrl, hrefs });
  } catch (e) {
    say({ kind: 'link_miss', url: pageUrl, error: String(e && e.message ? e.message : e) });
  }
}

const start = Date.now();
const work = Promise.allSettled(pages.map(hrefsOf));
const guard = new Promise((resolve) => setTimeout(() => resolve('budget'), budgetMs));
const outcome = await Promise.race([work, guard]);
say({ kind: 'links_done', pages: pages.length, elapsed_ms: Date.now() - start, hit_budget: outcome === 'budget' });
