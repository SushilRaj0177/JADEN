# Baselines: other Japanese address tools

These scripts run other open-source Japanese address tools on a JSONL file of `{"id", "input"}`
(JA-AddrBench, or the real-data inputs written by `benchmarks/realdata/compare_tools.py`) and
convert their output to one format: one JSON object per line with `id`, `lg_code` (6-digit
全国地方公共団体コード, or `null` when the tool does not commit to a municipality), `lat` and `lon`.

| Tool | Runner | Notes |
|---|---|---|
| [@geolonia/normalize-japanese-addresses](https://github.com/geolonia/normalize-japanese-addresses) 3.1.3 | `geolonia_run.mjs` then `geolonia_to_jsonl.py` | Fetches its address data from Geolonia's API while running |
| [jageocoder](https://github.com/t-sagara/jageocoder) 2.2.1.1 | `jageocoder_run.py` | Needs a dictionary (`gaiku_all_v22.20260417`, 370 MB) |

```bash
# Geolonia (level 3 = same municipality answers as the default, without house-level fetches)
npm install @geolonia/normalize-japanese-addresses@3.1.3
node geolonia_run.mjs ../jabench.jsonl geolonia_raw.jsonl 8 3      # concurrency 8, level 3
python geolonia_to_jsonl.py geolonia_raw.jsonl geolonia.jsonl

# jageocoder
pip install jageocoder==2.2.1.1
jageocoder install-dictionary gaiku_all_v22.20260417.zip  # https://www.info-proto.com/static/jageocoder/latest/
python jageocoder_run.py ../jabench.jsonl jageocoder.jsonl 4       # 4 processes

# Score everything together
python ../evaluate.py --systems jaden jaden+blocks --blocks-dir ~/.local/share/jaden/blocks \
    --external geolonia=geolonia.jsonl jageocoder=jageocoder.jsonl
```

How the other tools' output is read, so that each is scored on what it actually decided:

- **An answer** is a result that reaches the municipality: Geolonia `level >= 2`; jageocoder a best match
  with a non-empty matched string and a city code. When nothing in the text matches, jageocoder still
  returns a node (`あいうえお` gives 埼玉県川口市 with an empty match); that is not counted as an answer.
- **Names and codes.** Geolonia returns names, which are mapped to the MIC code after folding variant
  characters (茅ヶ崎/茅ケ崎, 檮原/梼原). jageocoder returns codes; a code that is no longer current is
  mapped by its name (its dictionary has 浜松市天竜区 under the pre-2024 code). A name that names no
  current municipality (浜松市中区, abolished in 2024) stays an answer, scored as wrong.
- **Geolonia's level.** The prefecture, municipality and town are decided before Geolonia's
  house-level step, so `level 3` gives identical municipality answers (checked on 1,500 addresses)
  about 7× faster. Its points are then town points; run with level 8 for its house-level points.

Neither tool reports ambiguity, so for them every returned municipality is an answer.
That is exactly what the "wrong answers" and "false-accept" columns measure.
