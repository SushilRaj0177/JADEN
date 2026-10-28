## Valid addresses (higher accuracy/precision, lower wrong-answer is better)

| System | Variant | Accuracy | Coverage | Precision | Wrong answers | Geo median | Geo ≤1 km |
|---|---|---:|---:|---:|---:|---:|---:|
| jaden | original | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | town_only | 50.4% | 50.5% | 100.0% | 0.0% | 386 m | 78.0% |
| jaden | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 360 m | 79.3% |
| jaden | romaji | 100.0% | 100.0% | 100.0% | 0.0% | 297 m | 83.6% |
| jaden+blocks | original | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 89.0% |
| jaden+blocks | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 89.0% |
| jaden+blocks | town_only | 50.4% | 50.5% | 100.0% | 0.0% | 77 m | 87.5% |
| jaden+blocks | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 89.0% |
| jaden+blocks | romaji | 100.0% | 100.0% | 100.0% | 0.0% | 59 m | 93.6% |
| jaden-parser-only | original | 100.0% | 100.0% | 100.0% | 0.0% | – | – |
| jaden-parser-only | no_pref | 99.7% | 99.7% | 100.0% | 0.0% | – | – |
| jaden-parser-only | town_only | 0.1% | 2.3% | 5.7% | 2.1% | – | – |
| jaden-parser-only | noisy | 100.0% | 100.0% | 100.0% | 0.0% | – | – |
| jaden-parser-only | romaji | 0.0% | 0.0% | – | 0.0% | – | – |

## Invalid inputs (false-accept rate: lower is better)

| System | wrong_pref | chome_99 | non_address |
|---|---:|---:|---:|
| jaden | 0.0% | 7.2% | 0.0% |
| jaden+blocks | 0.0% | 7.2% | 0.0% |
| jaden-parser-only | 0.0% | 100.0% | 57.9% |

## When a system abstains with a candidate list

| System | Variant | Abstained | With candidates | Gold in list | Median list size |
|---|---|---:|---:|---:|---:|
| jaden | no_pref | 1 | 1 | 100.0% | 2 |
| jaden | town_only | 2328 | 2125 | 98.6% | 8 |
| jaden+blocks | no_pref | 1 | 1 | 100.0% | 2 |
| jaden+blocks | town_only | 2328 | 2125 | 98.6% | 8 |
| jaden-parser-only | no_pref | 12 | 12 | 100.0% | 11 |
| jaden-parser-only | town_only | 4594 | 14 | 0.0% | 3 |

## Throughput

| System | Items/s |
|---|---:|
| jaden | 2,867 |
| jaden+blocks | 373 |
| jaden-parser-only | 8,820 |
