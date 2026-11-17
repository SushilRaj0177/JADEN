## Valid addresses (higher accuracy/precision, lower wrong-answer is better)

| System | Variant | Accuracy | Coverage | Precision | Wrong answers | Geo median | Geo ≤1 km |
|---|---|---:|---:|---:|---:|---:|---:|
| jaden | original | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | town_only | 51.5% | 51.6% | 100.0% | 0.0% | 391 m | 77.9% |
| jaden | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | romaji | 100.0% | 100.0% | 100.0% | 0.0% | 298 m | 83.6% |
| jaden | former_name | 100.0% | 100.0% | 100.0% | 0.0% | 415 m | 83.2% |
| jaden-parser-only | original | 100.0% | 100.0% | 100.0% | 0.0% | – | – |
| jaden-parser-only | no_pref | 99.7% | 99.7% | 100.0% | 0.0% | – | – |
| jaden-parser-only | town_only | 0.1% | 2.3% | 5.7% | 2.1% | – | – |
| jaden-parser-only | noisy | 100.0% | 100.0% | 100.0% | 0.0% | – | – |
| jaden-parser-only | romaji | 0.0% | 0.0% | – | 0.0% | – | – |
| jaden-parser-only | former_name | 8.3% | 100.0% | 8.3% | 91.7% | – | – |
| jaden+blocks | original | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.8% |
| jaden+blocks | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.8% |
| jaden+blocks | town_only | 51.5% | 51.6% | 100.0% | 0.0% | 80 m | 87.2% |
| jaden+blocks | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.8% |
| jaden+blocks | romaji | 100.0% | 100.0% | 100.0% | 0.0% | 60 m | 93.5% |
| jaden+blocks | former_name | 100.0% | 100.0% | 100.0% | 0.0% | 51 m | 93.2% |

## Invalid inputs (false-accept rate: lower is better)

| System | wrong_pref | chome_99 | non_address |
|---|---:|---:|---:|
| jaden | 0.0% | 7.2% | 0.0% |
| jaden-parser-only | 0.0% | 100.0% | 57.9% |
| jaden+blocks | 0.0% | 7.2% | 0.0% |

## When a system abstains with a candidate list

| System | Variant | Abstained | With candidates | Gold in list | Median list size |
|---|---|---:|---:|---:|---:|
| jaden | no_pref | 1 | 1 | 100.0% | 2 |
| jaden | town_only | 2277 | 2156 | 98.6% | 8 |
| jaden-parser-only | no_pref | 12 | 12 | 100.0% | 11 |
| jaden-parser-only | town_only | 4594 | 14 | 0.0% | 3 |
| jaden+blocks | no_pref | 1 | 1 | 100.0% | 2 |
| jaden+blocks | town_only | 2277 | 2156 | 98.6% | 8 |

## Throughput

| System | Items/s |
|---|---:|
| jaden | 2,111 |
| jaden-parser-only | 6,649 |
| jaden+blocks | 381 |
