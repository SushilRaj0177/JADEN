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

## Audit round 4 (separate high-precision audit, 23 Nov 2026)
- [x] R4-H1 A trailing lot written `321-1221` is taken as a postal code and the numbers are lost
- [x] R4-H2 A floor or room with no house number (`芝公園 2階`, `芝公園 101号室`) is read as the 丁目 / 番
- [x] R4-H3 Different rooms share a key: `207-1号室`, `101A号室`, `3F-301`
- [x] R4-H4 A tiny `.xlsx` whose cells share one huge string can use unbounded memory
- [x] R4-H5 English in the NTA style (`Sakae ku Yokohama shi`, `1-1,Chuo, Konosu shi`, `Kita 1-jo Nishi 2-chome` after the numbers) is accepted at a wrong place
- [x] R4-M1 Kyoto towns with the same name in one ward get one key and a midpoint location
- [x] R4-M2 `compare` says 'same' when neither side has a block or house number
- [x] R4-M3 Asahikawa `1条通8丁目右2号` (右 / 左 sides) misparsed
- [x] R4-M4 `4丁目乙222番地30` leaves the branch in the building
- [x] R4-M5 English line read-back: towns only in the Japan Post list, unlisted 丁目, floor B2, names ending in a digit, `Hongo 7-chome`
- [x] R4-M6 Space-separated numbers (`芝公園4 2 8`): canonical not a fixed point
- [x] R4-M7 Kana number marks after a kanji town (`芝公園4ちょうめ2-8`)
- [x] R4-M8 A room or floor after a lot (`488 101号`, `488 1・2階`): canonical not a fixed point
- [x] R4-M9 Deeply nested JSON crashes the server, MCP, stream and batch
- [x] R4-L1 A stray 号 / 号室 / 階 kept as the building
- [x] R4-L2 Towns without a reading drop the whole kana / English line
- [x] R4-L3 Hyphen form of a lot with a digit wing and room is not lossless
- [x] R4-L4 Slow clients can hold every server connection slot
- [x] R4-L5 `/v1/postal` refuses a JSON number; OpenAPI misses its 404
- [x] R4-L6 Large-office (事業所) postal codes are reported as not existing: the warning now says such a code may be a large-office code JADEN does not hold, and the README says so (Japan Post's large-office file could not be downloaded from the build machine; adding it stays open)
- [x] R4-X1 (found while checking) English lines with a building holding digits (`5号棟101 #102`), a Kyoto clause, two towns spelled alike (志水町 / 清水町), a 番地 lot in a town with 丁目, or a note in brackets now read back to the same key (invariant failures on 14,817 real addresses: 142 → 1)
- [x] R4-X2 (found while checking) A registered town glued to a building with no block number (`摩耶埠頭摩耶業務センタービル5階`) is split; an unregistered name with no number reports precision `municipality`, not `town`

## Audit round 5 (separate high-precision audit, 24 Nov 2026)
- [x] R5-H1 English with a room after the numbers (`4-2-8-101 Shibakoen`, `1-10-1-915, Higashishinbashi`) loses the room or wrecks the address
- [x] R5-H2 English accepted in the wrong place: `791, Yoshida, Yoshida-cho, Akitakata-shi, Hiroshima`; comma-less towns ending in Kita / Higashi read as wards
- [x] R5-H3 English numbers before a separate 丁目 / 条 part (`2-22, Minami 14-jo Nishi 1-chome`, `2-18, 4-chome, Shibakoen`) turn the house number into a room
- [x] R5-M1 Short units after the house (`3B`, `10-1`, `B-3`, `B室`) left out of the key
- [x] R5-M2 A branch letter after 番地 (`828番地ロ`, `1062番地乙`, `528番地ハ号`) moved into the building
- [x] R5-M3 Two rooms listed together: canonical reverses them
- [x] R5-M4 A floor written first in English (`5F, 4-2-8 Shibakoen`) gives a stray 号室
- [x] R5-M5 English word orders `Shibakoen 4-chome 2-8`, `4-chome 2-8, Shibakoen`, `oomachi 1-chome 2-ban 15-go`, a building after the numbers, `2-5, 1-chome, Minamihonmachi`
- [x] R5-M6 English without commas loses the town or is rejected
- [x] R5-M7 Non-addresses accepted: `仙台市長`, `金沢市長`, `白浜町中央保健センター`, `東京都港区第5`
- [x] R5-L1 English line of a lot with a kana / kanji branch (`5415-乙`, `860-イ`) does not read back
- [x] R5-L2 A comma inside a building name breaks the English read-back
- [x] R5-L3 English line drops a 字 that repeats the 大字 name
- [x] R5-L4 Kana input with `ごうしつ` leaves `しつ` as the building
- [x] R5-L5 Canonical not a fixed point: `4-2-8-105-0011`, Kyoto clause with numbers and no town
- [x] R5-L6 JSONL output can hold Infinity / NaN; the server accepts NaN
- [x] R5-L7 Blank rows are dropped, so output rows no longer line up with input
- [x] R5-L8 `jaden resolve --help` prints `%%`
- [x] R5-L9 `check_fields` refuses English fields
- [x] R5-X1 (found while checking) The English reader was rewritten: the prefecture and municipality are taken from the end (or the start), and the rest is read as numbers, 丁目, town, building, floor and room in any order. JADEN's own English lines read back on 2,961 of 2,974 real addresses with the commas removed (was 2,644); invariant failures on 29,298 real addresses: 5
- [x] R5-X2 (found while checking) A room written twice (`メゾン花池101号メゾン花池101号室`) is one room

## Audit round 6 (separate high-precision audit, 24 Nov 2026)
- [x] R6-H1 English in Japanese order (`Chiba, Yachiyo-shi, 55-1 Shimada`) read at a wrong municipality (regression)
- [x] R6-H2 A comma with no space after a name (`Shiba Park Bldg,4-2-8 Shibakoen,Minato-ku`) breaks the address (regression)
- [x] R6-H3 A building starting with F or 階 after 号 / 番地 / 番 (`4丁目2番18号 Fビル`) takes the last digit as a floor
- [x] R6-H4 Universities and landmarks (`千葉大学`, `熊本城`, `大阪港`) accepted at a town somewhere in the prefecture
- [x] R6-H5 `3-1-1 Izumi Kita Akita shi Akita` read as 北秋田市
- [x] R6-M1 A short unit after a building name (`メゾン芝 4A`, `コーポ田中 B-3`) left out of the key
- [x] R6-M2 English 番 / 号 without hyphens (`4chome 2ban 8go`, `4 chome 2 ban 8 go`, `5200 banchi`)
- [x] R6-M3 `Aza-X`, `Oaza-X`, `Ooaza-X`, `Ōaza` not stripped
- [x] R6-M4 English lot written after the town (`Aikoku 191-5711, Kushiro-shi`) taken as a postal code
- [x] R6-M5 Sapporo shorthand `Kita 8 Nishi 5`, `南3西4 1-1`
- [x] R6-M6 A Japanese building after the town in English glued onto the town (regression)
- [x] R6-M7 English read-back: repeated 字 with commas, island counties and Japanese buildings without commas, `／2316`
- [x] R6-M8 `check_fields` with mixed Japanese and English fields
- [x] R6-M9 Kyoto same-named town written without its clause: accepted (the ward is certain) with the existing warning, no point given, and `compare` against a version with the clause says possibly_same
- [x] R6-M10 Tax-office style without commas where a 大字 has the municipality's name (`Takanabe cho`)
- [x] R6-M11 Two rooms after a lot (`576番地 201・202号室`)
- [x] R6-M12 `世田谷区役所 第2庁舎` accepted
- [x] R6-L1 Kunrei / Nihon-shiki spellings beyond shi / chi / tsu / fu (`Tyuo`, `Sinzyuku`, `Kisaradu`)
- [x] R6-L2 English with a Japanese town and `X City` / `X shi` rejected
- [x] R6-L3 `1-2-9, Imojima, Gifu` rejected (city named like its prefecture)
- [x] R6-L4 `富山市山岸95 503 号` not a fixed point; municipality text left in the building
- [x] R6-X1 (found while checking) A Japanese building written after a 字 or a Japanese town in English (`54 興戸御垣内 たけのこハウス 2F`) is split off; text after the prefecture (`…, Osaka, A`) is the building; Kunrei suffixes `-si`, `-tyo`, `tyome`
- [x] R6-X2 (found while checking) A building and room typed twice (`アースビルディング 303 アースビルディング 303`) read as one

## Audit round 7 (separate high-precision audit, 24 Nov 2026)
- [x] R7-H1 A unit `F201` / `F-201` after 号 / 番地 / 番 takes the last digit of the number as a floor
- [x] R7-H2 English reader drops a town written in Japanese whose name looks like a building (`日置荘北町`, `二階堂`) (regression)
- [x] R7-M1 A 号 set apart by spaces (`2番 8 号`) read as a room (regression)
- [x] R7-M2 `check_fields` with mixed languages, a ward name shared by several cities and no prefecture: MALFORMED with no issue
- [x] R7-M3 English without commas: a Japanese building after the town glued onto the town
- [x] R7-M4 JADEN's English line leaves out a town with no romanization (`北6条西`)
- [x] R7-M5 Sapporo grid with a building glued after the block (`南七条西７丁目４ラフィリア札幌７０６号`)
- [x] R7-M6 Spaces around every number (`芝公園 4 丁目 2 番 8 号`)
- [x] R7-M7 A postal code of another town in the same municipality now gives a warning naming the town it belongs to
- [x] R7-L1 A room after a Japanese building written after the prefecture stays in the building
- [x] R7-L2 `DAI 6GO 1-1` (第6号1番地の1) read as 6番 (regression)
- [x] R7-L3 A long building text after the prefecture rejects the address
- [x] R7-L4 The compare note now says only that one address gives no street clause JADEN could read (reading romanized Kyoto clauses stays open)
- [x] R7-L5 English town in the wrong ward: the town is kept as written and a note names the municipality that has it ("did you mean 東京都港区芝公園?")
- [x] R7-L6 English with no ward (`5-1 Nihonbashi Kabuto-cho, Tokyo`, `71-Saiwai cho, Tottori, Tottori`) rejected
- [x] R7-L7 `愛知県日進市蟹甲町中島` (字 not written) rejected
- [ ] R7-L8 `加美町町裏八番70-1` not a fixed point (open: a town whose name ends in a kanji 番)
- [x] R7-L9 Two rooms after a building (`トランキーロT 101 102`) split wrongly
- [x] R7-X1 (found while checking) Kunrei `Zyo`, `Higasi`, `Nisi`, `tyome` in Hokkaido grids; a 字 already written is not doubled
