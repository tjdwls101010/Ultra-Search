// snippet: cleanup_tabs
// Close tabs left open by an escalation that timed out before its `finally` ran.
//
// Only tabs whose URL is in the caller's list are touched. The user's own browser is the
// same browser, and closing something they were reading would be a real cost for a
// cosmetic gain.

const { urls } = ARGS;

const wanted = new Set(urls);
let closed = 0;
let inspected = 0;

try {
  const tabs = await listBrowserTabs();
  for (const t of tabs || []) {
    inspected += 1;
    const u = t && (t.url || t.URL);
    if (!u || !wanted.has(u)) continue;
    try {
      const page = await attachBrowserTab(t);
      await closeTab(page);
      closed += 1;
    } catch (e) {
      // Nothing to do about a tab that will not close; reporting the count is enough.
    }
  }
} catch (e) {
  console.log(JSON.stringify({ kind: 'error', error: String(e && e.message ? e.message : e) }));
}

console.log(JSON.stringify({ kind: 'cleanup_done', inspected, closed }));
