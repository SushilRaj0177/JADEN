# Held-out test: MLIT welfare facilities (2023)

Run once at commit `01a23ba0b8` under `benchmarks/heldout/PROTOCOL.md`. Right / wrong are counts of answers naming the row's municipality or another one; percentages are of all inputs; the interval is the Wilson 95% interval of the wrong-answer rate among answers.

## All categories

| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | AURC | ECE | Conformal 95%: coverage / size |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | ---: | :--- |
| town only | JADEN rules | 318,578 | 52.16% | 639 | 0.38% (0.35–0.41%) | 47.64% | – | – | – |
|  | JADEN calibrated | 318,578 | 59.78% | 2,115 | 1.10% (1.05–1.15%) | 39.56% | 0.0401 | 0.0146 | 93.72% / 2.39 |
|  | JADEN calibrated + name | 318,578 | 61.20% | 2,255 | 1.14% (1.10–1.19%) | 38.09% | 0.0352 | 0.0073 | 93.83% / 2.16 |
|  | geolonia | 318,578 | 0.03% | 6,256 | 98.40% (98.06–98.68%) | 98.00% | – | – | – |
|  | jageocoder | 318,578 | 76.46% | 66,164 | 21.36% (21.22–21.50%) | 2.77% | – | – | – |
| with prefecture | JADEN rules | 318,578 | 81.33% | 374 | 0.14% (0.13–0.16%) | 18.55% | – | – | – |
|  | JADEN calibrated | 318,578 | 86.12% | 702 | 0.26% (0.24–0.27%) | 13.66% | 0.0023 | 0.0025 | 94.06% / 0.96 |
|  | JADEN calibrated + name | 318,578 | 86.93% | 799 | 0.29% (0.27–0.31%) | 12.82% | 0.0018 | 0.0043 | 94.11% / 0.96 |
|  | geolonia | 318,578 | 0.03% | 194 | 64.67% (59.10–69.86%) | 99.91% | – | – | – |
|  | jageocoder | 318,578 | 2.51% | 4,758 | 37.28% (36.44–38.12%) | 95.99% | – | – | – |
| full | JADEN rules | 318,578 | 99.98% | 0 | 0.00% (0.00–0.00%) | 0.02% | – | – | – |
|  | JADEN calibrated | 318,578 | 99.98% | 0 | 0.00% (0.00–0.00%) | 0.02% | 0.0000 | 0.0023 | 99.66% / 1.00 |
|  | JADEN calibrated + name | 318,578 | 99.98% | 0 | 0.00% (0.00–0.00%) | 0.02% | 0.0000 | 0.0018 | 99.71% / 1.00 |
|  | geolonia | 318,578 | 100.00% | 0 | 0.00% (0.00–0.00%) | 0.00% | – | – | – |
|  | jageocoder | 318,578 | 100.00% | 0 | 0.00% (0.00–0.00%) | 0.00% | – | – | – |

## Categories that cannot be care offices

| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | AURC | ECE | Conformal 95%: coverage / size |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | ---: | :--- |
| town only | JADEN rules | 59,503 | 51.70% | 92 | 0.30% (0.24–0.37%) | 48.15% | – | – | – |
|  | JADEN calibrated | 59,503 | 60.11% | 369 | 1.02% (0.92–1.13%) | 39.27% | 0.0383 | 0.0094 | 93.92% / 2.39 |
|  | JADEN calibrated + name | 59,503 | 61.76% | 401 | 1.08% (0.98–1.19%) | 37.56% | 0.0333 | 0.0023 | 94.05% / 2.16 |
|  | geolonia | 59,503 | 0.03% | 1,091 | 98.55% (97.67–99.11%) | 98.14% | – | – | – |
|  | jageocoder | 59,503 | 77.59% | 11,907 | 20.50% (20.18–20.83%) | 2.40% | – | – | – |
| with prefecture | JADEN rules | 59,503 | 81.46% | 83 | 0.17% (0.14–0.21%) | 18.40% | – | – | – |
|  | JADEN calibrated | 59,503 | 86.58% | 131 | 0.25% (0.21–0.30%) | 13.20% | 0.0023 | 0.0027 | 94.02% / 0.96 |
|  | JADEN calibrated + name | 59,503 | 87.48% | 157 | 0.30% (0.26–0.35%) | 12.26% | 0.0019 | 0.0043 | 94.05% / 0.96 |
|  | geolonia | 59,503 | 0.03% | 31 | 64.58% (50.44–76.57%) | 99.92% | – | – | – |
|  | jageocoder | 59,503 | 2.58% | 941 | 37.96% (36.07–39.89%) | 95.83% | – | – | – |
| full | JADEN rules | 59,503 | 99.98% | 0 | 0.00% (0.00–0.01%) | 0.02% | – | – | – |
|  | JADEN calibrated | 59,503 | 99.98% | 0 | 0.00% (0.00–0.01%) | 0.02% | 0.0000 | 0.0021 | 99.83% / 1.00 |
|  | JADEN calibrated + name | 59,503 | 99.98% | 0 | 0.00% (0.00–0.01%) | 0.02% | 0.0000 | 0.0016 | 99.87% / 1.00 |
|  | geolonia | 59,503 | 100.00% | 0 | 0.00% (0.00–0.01%) | 0.00% | – | – | – |
|  | jageocoder | 59,503 | 100.00% | 0 | 0.00% (0.00–0.01%) | 0.00% | – | – | – |

## Language models on the inputs the calibrated resolver leaves unanswered

Systems 4 and 4b run on 1,000 town-only inputs the calibrated resolver with the name does not answer; system 5 on 1,000 random town-only inputs (PROTOCOL.md and its amendment). 'Kept' is system 4b's rule: the answer is one of JADEN's candidates and the model is at least 80% sure.

| System | Inputs | Answered | Right | Wrong (95% CI among answers) | Named no existing municipality | One of JADEN's candidates: right / wrong | Kept: right / wrong (95% CI) |
| :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| system 4: haiku chooses from JADEN's candidates | 1,000 | 526 | 360 | 166 (27.73–35.65%) | 0 | all (only candidates can be chosen) | – |
| system 4b: haiku proposes, JADEN verifies | 1,000 | 478 | 294 | 184 (34.24–42.93%) | 4 | 288 / 70 | 162 / 10 (3.19–10.37%) |
| system 4b: sonnet proposes, JADEN verifies | 1,000 | 851 | 452 | 399 (43.55–50.25%) | 2 | 444 / 41 | 295 / 8 (1.34–5.12%) |
| system 5: haiku alone | 1,000 | 624 | 458 | 166 (23.29–30.21%) | 6 | 439 / 33 | 315 / 3 (0.32–2.74%) |
| system 5: sonnet alone | 1,000 | 957 | 617 | 340 (32.56–38.61%) | 2 | 599 / 25 | 502 / 8 (0.80–3.06%) |

