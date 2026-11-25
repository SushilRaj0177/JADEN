# Held-out test 2: medical facilities (pre-registered)

Written on 25 November 2026, before any address in the test data was read or run through any
system. The commit that adds this file is the record of what was decided in advance. Results are
reported whatever they are, including hypotheses that fail.

## Why a second test

The first held-out test (`benchmarks/heldout/PROTOCOL.md`, MLIT welfare facilities) was run once at
commit `01a23ba0b8`. Since then the rule engine went through ten rounds of fixes found by audits
on the development data (care offices, companies, JA-AddrBench). Two questions remain open:

1. Does the final engine keep its low wrong-answer rate on addresses from a publisher, and a kind of
   facility, it has never seen?
2. Did the ten rounds of fixes generalise, or did they fit the development data?

The first test's addresses were also clean, publisher-formatted text. This test uses addresses
entered by the facilities themselves.

## Data

**Test (frozen):** MHLW 医療情報ネット open data, facility tables as of 2026-06-01, downloaded on
25 November 2026 from
`https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html`:

| File | SHA-256 | Rows |
| :--- | :--- | ---: |
| `01-1_hospital_facility_info_20260601.csv.zip` | `b416472ec52a151455e1c91438e0dec5b471e19eafe70e3e2ee1bb22544efe87` | 7,715 |
| `02-1_clinic_facility_info_20260601.csv.zip` | `602be1310990fc557cfca8cda0e84494304e4df8581c1aca218b68327ebea2cf` | 80,155 |
| `03-1_dental_facility_info_20260601.csv.zip` | `1585ea00b981df8c32d93850b2321a27053b8a9af3d46afc18df11af1f022727` | 54,637 |
| `04_maternity_home_20260601.csv.zip` | `27cc63ed72913f95d8da48cef2287246bbfc6f25f414caa94fc226524d6eb87a` | 2,138 |
| `05_pharmacy_20260601.csv.zip` | `e53eacdbd9b4a11593cfe89f9a8b57a62f62a1e066751d42c73591b6818f9bf4` | 61,398 |

Each row holds the facility's name, its prefecture code and 3-digit municipality code (together
the answer key), its address (`所在地`) and the publisher's coordinates.

**What was looked at before writing this file:** the column headers, the row counts, and counts
over all rows (no address printed): every address starts with its prefecture's name; 205,993 of
206,043 contain the name of their own municipality; 2 pharmacy rows have no municipality code.
Nothing else.

**Development data** (used to build and tune JADEN): the NTA corporate register, the MHLW
care-office register, JA-AddrBench, and the first held-out test's MLIT welfare-facility file. Some
test facilities may appear there too (a clinic run by a registered medical corporation at the same
address, a hospital that also runs a care office). Results are therefore also reported on the
**unseen** subset: rows whose full address, after NFKC normalisation and removal of spaces, matches
no address in any development file (care offices as typed and with their prefecture and
municipality columns; companies as prefecture + city + street; welfare facilities as prefecture +
municipality + address).

## Inputs

From each row with a known municipality code, up to three inputs:

| Input | Text | Built when |
| :--- | :--- | :--- |
| full | the address as published | always |
| no prefecture | the address without the leading prefecture name | always |
| town only | the address without prefecture, county and municipality name (city and ward for a designated-city ward) | the address starts with exactly those names |

Rows whose code is not a current municipality in JADEN's registry, and rows excluded from the town-only
input, are counted and reported. The facility name is the side information for the systems that use one.

## Systems

1. **JADEN rules (final)**: the engine at the commit that adds this file. Answers when `validate`
   returns ACCEPTED.
2. **JADEN rules (before the audits)**: the same scripts with the engine at `01a23ba0b8`, the
   commit at which the first held-out test was run.
3. **JADEN calibrated** and **JADEN calibrated + name**: the resolver model fitted for the first
   test (`benchmarks/calibration/data/model.json`), unchanged, with the thresholds chosen on
   development data for a 1% wrong-answer target and 95% conformal sets.
4. **Geolonia** normalize-japanese-addresses 3.1.3 (level 3) and **jageocoder** 2.2.1.1 (dictionary
   `gaiku_all_v22.20260417`), run and read as in `benchmarks/jabench/baselines/README.md`.

No language model is run in this test.

## Measures

For each system and input, on all rows and on the unseen subset: right, wrong and no-answer counts;
the wrong-answer rate among answers with its Wilson 95% interval. An answer is right when it is the
row's municipality or a ward of the row's designated city. For the calibrated systems also: the
wrong-answer rate at the development threshold, expected calibration error (15 equal-mass bins), and
conformal coverage and mean set size. Descriptive only: the distance between JADEN's offline point
for the full address and the publisher's coordinates (median, share within 1 km), by JADEN's
point level.

## Hypotheses (stated before the run)

- **H1**: On full addresses JADEN rules (final) answer at least 99.5% of inputs, and the upper end of
  the 95% interval of their wrong-answer rate among answers is at most 0.05%.
- **H2**: Without the prefecture, the upper end of that interval is at most 0.1%, and JADEN rules
  (final) give fewer wrong answers than each of Geolonia and jageocoder.
- **H3**: On town-only input, the upper end of that interval is at most 0.5%, and JADEN rules (final)
  give fewer wrong answers than each of Geolonia and jageocoder.
- **H4**: At the development threshold for 1%, JADEN calibrated's wrong-answer rate on town-only input
  has a 95% interval that includes or lies below 1%.
- **H5**: Conformal sets calibrated for 95% reach at least 95% coverage on town-only input. (They fell
  short on the first test, at 93.7%; the size of any shortfall is the result.)
- **H6**: The audits generalised: on full and no-prefecture input, JADEN rules (final) give at most
  as many wrong answers and at least as many right answers as JADEN rules (before the audits), on all
  rows and on the unseen subset.

## Rules

- No test row is used for any code change, threshold or model before the run.
- The scripts in `benchmarks/heldout2/` may be written after this file, but only against the column
  headers above and synthetic rows; any change to them after the first run is reported with its
  reason, and both runs are reported.
- The engine (`src/jaden`) stays as it is at this commit until the results are written.
- Results go to `benchmarks/heldout2/results/`, with the commit they were run at.
