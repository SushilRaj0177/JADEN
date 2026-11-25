# Held-out test 2: MHLW medical facilities (2026-06-01)

Run once at commit `c7a22d21c5` under `benchmarks/heldout2/PROTOCOL.md`; "before the audits" is the engine at `01a23ba0b8`. Right and wrong count answers that name the row's municipality or another one; percentages are of all inputs; the interval is the Wilson 95% interval of the wrong-answer rate among answers.

## Inputs

- rows: 206,043
- rows: hospital: 7,715
- unseen: 180,655
- inputs: full: 206,041
- inputs: no prefecture: 206,041
- inputs: town only: 205,830
- no town only input: 211
- rows: clinic: 80,155
- rows: dental: 54,637
- rows: maternity: 2,138
- rows: pharmacy: 61,398
- excluded: municipality code not current or missing: 2

## Hypotheses

- **H1**: holds
- **H2**: holds
- **H3**: holds
- **H4**: holds
- **H5**: does not hold
- **H6**: does not hold

## All rows

| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | ECE | Conformal 95%: coverage / size |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | :--- |
| full | JADEN rules (final) | 206,041 | 99.95% | 0 | 0.000% (0.000–0.002%) | 0.05% | – | – |
|  | JADEN rules (before the audits) | 206,041 | 99.95% | 0 | 0.000% (0.000–0.002%) | 0.05% | – | – |
|  | JADEN calibrated | 206,041 | 99.94% | 0 | 0.000% (0.000–0.002%) | 0.06% | 0.0017 | 99.85% / 1.00 |
|  | JADEN calibrated + name | 206,041 | 99.95% | 0 | 0.000% (0.000–0.002%) | 0.05% | 0.0013 | 99.85% / 1.00 |
|  | geolonia | 206,041 | 99.99% | 0 | 0.000% (0.000–0.002%) | 0.01% | – | – |
|  | jageocoder | 206,041 | 99.97% | 0 | 0.000% (0.000–0.002%) | 0.03% | – | – |
| no prefecture | JADEN rules (final) | 206,041 | 99.87% | 0 | 0.000% (0.000–0.002%) | 0.13% | – | – |
|  | JADEN rules (before the audits) | 206,041 | 99.88% | 0 | 0.000% (0.000–0.002%) | 0.12% | – | – |
|  | JADEN calibrated | 206,041 | 99.87% | 0 | 0.000% (0.000–0.002%) | 0.13% | 0.0031 | 99.93% / 1.00 |
|  | JADEN calibrated + name | 206,041 | 99.87% | 0 | 0.000% (0.000–0.002%) | 0.13% | 0.0026 | 99.93% / 1.00 |
|  | geolonia | 206,041 | 99.97% | 50 | 0.024% (0.018–0.032%) | 0.01% | – | – |
|  | jageocoder | 206,041 | 99.97% | 2 | 0.001% (0.000–0.004%) | 0.03% | – | – |
| town only | JADEN rules (final) | 205,830 | 48.80% | 279 | 0.277% (0.246–0.311%) | 51.07% | – | – |
|  | JADEN rules (before the audits) | 205,830 | 48.85% | 774 | 0.764% (0.712–0.819%) | 50.78% | – | – |
|  | JADEN calibrated | 205,830 | 58.59% | 880 | 0.724% (0.678–0.774%) | 40.99% | 0.0062 | 93.77% / 2.33 |
|  | JADEN calibrated + name | 205,830 | 59.80% | 1,075 | 0.866% (0.816–0.919%) | 39.68% | 0.0049 | 93.72% / 2.12 |
|  | geolonia | 205,830 | 0.06% | 4,385 | 97.466% (96.965–97.886%) | 97.81% | – | – |
|  | jageocoder | 205,830 | 75.80% | 45,343 | 22.518% (22.336–22.701%) | 2.17% | – | – |

## Unseen rows

| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | ECE | Conformal 95%: coverage / size |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | :--- |
| full | JADEN rules (final) | 180,655 | 99.94% | 0 | 0.000% (0.000–0.002%) | 0.06% | – | – |
|  | JADEN rules (before the audits) | 180,655 | 99.95% | 0 | 0.000% (0.000–0.002%) | 0.05% | – | – |
|  | JADEN calibrated | 180,655 | 99.94% | 0 | 0.000% (0.000–0.002%) | 0.06% | 0.0016 | 99.84% / 1.00 |
|  | JADEN calibrated + name | 180,655 | 99.94% | 0 | 0.000% (0.000–0.002%) | 0.06% | 0.0013 | 99.83% / 1.00 |
|  | geolonia | 180,655 | 99.99% | 0 | 0.000% (0.000–0.002%) | 0.01% | – | – |
|  | jageocoder | 180,655 | 99.97% | 0 | 0.000% (0.000–0.002%) | 0.03% | – | – |
| no prefecture | JADEN rules (final) | 180,655 | 99.86% | 0 | 0.000% (0.000–0.002%) | 0.14% | – | – |
|  | JADEN rules (before the audits) | 180,655 | 99.87% | 0 | 0.000% (0.000–0.002%) | 0.13% | – | – |
|  | JADEN calibrated | 180,655 | 99.86% | 0 | 0.000% (0.000–0.002%) | 0.14% | 0.0032 | 99.92% / 1.00 |
|  | JADEN calibrated + name | 180,655 | 99.86% | 0 | 0.000% (0.000–0.002%) | 0.14% | 0.0027 | 99.92% / 1.00 |
|  | geolonia | 180,655 | 99.97% | 46 | 0.025% (0.019–0.034%) | 0.01% | – | – |
|  | jageocoder | 180,655 | 99.97% | 2 | 0.001% (0.000–0.004%) | 0.03% | – | – |
| town only | JADEN rules (final) | 180,450 | 48.58% | 260 | 0.296% (0.262–0.334%) | 51.27% | – | – |
|  | JADEN rules (before the audits) | 180,450 | 48.63% | 741 | 0.837% (0.779–0.900%) | 50.96% | – | – |
|  | JADEN calibrated | 180,450 | 58.82% | 767 | 0.717% (0.669–0.770%) | 40.75% | 0.0063 | 94.14% / 2.29 |
|  | JADEN calibrated + name | 180,450 | 60.06% | 948 | 0.867% (0.814–0.924%) | 39.41% | 0.0069 | 94.08% / 2.09 |
|  | geolonia | 180,450 | 0.06% | 3,712 | 97.097% (96.515–97.583%) | 97.88% | – | – |
|  | jageocoder | 180,450 | 76.00% | 39,422 | 22.328% (22.134–22.523%) | 2.16% | – | – |

## Before and after the audits (all rows)

Inputs whose outcome under JADEN's rules changed between the two engines.

- full: before no answer → final right: 11, before right → final no answer: 28
- no prefecture: before no answer → final right: 11, before right → final no answer: 28
- town only: before no answer → final right: 21, before right → final no answer: 138, before wrong → final no answer: 484, before wrong → final right: 11

## JADEN rules (final): wrong answers (first 15 per input)

**full**


**no prefecture**


**town only**

- `栄町` → 123293 (row: 10206)
- `苗木字３７２５ー２` → 102075 (row: 21206)
- `栄町南舘３－８７９` → 123293 (row: 23229)
- `西宮市５ー５ー４２` → 282049 (row: 40213)
- `和多田２４３０` → 182044 (row: 41202)
- `荘園町３０番１０号` → 272167 (row: 44202)
- `荘園町６６番２７号` → 272167 (row: 44202)
- `荘園町７３番８号` → 272167 (row: 44202)
- `荘園町６６番４４号` → 272167 (row: 44202)
- `字旧館１－１７` → 043613 (row: 04445)
- `旧舘１番８０－２` → 043613 (row: 04445)
- `花山字本沢北ノ前７８－２` → 262099 (row: 04213)
- `角田字町２４３` → 271276 (row: 04208)
- `長野新山７０－１` → 202185 (row: 05212)
- `美咲町` → 336661 (row: 06207)

## JADEN's offline point against the publisher's coordinates (full addresses, descriptive)

The publisher's coordinates are its own geocoding, so this is agreement between two systems.

| JADEN point level | Addresses | Median distance | Within 1 km |
| :--- | ---: | ---: | ---: |
| chome | 102,869 | 165 m | 99.57% |
| town | 85,783 | 380 m | 82.43% |
