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
- [x] I3 One comparison core for `match_key` and `compare` *(both are built on `match_parts`; a property test checks that equal keys and a 'same' verdict always go together, on 16,573 spelling pairs; with no exception: a wing marked as such, or glued to the name, is part of the key)*
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
- [x] F6 Explainable fuzzy dedupe: building-name similarity with a reason per pair *(`building_similarity`, `duplicate_pairs`, `jaden dedupe --pairs`; wings marked as such are part of the key; 第一ビル / 第二ビル on one lot keep one key (names are often left out) but are never proposed as a pair)*
- [x] F7 Data I/O: pandas helper, `.xlsx`, NDJSON streaming *(`jaden.frame`, stdlib `.xlsx` for batch and dedupe, `jaden stream`)*
- [x] F8 Full kana / romaji input (`とうきょうとちよだくかすみがせき1-2-1`) *(romaji was already read; kana prefecture and municipality now read from their readings)*
- [x] F9 `jaden data update` also refreshes the MIC municipality list *(finds the current list on MIC's code page, checks it, installs it only when it differs; `jaden data info` shows which list is in use)*
- [x] F10 Docker image with a gateway example *(`Dockerfile`, `deploy/docker-compose.yml` + nginx: API key, rate limit, size limit; image and gateway tested)*

## Final scan (separate audit, 23 Nov 2026)
High
- [x] H1 Kana input picks the longest municipality reading even when the rest is not a town there (`ならしのだい1-2` → 奈良市); 131 of 132 random kana town readings went to the wrong municipality *(a kana municipality is taken only when a registered town follows by reading; kana towns are readings, so several spellings stay ambiguous; random check: 0 wrong in 5,000)*
- [x] H2 `.xlsx` reader glues Excel's furigana (`rPh`) onto cell text *(only a string's own text and rich-text runs are read; `rPh` furigana skipped)*
- [x] H3 `.xlsx` denial of service: huge row/column indices, zip bombs, no size cap before parsing *(streaming parse; parts capped by size and compression ratio; DTDs refused; Excel's row and column limits; at most 5,000,000 cells; empty rows not materialized)*
- [x] H4 `コーポ1-201` / `コーポ1-202` keep the room inside the building name, so dedupe merges different flats *(`<name><wing>-<room>` read as building plus wing-and-room; a wing marked as such (A棟, 2号館, コーポ1-201) is part of the room key; a number that is only part of a name (第二) is not, since names are often left out)*
Medium
- [x] M1 `duplicate_pairs` silently skips rows past 200 on one block *(bucketed by house and room instead of a 200-row cut; a comparison cap, if ever reached, is reported)*
- [x] M2 Kana addresses with 条 / 丁目 / 番町 towns accepted with garbage town text *(town readings include their numbers: 春光台四条, 大門七番町, 北一条西; じょう/ちょうめ/ばんち read as 条/丁目/番地)*
- [x] M3 `building_similarity`: 一号館/二号館, Ⅰ/Ⅱ, A/B, 東/西 called typos; 第1 vs 第一 not equal *(kanji and Roman numerals in digits, wings A/B and 東/西 tell buildings apart; 第1 = 第一)*
- [x] M4 JSONL→CSV drops keys missing from the first row; CSV→JSONL loses duplicate headers and extra values *(JSONL headers are the union of every row's keys, nested values written as JSON; CSV rows become objects with repeated names numbered and extra values kept)*
- [x] M5 Lone surrogates survive cleaning and crash CSV/xlsx output, `jaden stream` and the server (500) *(lone surrogates and more invisible characters removed; every writer tolerates what its encoding cannot hold)*
- [x] M6 `4-2、8` reads 8 as a room: canonical is not a fixed point, keys differ *(a comma between numbers is a hyphen, after 番/丁目 it goes, before a room or floor it is a space)*
- [x] M7 `横浜市立第3中学校` accepted as an address *(…市立 followed by a facility word is a name, not an address)*
- [x] M8 A town from another ward (新宿区芝公園) accepted at municipality level; `xxx-0000` postal codes filled in; 広島市 designated-city code instead of the ward *(rejecting such towns also rejected real addresses missing from the registry, so the address is kept and the municipality where the town is registered is offered in `suggestions`; check_fields reports CITY_MISMATCH; a designated city without a resolvable ward is AMBIGUOUS among its wards; 広島市県広島市 is read as 広島県広島市)*
- [x] M9 `check_fields` rejects kana prefecture/city fields; status and `valid` disagree after a postal mismatch *(kana fields converted by reading; a form error makes the status MALFORMED with its code)*
- [x] M10 Label: postal line not measured, `style='en'` repeats Japanese parts, full-width numbers split *(every line within the width, the postal line included; 'en' splits the English line; numbers such as ４－２－８ never split when a break is possible; overflow as written)*
- [x] M11 `茶山台99-5-1` accepted (registry spells 一丁, so the 丁目 range check is skipped); README chome_99 claim overstated *(a 丁目 is checked against a 丁 family such as 茶山台一丁–三丁; no 丁目 above 90 is accepted unchecked; a large first number in N-N-N is a lot number)*
Low
- [x] Server: `text/plain; a=json` accepted; JSON numbers refused in POST; chunked bodies mis-parsed; unbounded threads *(media type must be application/json; numbers accepted; chunked gets 411; 64 connections at once, then 503)*
- [x] Gateway: 401s not rate-limited; `/health` location reachable with crafted paths; empty key fails open *(refused requests go to a deny upstream, so the rate limit applies; /health proxies to a fixed path; no key gives 503; tested with the nginx image)*
- [x] MCP: booleans and tool names not type-checked; empty batch gets no reply *(every argument checked against its schema type; ids must be strings or integers; an empty batch gets an error)*
- [x] xlsx: missing parts give a traceback instead of an error message *(every malformed file is a ValueError, shown as `Error:` with exit 64)*
- [x] Glued 7-digit postal code before the prefecture; 之 / ノ lot separators; a few invisible characters; `TEL/FAX` and `携帯` numbers; UTF-16 without BOM; integer postal codes losing the leading zero
- [x] `jaden.frame.records()` builds a new engine per call; `normalize_frame` duplicates existing `jaden_*` columns; CLI accepts `--jobs 0`, `--min-score 5` *(engines cached; earlier result columns replaced; names aligned by index; option values checked; --name-column needs --resolve)*
- [x] `extract_addresses` span runs into the next 〒 code

## Audit round 2 (separate high-precision audit, 23 Nov 2026)
High
- [x] H-a A wing written `A-201号室` / `1-201号室` with no building name drops the wing from the key *(a wing and room with no building name is read as such; letter and digit wings in W-RRR stay in the key)*
- [x] H-b `201室` is not read as a room *(`室` and `ごうしつ` are room marks)*
- [x] H-c `.xlsx`: sparse wide rows (one cell at column XFD per row) are fully materialised *(at most 20,000,000 cells counting the padding; refused in under a second)*
Medium
- [x] M-a A room or floor after `丁目` with no block number is read as the block number (canonical not a fixed point) *(after 丁目 or a 条 grid, a number with 号室/室/階/F, or text, is not the block)*
- [x] M-b Rooms written `Apt 703` / `#703` give a canonical that reads back with a different key *(a bare room after a number without 号 is written `NNN号室` in the canonical and hyphen forms; all 34,032 real-life inputs read back)*
- [x] M-c CSV/TSV/xlsx output shifts result columns for rows longer than the header *(the header is widened with columnN names, as for JSONL)*
- [x] M-d An address without a town is ACCEPTED at house precision with no warning; a designated city without a ward gets the city code *(numbers with no town in a municipality that Japan Post divides into towns: precision municipality and a warning; a designated city with numbers but no ward or town: AMBIGUOUS among its wards)*
- [x] M-e 壱/弐/参/拾 building numbers are not read as numbers *(壱/弐/参/拾 read as numbers)*
- [x] M-f `第2-305` splits 第 from its number *(`第2-305`: 第2 stays with the name, 305 is the room)*
- [x] M-g A kana town after a kanji municipality does not read 条 (`旭川市しゅんこうだい4じょう`) *(a kana town after a kanji municipality is read by its full reading, numbers included, before the Sapporo grid; `本郷通6-南1-1` reads as 本郷通六丁目南)*
- [x] M-h JADEN's own English output with a leading room (`#101, 4-2-8 Shibakoen, …`) is misread *(a leading building and room in an English line are read as such; JADEN's English line reads back to the same key)*
- [x] M-i `reverse_geocode` with a huge `max_km` far from Japan runs for minutes *(wide searches scan the points once with great-circle distances: under a second)*
- [x] M-j `duplicate_pairs` pairs every room-less row with every flat of a large building *(copies are linked to one row; a room-less row scores 0.6 / number of flats and is compared only when that can reach the minimum score)*
Low
- [x] `--output-encoding` ignored for stdout; an unknown output encoding gives a traceback
- [x] xlsx DTD check reads only the first 2 KB
- [x] check_fields keeps the wrong municipality's postal code in `fields` after CITY_MISMATCH
- [x] English output drops a town that is not registered
- [x] English labels: postal code printed twice with `postal_line`; words cut mid-word
- [x] `/v1/fields` refuses a JSON number for `postal_code`
- [x] OpenAPI: `/v1/label` lacks `style`; `/v1/postal?code=` undocumented
- [x] `.xlsx` in Strict OOXML or with lower-case cell references reads wrongly without an error
- [x] nginx `map` may match the API key case-insensitively

## Audit round 3 (separate high-precision audit, 23 Nov 2026)
- [x] R3-H1 English input picks one of two towns spelled the same in one municipality, even against the postal code
- [x] R3-M1 JADEN's English line misses: a digit wing and room (`#1`), a leading building with no Latin town, 字 / 地割 / unregistered town text
- [x] R3-M2 A room or wing mark after an open 番地/番 (`305室`, `2号棟305号室`, `1号館`) is read as the next number
- [x] R3-M3 A digit wing and room after an open number: canonical not a fixed point
- [x] R3-M4 A kana town after a kanji municipality with kana number marks (`しばこうえん4ちょうめ2ばん8ごう`) leaves the numbers as the building
- [x] R3-L1 `ごうしつ` kept in the room key
- [x] R3-L2 `4丁目 1-201号室` gets no key while its canonical does
- [x] R3-L3 CSV/TSV fields over 131,072 characters crash
- [x] R3-L4 `.xlsx` DTD check misses a UTF-16 part
- [x] R3-L5 README says 124,526 postal records; the data has 124,527
- [x] R3-L6 An ambiguous designated city with numbers reports precision `house`
- [x] R3-X1 (found while checking) `13番地1-2階` and `1番地19ビル1-1階` put `13番地` inside the town; Sakai's `3丁8番1-1311号` lost its 番
- [x] R3-X2 (found while checking) The English line dropped the 番地 numbers after a 丁目, and the 丁目 before a 甲/乙 lot
- [x] R3-X3 (found while checking) The English line `2-17 Town` read back as a lot; now `2-chome-17 Town`
