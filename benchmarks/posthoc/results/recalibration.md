# Post-hoc: corrected calibration procedure

Same model weights as the pre-registered resolver; temperature on one fold of the calibration half, threshold (fixed-sequence testing, 1% target, 95%) and conformal quantiles (95%) on the other. Applied after both tests; the pre-registered results stand as reported.

## address

Folds A / B: 152,340 / 151,797 inputs. Temperature 0.966 (pre-registered 0.966); threshold 0.8732 (pre-registered 0.8823), after testing 323 thresholds in order.

| Data | Input | Threshold | Right | Wrong among answers (95% CI) | ECE | Conformal coverage / size |
| :--- | :--- | :--- | ---: | :--- | ---: | :--- |
| development check | town only | pre-registered | 66.57% | 0.92% (0.85%–0.99%) | 0.0164 | 95.03% / 2.15 |
| development check | with prefecture | pre-registered | 88.72% | 0.31% (0.28%–0.35%) | 0.0034 | 94.99% / 0.97 |
| development check | full | pre-registered | 99.36% | 0.25% (0.22%–0.28%) | 0.0054 | 94.92% / 0.95 |
| development check | town only | corrected | 66.84% | 1.02% (0.94%–1.09%) | 0.0164 | 94.93% / 2.13 |
| development check | with prefecture | corrected | 88.85% | 0.36% (0.32%–0.40%) | 0.0034 | 94.98% / 0.97 |
| development check | full | corrected | 99.45% | 0.25% (0.22%–0.28%) | 0.0054 | 95.04% / 0.95 |
| test 1 | town only | pre-registered | 59.78% | 1.10% (1.05%–1.15%) | 0.0146 | 93.72% / 2.39 |
| test 1 | with prefecture | pre-registered | 86.12% | 0.26% (0.24%–0.27%) | 0.0025 | 94.06% / 0.96 |
| test 1 | full | pre-registered | 99.98% | 0.00% (0.00%–0.00%) | 0.0023 | 99.66% / 1.00 |
| test 1 | town only | corrected | 60.10% | 1.20% (1.15%–1.24%) | 0.0146 | 93.63% / 2.36 |
| test 1 | with prefecture | corrected | 86.29% | 0.31% (0.29%–0.34%) | 0.0025 | 94.05% / 0.96 |
| test 1 | full | corrected | 99.98% | 0.00% (0.00%–0.00%) | 0.0023 | 99.66% / 1.00 |
| test 2 | town only | pre-registered | 58.59% | 0.72% (0.68%–0.77%) | 0.0062 | 93.77% / 2.33 |
| test 2 | no prefecture | pre-registered | 99.87% | 0.00% (0.00%–0.00%) | 0.0031 | 99.93% / 1.00 |
| test 2 | full | pre-registered | 99.94% | 0.00% (0.00%–0.00%) | 0.0017 | 99.85% / 1.00 |
| test 2 | town only | corrected | 58.95% | 0.89% (0.84%–0.94%) | 0.0062 | 93.66% / 2.30 |
| test 2 | no prefecture | corrected | 99.87% | 0.00% (0.00%–0.00%) | 0.0031 | 99.93% / 1.00 |
| test 2 | full | corrected | 99.95% | 0.00% (0.00%–0.00%) | 0.0017 | 99.85% / 1.00 |

## address+name

Folds A / B: 152,340 / 151,797 inputs. Temperature 0.933 (pre-registered 0.933); threshold 0.8773 (pre-registered 0.8783), after testing 325 thresholds in order.

| Data | Input | Threshold | Right | Wrong among answers (95% CI) | ECE | Conformal coverage / size |
| :--- | :--- | :--- | ---: | :--- | ---: | :--- |
| development check | town only | pre-registered | 67.79% | 0.94% (0.88%–1.02%) | 0.0086 | 95.11% / 1.97 |
| development check | with prefecture | pre-registered | 89.35% | 0.31% (0.28%–0.35%) | 0.0025 | 95.03% / 0.96 |
| development check | full | pre-registered | 99.45% | 0.25% (0.22%–0.28%) | 0.0050 | 94.93% / 0.95 |
| development check | town only | corrected | 67.83% | 0.95% (0.88%–1.02%) | 0.0086 | 95.06% / 1.96 |
| development check | with prefecture | corrected | 89.36% | 0.31% (0.28%–0.35%) | 0.0025 | 95.01% / 0.96 |
| development check | full | corrected | 99.46% | 0.25% (0.22%–0.28%) | 0.0050 | 94.94% / 0.95 |
| test 1 | town only | pre-registered | 61.20% | 1.14% (1.10%–1.19%) | 0.0073 | 93.83% / 2.16 |
| test 1 | with prefecture | pre-registered | 86.93% | 0.29% (0.27%–0.31%) | 0.0043 | 94.11% / 0.96 |
| test 1 | full | pre-registered | 99.98% | 0.00% (0.00%–0.00%) | 0.0018 | 99.71% / 1.00 |
| test 1 | town only | corrected | 61.24% | 1.15% (1.10%–1.20%) | 0.0073 | 93.79% / 2.15 |
| test 1 | with prefecture | corrected | 86.94% | 0.29% (0.27%–0.31%) | 0.0043 | 94.08% / 0.96 |
| test 1 | full | corrected | 99.98% | 0.00% (0.00%–0.00%) | 0.0018 | 99.71% / 1.00 |
| test 2 | town only | pre-registered | 59.80% | 0.87% (0.82%–0.92%) | 0.0049 | 93.72% / 2.12 |
| test 2 | no prefecture | pre-registered | 99.87% | 0.00% (0.00%–0.00%) | 0.0026 | 99.93% / 1.00 |
| test 2 | full | pre-registered | 99.95% | 0.00% (0.00%–0.00%) | 0.0013 | 99.85% / 1.00 |
| test 2 | town only | corrected | 59.84% | 0.88% (0.83%–0.93%) | 0.0049 | 93.67% / 2.11 |
| test 2 | no prefecture | corrected | 99.87% | 0.00% (0.00%–0.00%) | 0.0026 | 99.93% / 1.00 |
| test 2 | full | corrected | 99.95% | 0.00% (0.00%–0.00%) | 0.0013 | 99.85% / 1.00 |

