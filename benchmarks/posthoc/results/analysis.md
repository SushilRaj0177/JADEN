# Post-hoc analyses

Computed after both tests from their stored outputs; see the docstring of `analysis.py` for what each section is. No pre-registered number changes.

## 1–2. Forced answers and where the calibrated resolver is wrong (town only)

| Test | Model | With candidates | Forced: wrong | At threshold: answered | wrong | truth not among candidates | ranking error |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| test 1 | calibrated | 310,296 | 70,197 (22.62%) | 192,556 | 2,115 | 1,082 | 1,033 |
| test 1 | calibrated + name | 310,296 | 64,342 (20.74%) | 197,239 | 2,255 | 1,156 | 1,099 |
| test 2 | calibrated | 194,975 | 42,050 (21.57%) | 121,467 | 880 | 247 | 633 |
| test 2 | calibrated + name | 194,975 | 39,398 (20.21%) | 124,162 | 1,075 | 359 | 716 |

## 3. Town-only inputs that start with a municipality name (calibrated, at the threshold)

| Data | Such inputs | Answered | Wrong | Wrong among answers |
| :--- | ---: | ---: | ---: | ---: |
| care offices (development check) | 2,485 | 730 | 185 | 25.34% |
| test 1 | 7,103 | 2,374 | 856 | 36.06% |
| test 2 | 5,018 | 884 | 127 | 14.37% |

## 4. Language models on test 1, filters separated

Kept = answers that survive the filter; discarded right = right answers the filter throws away.

| System | Sample | Filter | Kept | Wrong among kept (95% CI) | Right answers discarded |
| :--- | :--- | :--- | ---: | :--- | ---: |
| haiku chooses | remainder | none | 526 | 166 (27.7–35.7%) | 0 |
| haiku chooses | remainder | confidence ≥ 80 | 337 | 70 (16.8–25.4%) | 93 |
| haiku proposes | remainder | none | 478 | 184 (34.2–42.9%) | 0 |
| haiku proposes | remainder | confidence ≥ 80 | 180 | 13 (4.3–12.0%) | 127 |
| haiku proposes | remainder | in JADEN's candidates | 358 | 70 (15.8–24.0%) | 6 |
| haiku proposes | remainder | both (system 4b) | 172 | 10 (3.2–10.4%) | 132 |
| sonnet proposes | remainder | none | 851 | 399 (43.6–50.2%) | 0 |
| sonnet proposes | remainder | confidence ≥ 80 | 339 | 38 (8.3–15.0%) | 151 |
| sonnet proposes | remainder | in JADEN's candidates | 485 | 41 (6.3–11.3%) | 8 |
| sonnet proposes | remainder | both (system 4b) | 303 | 8 (1.3–5.1%) | 157 |
| haiku alone | random | none | 624 | 166 (23.3–30.2%) | 0 |
| haiku alone | random | confidence ≥ 80 | 360 | 31 (6.1–12.0%) | 129 |
| haiku alone | random | in JADEN's candidates | 472 | 33 (5.0–9.7%) | 19 |
| haiku alone | random | both (system 4b) | 318 | 3 (0.3–2.7%) | 143 |
| sonnet alone | random | none | 957 | 340 (32.6–38.6%) | 0 |
| sonnet alone | random | confidence ≥ 80 | 588 | 70 (9.5–14.8%) | 99 |
| sonnet alone | random | in JADEN's candidates | 624 | 25 (2.7–5.8%) | 18 |
| sonnet alone | random | both (system 4b) | 510 | 8 (0.8–3.1%) | 115 |

## 5. Projection: calibrated + name, then verified proposals (test 1, town only)

Town-only inputs: 318,578. Calibrated + name answers 197,239 (194,984 right, 2,255 wrong). Inputs left with candidates (the population the remainder sample was drawn from): 113,057.

| Proposals from | Kept per 1,000: right / wrong | Projected right | Projected wrong among answers |
| :--- | :--- | ---: | ---: |
| haiku proposes | 162 / 10 | 67.0% | 1.56% |
| sonnet proposes | 295 / 8 | 71.7% | 1.36% |

## 6. Wilson intervals against a cluster bootstrap over identical inputs (town only)

| Test | System | Answered | Wrong | Wilson 95% | Cluster bootstrap 95% |
| :--- | :--- | ---: | ---: | :--- | :--- |
| test 1 | rules | 166,816 | 639 | 0.355–0.414% | 0.346–0.421% |
| test 1 | calibrated | 192,556 | 2,115 | 1.053–1.146% | 1.040–1.163% |
| test 2 | rules | 100,715 | 279 | 0.246–0.311% | 0.220–0.356% |
| test 2 | calibrated | 121,467 | 880 | 0.678–0.774% | 0.675–0.770% |

## 7. Sizes

- training inputs: 359,994
- calibration inputs: 304,137
- development-check inputs: 305,913
