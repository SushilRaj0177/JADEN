# Register consistency study (pre-registered)

Written on 26 November 2026, before the audit (`jaden.audit`, as of the commit that adds this file)
was run on any of the registers below. The commit that adds this file records what was decided in advance.
Results are reported whatever they are.

## Question

Japan's public registers store each record's address as text and its municipality as a code, maintained
separately. **How often do the two disagree, and why?** Specifically: how many records carry a code that no
longer exists, how many addresses name a different municipality from their code, how many addresses still
use a former municipality name, and, for each kind of disagreement, is the code wrong, the text wrong, or
the reading of the text wrong?

## Registers

| Register | Date | Records | Address | Code | Coordinates |
| :--- | :--- | ---: | :--- | :--- | :--- |
| NTA corporation register (法人番号公表サイト) | 2026-10-30 | 5,049,462 active, domestic | prefecture + municipality + street columns, joined | 5-digit municipality code | no |
| MHLW care offices (介護サービス情報公表システム) | end of June 2026 | 223,161 | address as typed by the office | municipality code column | yes |
| MHLW medical facilities (医療情報ネット) | 2026-06-01 | 206,043 | 所在地 as entered by the facility | prefecture code + 3-digit municipality code | yes |
| MLIT welfare facilities (国土数値情報 P14) | 2023 | 321,859 with an address | address as published, without the municipality | P14_003 | yes |

The files are those already used in this repository (same SHA-256 as in `benchmarks/realdata`,
`benchmarks/heldout` and `benchmarks/heldout2`).

**Disclosure.** All four files have been read before, for other purposes: the first two to develop JADEN, the
last two as held-out tests of municipality resolution. Earlier reports already gave some related counts
(for example 211 corporation rows and 15 care rows whose code is no longer current; 3,281 welfare
facilities with such codes; 6 corporation rows whose address contradicts the code). This study is not blind
to those numbers. JADEN's engine is frozen at the commit of this file for the duration of the study.

## Method

1. **Audit.** Every record goes through `jaden.audit.check_record(address, code)`, which gives one verdict:
   consistent, consistent_former_name, code_retired, conflict, district_not_in_claimed, undetermined,
   unreadable or code_invalid (definitions in `src/jaden/audit.py`).
2. **Location signal.** For registers with coordinates, the published point is placed in MLIT's municipal
   boundaries as of 2026-01-01 (国土数値情報 行政区域 N03-2026, point in polygon). This is computed for every
   record whose verdict is conflict, district_not_in_claimed, code_retired or code_invalid, and for a random
   sample of 2,000 consistent records per register (seed 2026), to measure how often the point agrees with a
   code that the text confirms. The point is the publisher's own geocoding, so it is a third reading, not
   ground truth.
3. **Second reader.** jageocoder 2.2.1.1 (dictionary `gaiku_all_v22.20260417`) reads the address of every
   conflict record whose address writes its municipality.
4. **Inspection.** From each register, a random sample (seed 2027) of up to 100 conflict records and up to
   50 district_not_in_claimed records is inspected one by one, looking at the address, the code's
   municipality, JADEN's reading, jageocoder's reading and the location signal. Each is put in exactly one
   category, defined now:
   - **C, code wrong**: the address, read correctly, names another municipality, and nothing else in the
     record (location, other columns) supports the code.
   - **T, text wrong**: the code is supported (by the location or other columns), and the address names a
     different municipality (a typo, a neighbouring municipality, a building's postal address).
   - **R, reading wrong**: the address, read correctly, agrees with the code; JADEN misread it.
   - **G, gazetteer gap** (district_not_in_claimed only): the district exists in the code's municipality but
     is missing from MLIT's gazetteer.
   - **U, cannot tell.**
   The inspection records (row, category, one-line reason) are published with the results.

## Measures

Per register: the number and share of each verdict, with Wilson 95% intervals, overall and for records whose
address writes its municipality. For the inspected samples: the share of each category with Wilson 95%
intervals. For the location signal: agreement of the point with the code among sampled consistent records,
and, among flagged records, whether the point lies in the code's municipality, the text's, or neither.

## Hypotheses (stated before the run)

- **H1**: In every register, at least 99.5% of the records whose address writes a municipality are
  consistent (verdicts consistent, consistent_former_name or code_retired).
- **H2**: The share of records carrying a retired code is highest in the MLIT welfare file, which predates
  浜松市's 2024 ward reorganisation.
- **H3**: Among inspected conflict records whose address writes its municipality, at most 20% are reading
  errors (category R), in every register with at least 20 such records inspected.
- **H4**: Among sampled consistent records with coordinates, the published point lies in the code's
  municipality at least 97% of the time in every register with coordinates.

Exploratory, no direction stated: among flagged records with coordinates, is the point more often in the
code's municipality or in the text's? How often do addresses still use a former municipality name, per
register?

## Rules

- No change to `src/jaden` during the study; any change found necessary is made afterwards and reported, and
  the reported numbers stay those of the frozen engine.
- Each stage is run once; any rerun is reported with its reason.
- Scripts and results: `benchmarks/registers/`.
