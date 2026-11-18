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
| jaden+blocks | original | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.9% |
| jaden+blocks | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.9% |
| jaden+blocks | town_only | 51.5% | 51.6% | 100.0% | 0.0% | 79 m | 87.3% |
| jaden+blocks | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 71 m | 88.9% |
| jaden+blocks | romaji | 100.0% | 100.0% | 100.0% | 0.0% | 60 m | 93.6% |
| jaden+blocks | former_name | 100.0% | 100.0% | 100.0% | 0.0% | 51 m | 93.2% |
| geolonia | original | 100.0% | 100.0% | 100.0% | 0.0% | 128 m | 85.0% |
| geolonia | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 128 m | 85.0% |
| geolonia | town_only | 0.1% | 2.2% | 4.8% | 2.1% | 116 m | 100.0% |
| geolonia | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 128 m | 85.0% |
| geolonia | romaji | 0.0% | 0.0% | – | 0.0% | – | – |
| geolonia | former_name | 8.3% | 8.3% | 100.0% | 0.0% | 1359 m | 35.3% |
| jageocoder | original | 100.0% | 100.0% | 100.0% | 0.0% | 65 m | 91.0% |
| jageocoder | no_pref | 100.0% | 100.0% | 100.0% | 0.0% | 65 m | 91.0% |
| jageocoder | town_only | 76.9% | 96.5% | 79.7% | 19.6% | 60 m | 94.5% |
| jageocoder | noisy | 100.0% | 100.0% | 100.0% | 0.0% | 139 m | 69.6% |
| jageocoder | romaji | 0.0% | 27.9% | 0.0% | 27.9% | – | – |
| jageocoder | former_name | 97.1% | 100.0% | 97.1% | 2.9% | 49 m | 94.7% |

## Invalid inputs (false-accept rate: lower is better)

| System | wrong_pref | chome_99 | non_address |
|---|---:|---:|---:|
| jaden | 0.0% | 7.2% | 0.0% |
| jaden-parser-only | 0.0% | 100.0% | 57.9% |
| jaden+blocks | 0.0% | 7.2% | 0.0% |
| geolonia | 0.0% | 100.0% | 52.5% |
| jageocoder | 0.1% | 100.0% | 67.5% |

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
| jaden | 2,136 |
| jaden-parser-only | 6,544 |
| jaden+blocks | 440 |
