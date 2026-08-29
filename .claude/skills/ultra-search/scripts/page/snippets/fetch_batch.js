// Fetch N URLs through the user's logged-in browser and report each one as it lands.
//
// Two budgets, because the REPL is killed at 120s with no partial output preserved by
// the caller. A per-URL timeout stops one slow navigation from eating the whole window,
// and an overall budget leaves room to print what did succeed -- without them a single
// hanging URL loses the other seven, which is the failure this whole shape exists to
// avoid. Each result is printed the moment it resolves rather than collected at the end,
// so even a hard kill leaves the caller everything that had finished.
//
// Anything that is not text is written to the session directory instead of being
// stringified into the stream: a PDF through JSON.stringify is corrupt and enormous.

const { urls, perUrlTimeoutMs, budgetMs } = ARGS;

function say(obj) {
  console.log(JSON.stringify(obj));
}

function looksBinary(buf, contentType) {
  const ct = (contentType || '').toLowerCase();
  if (ct.includes('html') || ct.includes('xml') || ct.startsWith('text/')) return false;
  if (buf.length >= 4) {
    const sig = buf.subarray(0, 4);
    // %PDF, PK.. (any OOXML/ODF zip), and the legacy OLE2 header used by .doc/.xls/.ppt.
    if (sig[0] === 0x25 && sig[1] === 0x50 && sig[2] === 0x44 && sig[3] === 0x46) return true;
    if (sig[0] === 0x50 && sig[1] === 0x4b) return true;
    if (sig[0] === 0xd0 && sig[1] === 0xcf && sig[2] === 0x11 && sig[3] === 0xe0) return true;
  }
  return !!ct && !ct.includes('json') && !ct.includes('javascript');
}

function extFor(contentType, buf) {
  const ct = (contentType || '').toLowerCase();
  if (ct.includes('pdf')) return 'pdf';
  if (ct.includes('wordprocessingml')) return 'docx';
  if (ct.includes('presentationml')) return 'pptx';
  if (ct.includes('spreadsheetml')) return 'xlsx';
  if (ct.includes('epub')) return 'epub';
  if (ct.includes('csv')) return 'csv';
  if (buf.length >= 4 && buf[0] === 0x25 && buf[1] === 0x50) return 'pdf';
  if (buf.length >= 2 && buf[0] === 0x50 && buf[1] === 0x4b) return 'zip';
  return 'bin';
}

function safeName(u, ext) {
  const cleaned = String(u).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);
  return `${cleaned || 'download'}-${Date.now()}-${Math.floor(Math.random() * 10000)}.${ext}`;
}

// Always the session directory. The sandbox refuses writes outside the project and
// session roots, so an arbitrary destination is not ours to choose -- the caller copies
// the file where it wants it once it has the path.
const dir = pwd;

// The REPL sandbox has no AbortController, so a slow fetch cannot be cancelled -- only
// abandoned. Racing it against a timer gives the caller its budget back on time; the
// request itself keeps going until the sandbox is torn down, which is acceptable because
// nothing downstream is waiting on it.
const TIMED_OUT = Symbol('timeout');

function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(TIMED_OUT), ms))]);
}

async function one(u) {
  const t0 = Date.now();
  try {
    const res = await withTimeout(fetch(u, { redirect: 'follow' }), perUrlTimeoutMs);
    if (res === TIMED_OUT) {
      say({ url: u, status: 0, kind: 'error', ms: Date.now() - t0, error: 'timeout' });
      return;
    }
    const contentType = res.headers.get('content-type') || '';
    const body = await withTimeout(res.arrayBuffer(), Math.max(1000, perUrlTimeoutMs - (Date.now() - t0)));
    if (body === TIMED_OUT) {
      say({ url: u, status: res.status, kind: 'error', ms: Date.now() - t0, error: 'timeout reading body' });
      return;
    }
    const buf = Buffer.from(body);
    const base = {
      url: u,
      final_url: res.url || u,
      status: res.status,
      content_type: contentType,
      ms: Date.now() - t0,
      bytes: buf.length,
    };
    if (looksBinary(buf, contentType)) {
      const ext = extFor(contentType, buf);
      const file = path.join(dir, safeName(u, ext));
      // The sandbox's fs is promise-based and has no *Sync variants.
      await fs.writeFile(file, buf);
      say({ ...base, kind: 'file', saved_path: file, ext });
    } else {
      say({ ...base, kind: 'text', text: buf.toString('utf8') });
    }
  } catch (e) {
    say({ url: u, status: 0, kind: 'error', ms: Date.now() - t0, error: String(e && e.message ? e.message : e) });
  }
}

const batchStart = Date.now();
const work = Promise.allSettled(urls.map(one));
const guard = new Promise((resolve) => setTimeout(() => resolve('budget'), budgetMs));
const outcome = await Promise.race([work, guard]);
// The terminal line is what tells the caller the stream ended on purpose. Without it, a
// batch cut off by the 120s kill and one that simply finished look identical, and the
// caller cannot tell which URLs are missing from which cause.
say({ kind: 'batch_done', requested: urls.length, elapsed_ms: Date.now() - batchStart, hit_budget: outcome === 'budget' });
