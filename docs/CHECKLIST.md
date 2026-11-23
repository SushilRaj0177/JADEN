# JADEN checklist (from the full audit of 22 November 2026)

Every item comes from the audit of commit `96f81ae`. Each fixed bug is pinned by a test built from its
reproducing input (`tests/test_audit_fixes.py`). `[x]` done, `[ ]` open, `[~]` partly done (see note).

## Bugs

### Hangs and crashes
- [x] B1 `reverse_geocode(90, 0)` never returns (also `/v1/reverse`): unbounded ring loop near the poles
- [x] B27 Crashes instead of errors: `normalize(123)`, NaN, `validate(123)`, `lookup_postal(1050011)`, a JSONL line that is not an object, `--encoding nosuchenc`

### Wrong answers
- [x] B2 A contradicting postal code written with another dash (`100―0001`, `‐`, `–`, `—`) is ignored
- [x] B3 Postal codes without a hyphen or with spaces in front (`1050011 東京都…`, `〒 105 - 0011`) break the address; at the end they become the building
- [x] B4 Numbers after 丁目 joined by `-`, `ー`, `の` (`4丁目-2-8`) are lost
- [x] B5 `NのM番地` (`10の1番地`, `887の2番地`) leaves 番地 as the building and changes the regime
- [x] B6 Town names with 壱 (上尾市壱丁目北) are destroyed by the numeral stage
- [x] B7 Sapporo grid followed by 番 and a lot (`北29条西4丁目2番1-158`) is garbled
- [x] B8 `古町通6番町976` without the prefecture is misread
- [x] B9 resolve() reads a written (ambiguous) municipality name as a town (`大泉町立北小学校` → 練馬区 at 0.93)
- [x] B10 resolve() takes `東京都` as mentioning 京都府
- [x] B11 resolve() can answer while its 95% set is empty
- [x] B12 A raw address and its canonical get different match keys; `find_duplicates` and `compare` disagree
- [x] B13 Lettered and wing rooms (`A-302`, `302-A`, `1号棟302`, `A棟101`) are not rooms, so different flats merge; `三階` is not a floor
- [x] B14 The canonical form of an AMBIGUOUS or MALFORMED input commits to one reading and then validates elsewhere
- [x] B15 Offline geocoding returns SUCCESS for addresses validate rejects
- [x] B16 Extraction takes a phone number's tail as a postal code
- [x] B17 Extraction (and normalize) merges two addresses into one
- [x] B18 Race in the romaji town table can leave a town unconverted
- [x] B19 Romaji input whose town does not match is ACCEPTED with the romaji glued on

### Bad output
- [x] B20 CLI stdin joins several lines into one address
- [x] B21 `format('hyphen')` corrupts unresolved input (`宮城野2-4-1` → `野2-4-1`)
- [x] B22 The hyphen form is not lossless (`732番地の6` → `732-6` → `732番6号`)
- [x] B23 Canonical form unstable for a numeric room (`…16号 1`) and Sapporo kanji (`南十一条西`)
- [x] B24 Invisible and control characters (U+200B, U+00AD, U+2028, NUL) are not removed; `⁃` is not a dash
- [x] B25 A trailing `TEL 03-…` becomes the building
- [x] B26 Batch: duplicate headers lose data, `jaden_*` input columns overwritten, EUC-JP/UTF-16 misread, `--column 0`/out of range, header-less CSV loses a row, JSONL `null` → `"None"`
- [x] B28 Server: HTML errors (501/414/400), no socket timeout, traceback on client disconnect, `/v1/postal/X/extra` → 200, non-string `q` accepted
- [x] B29 CLI: `--limit` not validated, `jaden resolve -`, resolve exit codes undocumented, extract docstring span, README resolve example ranks Sapporo first

Remaining edge cases found by the property check (28 of 45,294 inputs, 0.06%): data that repeats a room number
(`123-2号…2号`, `TiedurC棟105号 105号`), a Sapporo address whose building name holds `11-302`, and rural Hokkaido
`西1線北24号` names. Each still resolves to the right municipality; only its re-reading differs.

### Suspected
- [x] S1 `Gazetteer.match_town` check-then-index could race with a cache clear
- [x] S2 Lazy singletons without locks could load data twice under concurrent first calls

### Slow paths and memory
- [x] P1 `extract_addresses` is ~0.37 ms per character on place-name-dense text; `/v1/extract` accepts 2 MB
- [x] P2 `suggest` averages 32 ms; kana without a municipality 220–465 ms
- [x] P3 Memory reaches ~380 MB with every feature used; README says ~90 MB *(the resolver prior went from ~86 MB to 18 MB; the README now gives the real figures: ~90 MB for normalize, ~350 MB with every feature)*
- [x] P4 `validate` and `resolve` normalize the same input two or three times

## Improvements
- [x] I1 One sanitizer for every path (B2–B5, B24)
- [x] I2 Canonical and hyphen forms are fixed points, checked by a property test on the benchmark and real data
- [~] I3 One comparison core for `match_key` and `compare` *(keys now agree for every spelling in the property test; the two functions still have separate code)*
- [x] I4 Resolver guards (B9–B11)
- [x] I5 Server hardening: Japan bounding box, handler timeout, `/v1/extract` length cap, JSON errors, string-only parameters
- [x] I6 Offline geocode carries the validation status (B15)
- [x] I7 Batch robustness: UTF-16/EUC-JP, mostly-MALFORMED warning, `--no-header`, `--column` validation, JSONL line numbers
- [x] I8 Performance: kana prefix index for suggest, reuse of one NormalizedAddress in validate/resolve, extract without re-normalizing overlaps
- [x] I9 None / NaN / int inputs give an empty result (pandas)
- [x] I10 CLI: multi-line stdin, `--limit`, resolve from stdin

## Features
- [x] F1 `resolve` in the HTTP API (`/v1/resolve`) and as columns in `jaden batch` *(`--resolve`, `--name-column`)*
- [x] F2 Structured input (prefecture, municipality, line 1, line 2, postal code) with cross-checks *(`check_fields`, `/v1/fields`, MCP `check_address_fields`)*
- [x] F3 Machine-readable reason codes, Japanese messages, OpenAPI description *(`reason`, `message_ja`, `/v1/openapi.json`)*
- [x] F4 MCP server: normalize, validate and resolve as tools for AI assistants *(`jaden mcp`, 8 tools)*
- [x] F5 Shipping-label output: fields split to carrier length limits *(`res.label()`, `--label WxL`, `/v1/label`; generic widths, no carrier presets)*
- [x] F6 Explainable fuzzy dedupe: building-name similarity with a reason per pair *(`building_similarity`, `duplicate_pairs`, `jaden dedupe --pairs`; match keys still ignore building names, so 第一ビル and 第二ビル on one lot share a group: the pairs file and `compare` tell them apart)*
- [x] F7 Data I/O: pandas helper, `.xlsx`, NDJSON streaming *(`jaden.frame`, stdlib `.xlsx` for batch and dedupe, `jaden stream`)*
- [x] F8 Full kana / romaji input (`とうきょうとちよだくかすみがせき1-2-1`) *(romaji was already read; kana prefecture and municipality now read from their readings)*
- [ ] F9 `jaden data update` also refreshes the MIC municipality list
- [x] F10 Docker image with a gateway example *(`Dockerfile`, `deploy/docker-compose.yml` + nginx: API key, rate limit, size limit; image and gateway tested)*
