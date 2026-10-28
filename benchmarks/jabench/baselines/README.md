# Baselines for JA-AddrBench

These scripts run other open-source Japanese address tools on the benchmark and
convert their output to the evaluator's format: one JSON object per line with
`id`, `lg_code` (6-digit 全国地方公共団体コード, or `null` when the tool does not
commit to a municipality), `lat` and `lon`.

| Tool | Runner | Notes |
|---|---|---|
| [@geolonia/normalize-japanese-addresses](https://github.com/geolonia/normalize-japanese-addresses) 3.1.3 | `geolonia_run.mjs` then `geolonia_to_jsonl.py` | Fetches its address data from Geolonia's API while running |
| [jageocoder](https://github.com/t-sagara/jageocoder) 2.2 | `jageocoder_run.py` | Needs a dictionary (`gaiku_all_v22`, ~370 MB) |

```bash
# Geolonia
npm install @geolonia/normalize-japanese-addresses@3.1.3
node geolonia_run.mjs ../jabench.jsonl geolonia_raw.jsonl
python geolonia_to_jsonl.py geolonia_raw.jsonl geolonia.jsonl

# jageocoder
pip install jageocoder
jageocoder install-dictionary <downloaded gaiku_all_v22 zip>
python jageocoder_run.py ../jabench.jsonl jageocoder.jsonl

# Score everything together
python ../evaluate.py --external geolonia=geolonia.jsonl jageocoder=jageocoder.jsonl
```

Neither tool reports ambiguity, so for them every returned municipality is an answer.
That is exactly what the "wrong answers" and "false-accept" columns measure.
