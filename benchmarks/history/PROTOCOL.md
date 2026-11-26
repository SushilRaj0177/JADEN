# Pre-merger address study (pre-registered)

Written on 26 November 2026, before any system was run on the addresses below. The commit that adds this
file records what was decided in advance. Results are reported whatever they are.

## Question

Records, archives and old registers keep addresses written with municipalities that no longer exist
(merged, renamed, turned into wards, reorganised). **When an address is written as it was at an earlier
date, can a tool still name the municipality it is in today, and can it say which earlier municipality a
current address belonged to?**

## Data (real addresses as published at the time, with an independent answer key)

| Source | Date | Facilities with an address | Address as published | Answer key |
| :--- | :--- | ---: | :--- | :--- |
| MLIT 国土数値情報 public facilities P02 (`P02-06`) | 2006 (平成18年) | 197,031 | 所在地 without the municipality, plus the facility's municipality code of the time | the facility's point in MLIT's municipal boundaries of 2026-01-01 (N03-2026) |
| MLIT 国土数値情報 welfare facilities P14 (`P14-11`) | 2011 (平成23年) | 90,762 | prefecture name, municipality name of the time, 所在地 without the municipality | the facility's point in N03-2026 |

Both sets of files are frozen by the SHA-256 of every file in `data_sha256.txt` (47 + 47 files, downloaded
on 26 November 2026 from `https://nlftp.mlit.go.jp/ksj/gml/data/P02/P02-06/` and `.../P14/P14-11/`).

The answer key is the municipality (designated-city ward included) whose 2026 boundary contains the
facility's surveyed point, so it does not depend on any tool's reading of the text, nor on JADEN's
former-name table.

**What was looked at before writing this file:** for P02, the field list, field types and lengths, the first
three rows of the Tokyo 1990 file (which has no address field and is therefore not used), row counts, and
counts by whether the 2006 code is current (188,519) or retired (8,512, 127 codes); for P14-11, the field
list and counts of facilities by whether the published municipality name is a current name in its
prefecture without normalisation (77,169 / 13,593; the latter count includes names written with their
county or with variant characters, which the definition below excludes). No address was read and no system
was run. The 2011 welfare file is an earlier edition of the file used as held-out test 1; its addresses are
from a different date. JADEN's former-name table was built from municipal boundaries and MIC code lists,
not from addresses; its handling of former names was developed on JA-AddrBench (schools).

## Inputs

- **P02-06**: prefecture name + the municipality's name in 2006 + 所在地. The 2006 name comes from the
  2006 code: the current registry when the code is current, else MIC's record of the retired code (a ward
  of a designated city gets its city's name in front).
- **P14-11**: P14_001 + P14_002 + P14_003, as published.

Facilities without a usable point (missing, or outside every 2026 boundary) are excluded and counted.

## Sets

- **changed**: the municipality as written then no longer exists. P02: the 2006 code is retired. P14-11:
  the published municipality name, after removing a leading county (〇〇郡) and folding variant characters
  (ヶ/ケ, 﨑/崎 and the like), is not the name of a current municipality (or designated-city ward) of its
  prefecture.
- **unchanged**: all others (controls).

## Systems

1. JADEN rules (`validate`; an answer is an ACCEPTED result's municipality), at the commit that adds this
   file.
2. jageocoder 2.2.1.1 (dictionary `gaiku_all_v22.20260417`) and Geolonia normalize-japanese-addresses 3.1.3
   (level 3), read as in `benchmarks/jabench/baselines/README.md`, on every changed input and on a random
   sample of 5,000 unchanged inputs per source (seed 2026).
3. **Reverse lookup** (`jaden.history.former_municipality`): for P02 facilities whose 2006 code is retired
   and was also the municipality's code on 2000-10-01, the 2000 municipality JADEN reports for the address is
   compared with that code.

## Measures

Right (names the answer key's municipality, or a ward of the key's designated city / the city of the key's
ward), wrong, no answer; the wrong-answer rate among answers with its Wilson 95% interval; per source and set,
and for the changed sets also by kind of change (merger, status change or rename, designated-city ward
creation or reorganisation, split across several current municipalities). For the reverse lookup:
agreement with the 2006 code.

## Hypotheses (stated before the run)

- **H1**: On P02-06 changed inputs, JADEN is right on at least 95% and wrong on at most 1% of its answers.
- **H2**: On P14-11 changed inputs, JADEN is right on at least 95% and wrong on at most 1% of its answers.
- **H3**: On each changed set, JADEN's wrong-answer rate among answers is below each other tool's, and its
  right share is at least each other tool's.
- **H4**: On each unchanged set, JADEN is right on at least 99% and wrong on at most 0.1% of its answers.
- **H5**: The reverse lookup agrees with the 2006 code for at least 97% of eligible facilities.

## Rules

- No change to `src/jaden` until the results are written; any change found necessary afterwards is reported
  separately and does not replace these results.
- Each system is run once; any rerun is reported with its reason.
- Scripts and results: `benchmarks/history/`.
