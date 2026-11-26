# Pre-merger address study

Run under `benchmarks/history/PROTOCOL.md`; JADEN at `af8e1546ae`. Right / wrong: answers naming the municipality that contains the facility's point in the 2026-01-01 boundaries, or another one. The other tools ran on every changed input and 5,000 unchanged inputs per source.

## Inputs

- P02-06 rows: 197,088
- P02-06 unchanged: 188,502
- P02-06 changed: 8,511
- P02-06 excluded: no usable point: 18
- P14-11 rows: 90,762
- P14-11 unchanged: 89,395
- P14-11 changed: 1,367

## Hypotheses

- **H1**: does not hold
- **H2**: holds
- **H3**: does not hold
- **H4**: does not hold
- **H5**: does not hold

## Results

| Set | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: |
| P02-06 changed | JADEN rules | 8,511 | 91.00% | 80 | 1.02% (0.82–1.27%) | 8.06% |
|  | geolonia | 8,511 | 0.46% | 0 | 0.00% (0.00–8.97%) | 99.54% |
|  | jageocoder | 8,511 | 82.76% | 802 | 10.22% (9.57–10.91%) | 7.81% |
| P02-06 unchanged | JADEN rules | 188,502 | 99.70% | 233 | 0.12% (0.11–0.14%) | 0.18% |
|  | JADEN rules (same sample as the other tools) | 5,000 | 99.60% | 10 | 0.20% (0.11–0.37%) | 0.20% |
|  | geolonia | 5,000 | 99.80% | 10 | 0.20% (0.11–0.37%) | 0.00% |
|  | jageocoder | 5,000 | 98.02% | 10 | 0.20% (0.11–0.37%) | 1.78% |
| P14-11 changed | JADEN rules | 1,367 | 99.20% | 1 | 0.07% (0.01–0.42%) | 0.73% |
|  | geolonia | 1,367 | 18.00% | 0 | 0.00% (0.00–1.54%) | 82.00% |
|  | jageocoder | 1,367 | 86.47% | 124 | 9.49% (8.02–11.21%) | 4.46% |
| P14-11 unchanged | JADEN rules | 89,395 | 99.80% | 77 | 0.09% (0.07–0.11%) | 0.11% |
|  | JADEN rules (same sample as the other tools) | 5,000 | 99.76% | 3 | 0.06% (0.02–0.18%) | 0.18% |
|  | geolonia | 5,000 | 99.26% | 3 | 0.06% (0.02–0.18%) | 0.68% |
|  | jageocoder | 5,000 | 99.94% | 3 | 0.06% (0.02–0.18%) | 0.00% |

## Changed inputs by kind of change

| Source | Kind | System | Inputs | Right | Wrong |
| :--- | :--- | :--- | ---: | ---: | ---: |
| P02-06 | merger | JADEN rules | 3,140 | 96.1% | 3 |
| P02-06 | merger | geolonia | 3,140 | 0.0% | 0 |
| P02-06 | merger | jageocoder | 3,140 | 63.3% | 559 |
| P02-06 | other | JADEN rules | 178 | 73.0% | 0 |
| P02-06 | other | geolonia | 178 | 21.9% | 0 |
| P02-06 | other | jageocoder | 178 | 56.2% | 39 |
| P02-06 | status or name change | JADEN rules | 5,193 | 88.5% | 77 |
| P02-06 | status or name change | geolonia | 5,193 | 0.0% | 0 |
| P02-06 | status or name change | jageocoder | 5,193 | 95.4% | 204 |
| P14-11 | merger | JADEN rules | 625 | 99.5% | 0 |
| P14-11 | merger | geolonia | 625 | 31.0% | 0 |
| P14-11 | merger | jageocoder | 625 | 79.5% | 87 |
| P14-11 | split | JADEN rules | 97 | 94.8% | 0 |
| P14-11 | split | geolonia | 97 | 0.0% | 0 |
| P14-11 | split | jageocoder | 97 | 81.4% | 18 |
| P14-11 | status or name change | JADEN rules | 286 | 99.0% | 1 |
| P14-11 | status or name change | geolonia | 286 | 0.0% | 0 |
| P14-11 | status or name change | jageocoder | 286 | 92.7% | 1 |
| P14-11 | ward | JADEN rules | 359 | 100.0% | 0 |
| P14-11 | ward | geolonia | 359 | 14.5% | 0 |
| P14-11 | ward | jageocoder | 359 | 95.0% | 18 |

## Reverse lookup (P02-06, retired 2006 codes that were also the 2000 code)

- eligible facilities: 3,794
- former_municipality agrees with the 2006 code: 2,322 (61.20%)
- no former municipality returned: 1,472
