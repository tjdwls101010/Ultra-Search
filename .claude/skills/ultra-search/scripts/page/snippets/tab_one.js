// Open one URL in a real browser tab and return the rendered DOM.
//
// This is the escalation path for a page that `fetch` gets nothing useful from -- a
// JavaScript shell, or a bot challenge a real browser can clear. It is one URL per call
// on purpose: a tab is slow and can hang, and batching them would put every URL in the
// batch behind the worst one.
//
// The tab is always closed. A leaked tab is invisible to the caller but real to the
// user's browser, and enough of them will make the browser unusable.

const { url, waitMs, settleMs } = ARGS;

let page = null;
const t0 = Date.now();
try {
  page = await openTab(url);
  const deadline = Date.now() + waitMs;
  let html = '';
  let finalUrl = url;
  // Poll rather than waiting a fixed time: a challenge page rewrites itself once it
  // clears, so the useful DOM is whichever one is there after it stops growing.
  let previous = -1;
  while (Date.now() < deadline) {
    await sleep(settleMs);
    try {
      html = await page.content();
      finalUrl = page.url();
    } catch (e) {
      // A navigation mid-read invalidates the handle; the next poll gets the new document.
      continue;
    }
    if (html.length === previous) break;
    previous = html.length;
  }
  // The rendered text as well as the DOM. An article extractor finds no article in a
  // feed, an inbox or a dashboard -- pages that are legitimately not articles but are
  // exactly what a logged-in fetch is for -- and returning nothing for them would make
  // the whole logged-in path look broken.
  let visibleText = '';
  try {
    visibleText = await page.evaluate(() => document.body ? document.body.innerText : '');
  } catch (e) {
    visibleText = '';
  }
  console.log(JSON.stringify({
    url, final_url: finalUrl, status: 200, kind: 'text', via: 'tab',
    ms: Date.now() - t0, text: html, visible_text: visibleText,
  }));
} catch (e) {
  console.log(JSON.stringify({ url, status: 0, kind: 'error', via: 'tab', ms: Date.now() - t0, error: String(e && e.message ? e.message : e) }));
} finally {
  if (page) {
    try {
      await closeTab(page);
    } catch (e) {
      // Reported, not thrown: the page content is the answer and losing it over a failed
      // cleanup would be the worse outcome. `cleanup_tabs.js` sweeps what is left behind.
      console.log(JSON.stringify({ kind: 'warning', message: 'could not close tab', url }));
    }
  }
}
