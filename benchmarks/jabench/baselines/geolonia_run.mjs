// Runs @geolonia/normalize-japanese-addresses over JA-AddrBench and writes raw JSONL results.
//   npm install @geolonia/normalize-japanese-addresses@3.1.3
//   node geolonia_run.mjs ../jabench.jsonl geolonia_raw.jsonl
import { normalize } from '@geolonia/normalize-japanese-addresses';
import fs from 'node:fs';
import readline from 'node:readline';

const [, , inPath, outPath, concurrency = '8'] = process.argv;
const items = [];
for await (const line of readline.createInterface({ input: fs.createReadStream(inPath) })) {
  if (line.trim()) items.push(JSON.parse(line));
}
const out = fs.createWriteStream(outPath);
let next = 0;
async function worker() {
  while (next < items.length) {
    const item = items[next++];
    try {
      const r = await normalize(item.input);
      out.write(JSON.stringify({ id: item.id, pref: r.pref ?? null, city: r.city ?? null, town: r.town ?? null,
        level: r.level, point: r.point ?? null }) + '\n');
    } catch (e) {
      out.write(JSON.stringify({ id: item.id, error: String(e) }) + '\n');
    }
  }
}
await Promise.all(Array.from({ length: Number(concurrency) }, worker));
out.end();
