// Runs @geolonia/normalize-japanese-addresses over a JSONL file of {"id", "input"} and writes raw JSONL results.
//   npm install @geolonia/normalize-japanese-addresses@3.1.3
//   node geolonia_run.mjs ../jabench.jsonl geolonia_raw.jsonl [concurrency] [level]
//
// The prefecture, municipality and town are decided before the house-level step, so level 3
// gives the same municipality answers as the default (8) without fetching house-level data
// for every town. Scoring only needs the municipality; pass 8 to get house-level points.
import { normalize, config } from '@geolonia/normalize-japanese-addresses';
import fs from 'node:fs';
import readline from 'node:readline';

const [, , inPath, outPath, concurrency = '8', level = '8'] = process.argv;
config.cacheSize = 50_000;
const items = [];
for await (const line of readline.createInterface({ input: fs.createReadStream(inPath) })) {
  if (line.trim()) items.push(JSON.parse(line));
}
const out = fs.createWriteStream(outPath);
let next = 0;
let done = 0;
const start = Date.now();
async function worker() {
  while (next < items.length) {
    const item = items[next++];
    try {
      const r = await normalize(item.input, { level: Number(level) });
      out.write(JSON.stringify({ id: item.id, pref: r.pref ?? null, city: r.city ?? null, town: r.town ?? null,
        level: r.level, point: r.point ?? null }) + '\n');
    } catch (e) {
      out.write(JSON.stringify({ id: item.id, error: String(e) }) + '\n');
    }
    if (++done % 20000 === 0) {
      console.error(`${done} / ${items.length}, ${Math.round(done / ((Date.now() - start) / 1000))}/s`);
    }
  }
}
await Promise.all(Array.from({ length: Number(concurrency) }, worker));
out.end();
