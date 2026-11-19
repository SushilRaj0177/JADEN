# Calibrated resolver: development results

Fitted on company addresses, calibrated on half the care offices, checked on the other half. No held-out test data is used here.

## address

Temperature 0.966; answer threshold 0.8823 (1% target); weights: log_town_companies +0.53, log_town_share +0.26, log_muni_companies +0.09, town_exact +0.00, town_found +0.87, chome_exists +0.75, chome_unchecked -0.31, rules_accepted +0.49, muni_written +0.26, muni_homonym -0.08, name_mentions_muni +0.00, name_mentions_pref +0.00, bias -0.47, log_candidates +0.91, rules_accepted -0.49, rules_ambiguous +0.02, rules_rejected +0.00, muni_written -0.26, town_verified -0.58, has_numbers -0.40, deduced_from_town -0.06

| Set | Input | Inputs | Rules: right / wrong / no answer | Calibrated at threshold: right / wrong (95% CI) / answered | AURC | ECE | Conformal 95%: coverage / mean size |
| :--- | :--- | ---: | :--- | :--- | ---: | ---: | :--- |
| calib | town only | 101,379 | 58.99% / 187 / 40.83% | 66.58% / 638 (0.87%–1.01%) / 67.21% | 0.0290 | 0.0162 | 95.00% / 2.15 |
| calib | with prefecture | 101,379 | 84.85% / 216 / 14.94% | 88.73% / 289 (0.29%–0.36%) / 89.02% | 0.0023 | 0.0031 | 95.00% / 0.97 |
| calib | full | 101,379 | 99.44% / 54 / 0.50% | 99.41% / 269 (0.24%–0.30%) / 99.67% | 0.0003 | 0.0054 | 95.03% / 0.95 |
| devcheck | town only | 101,971 | 58.93% / 173 / 40.90% | 66.57% / 629 (0.85%–0.99%) / 67.19% | 0.0289 | 0.0164 | 95.03% / 2.15 |
| devcheck | with prefecture | 101,971 | 84.84% / 176 / 14.98% | 88.72% / 284 (0.28%–0.35%) / 89.00% | 0.0022 | 0.0034 | 94.99% / 0.97 |
| devcheck | full | 101,971 | 99.44% / 50 / 0.51% | 99.36% / 256 (0.22%–0.28%) / 99.61% | 0.0003 | 0.0054 | 94.95% / 0.95 |

## address+name

Temperature 0.933; answer threshold 0.8783 (1% target); weights: log_town_companies +0.53, log_town_share +0.25, log_muni_companies +0.09, town_exact +0.00, town_found +0.86, chome_exists +0.75, chome_unchecked -0.31, rules_accepted +0.49, muni_written +0.26, muni_homonym -0.08, name_mentions_muni +1.09, name_mentions_pref +0.56, bias -0.46, log_candidates +0.91, rules_accepted -0.49, rules_ambiguous +0.03, rules_rejected +0.00, muni_written -0.26, town_verified -0.58, has_numbers -0.39, deduced_from_town -0.06

| Set | Input | Inputs | Rules: right / wrong / no answer | Calibrated at threshold: right / wrong (95% CI) / answered | AURC | ECE | Conformal 95%: coverage / mean size |
| :--- | :--- | ---: | :--- | :--- | ---: | ---: | :--- |
| calib | town only | 101,379 | 58.99% / 187 / 40.83% | 67.81% / 650 (0.87%–1.01%) / 68.45% | 0.0254 | 0.0093 | 95.00% / 1.97 |
| calib | with prefecture | 101,379 | 84.85% / 216 / 14.94% | 89.38% / 318 (0.31%–0.39%) / 89.69% | 0.0019 | 0.0020 | 95.01% / 0.96 |
| calib | full | 101,379 | 99.44% / 54 / 0.50% | 99.46% / 266 (0.23%–0.30%) / 99.72% | 0.0002 | 0.0053 | 95.00% / 0.95 |
| devcheck | town only | 101,971 | 58.93% / 173 / 40.90% | 67.79% / 659 (0.88%–1.02%) / 68.44% | 0.0254 | 0.0086 | 95.11% / 1.97 |
| devcheck | with prefecture | 101,971 | 84.84% / 176 / 14.98% | 89.35% / 283 (0.28%–0.35%) / 89.63% | 0.0019 | 0.0025 | 95.03% / 0.96 |
| devcheck | full | 101,971 | 99.44% / 50 / 0.51% | 99.45% / 252 (0.22%–0.28%) / 99.70% | 0.0002 | 0.0050 | 94.93% / 0.95 |

