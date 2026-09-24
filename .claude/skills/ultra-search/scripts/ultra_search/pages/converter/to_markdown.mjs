#!/usr/bin/env node
/**
 * HTML in, markdown and metadata out. One document per invocation.
 *
 *   echo '{"html":"…","url":"https://…"}' | node to_markdown.mjs
 *   -> {"ok":true,"markdown":"…","title":"…","author":"…","words":123,…}
 *
 * Reads stdin rather than taking the HTML as an argument because a page is routinely
 * larger than the platform's argv limit.
 *
 * Defuddle's async path falls back to third-party APIs (FxTwitter and friends) when it
 * finds no article, which would send the user's URLs to services they never chose. It is
 * off here: a page that extracts to nothing is reported as nothing, and the caller
 * promotes it to a real browser tab instead.
 */
import { Defuddle } from 'defuddle/node';
import { parseHTML } from 'linkedom';

function read(stream) {
  return new Promise((resolve, reject) => {
    let data = '';
    stream.setEncoding('utf8');
    stream.on('data', (c) => (data += c));
    stream.on('end', () => resolve(data));
    stream.on('error', reject);
  });
}

function countWords(text) {
  const trimmed = (text || '').trim();
  if (!trimmed) return 0;
  // Counting whitespace-delimited tokens undercounts CJK, where a whole paragraph can be
  // one token. Han/Kana/Hangul runs are counted by character so the shell-detection
  // threshold means the same thing in Korean as in English.
  const cjk = (trimmed.match(/[぀-ヿ㐀-䶿一-鿿가-힯]/g) || []).length;
  const latin = trimmed
    .replace(/[぀-ヿ㐀-䶿一-鿿가-힯]/g, ' ')
    .split(/\s+/)
    .filter(Boolean).length;
  return latin + cjk;
}

async function main() {
  let input;
  try {
    input = JSON.parse(await read(process.stdin));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: 'bad_input', message: String(e) }) + '\n');
    process.exit(2);
  }

  const { html, url, format } = input || {};
  if (typeof html !== 'string' || !html) {
    process.stdout.write(JSON.stringify({ ok: false, error: 'bad_input', message: 'html is required' }) + '\n');
    process.exit(2);
  }

  try {
    const { document } = parseHTML(html);
    const wantMarkdown = format !== 'html';
    const result = await Defuddle(document, url || '', { markdown: wantMarkdown, useAsync: false });
    const content = result.content || '';
    process.stdout.write(
      JSON.stringify({
        ok: true,
        markdown: content,
        title: result.title || '',
        author: result.author || '',
        published: result.published || '',
        site: result.site || '',
        domain: result.domain || '',
        description: result.description || '',
        language: result.language || '',
        // Defuddle's own wordCount is computed before markdown conversion and is absent
        // on some pages; recomputing keeps one definition of "how much text is here",
        // which is what the shell threshold is compared against.
        words: countWords(content.replace(/<[^>]+>/g, ' ')),
      }) + '\n',
    );
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ ok: false, error: 'extract_failed', message: String(e && e.message ? e.message : e) }) + '\n',
    );
    process.exit(1);
  }
}

main();
