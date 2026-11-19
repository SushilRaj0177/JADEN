# Knowing When You Do Not Know Where: Calibrated, Verified Resolution of Japanese Addresses, with Language Models in the Loop

**Draft v0.3 — Sushil Raj**

> Status: working draft, 19 November 2026. Every number comes from a script in this repository at a recorded commit; the held-out results are from one pre-registered run (`benchmarks/heldout/PROTOCOL.md`, commit `991bffb`, amended before any language-model call in `01a23ba`). The earlier draft is `paper/jaden-v0.2-draft.md`.

## Abstract

When a Japanese address does not name its municipality, the town name that remains often exists in many places: 錦町 is a registered town in 93 municipalities. Address tools either always answer, turning this ambiguity into silent errors, or refuse, leaving the address unresolved. We ask whether a resolver can *know when it does not know*: attach probabilities to candidate municipalities that are calibrated on data it has never seen, answer as many addresses as possible at a chosen error rate, and return candidate sets with a coverage guarantee. We build this on JADEN, an offline rule engine that grounds every decision in official registries, by adding a conditional-logit scorer with a "none of these" option, a town-frequency prior from 5 million registered companies, temperature calibration, a risk-controlled answer threshold, and split-conformal candidate sets. We also test two ways of letting a large language model resolve what remains: choosing from JADEN's candidates, and proposing freely while JADEN verifies. In a pre-registered evaluation on 321,859 welfare-facility addresses that no part of the system was developed on, the calibrated resolver answers 59.8% of town-only addresses (61.2% with the facility name), against 52.2% for the rules alone, with expected calibration error 0.015 (0.007), and full addresses are resolved with no wrong answer in 318,578. Two pre-registered guarantees fall slightly short under the shift between publishers: the wrong-answer rate is 1.10% for a 1% target and conformal sets cover 93.7% for a 95% target. On the same addresses, jageocoder answers 76.5% of the town-only addresses correctly but is wrong on 21.4% of those it answers (66,164 wrong answers, against 639 for JADEN's rules), and Geolonia answers 2.0% of them, almost all wrongly. A language model choosing from JADEN's candidates is wrong on 31.6% of its answers; proposing freely and keeping only answers that JADEN verifies keeps 30.3% of the hardest remainder with 2.6% wrong (Sonnet; 391 of its 399 free wrong answers removed). Projected from that sample, JADEN with verified proposals resolves 71.8% of town-only addresses at a 1.4% wrong-answer rate.

## 1. Introduction

Address resolution is usually scored by how often a system returns the right answer. For Japanese addresses this hides the failure that matters in practice: an answer that is confidently wrong. Municipality names repeat (11 wards are called 中央区), municipality names are also town names elsewhere (栄町 is a town in Chiba and a town name in 224 other places), and real records often drop the municipality altogether: the national welfare-facility file used here publishes every address *without* it.

The information needed to do better is public. MLIT lists every registered town and 丁目; Japan Post lists every postal code; the National Tax Agency publishes the registered address of every company. A resolver that consults them can often prove that only one municipality fits. When several fit, the remaining question is statistical: which one, and how sure can it be?

This paper makes four contributions.

1. **A calibrated resolver on top of registry-grounded rules** (Section 4). Each candidate municipality, and the possibility that the right one is none of them, gets a probability from a conditional logit fitted on company addresses. A town-frequency prior counts the 4,977,458 companies whose registered address lies in each of 107,653 registered towns. The probabilities are calibrated by temperature scaling; an answer threshold is chosen with a Clopper–Pearson bound for a 1% wrong-answer rate (selective classification with guaranteed risk); split-conformal sets target 95% coverage.
2. **A pre-registered held-out evaluation** (Sections 6–7). The question, test file, systems, measures and six hypotheses were committed before anything ran on the test data; one amendment, made on development evidence before any language-model call on test data, added two systems. Results are reported as they came out, including the hypotheses that failed.
3. **Language models in the loop, measured** (Sections 5 and 7.4). Choosing from a verified candidate list does not make a model's answers reliable (31.6% wrong on test); letting it propose freely and keeping only answers the registry confirms removes 98% of its errors. The larger model is wrong more often on its own (47% vs 38% of its answers on the same inputs) and less often once verified (2.6% vs 5.8%).
4. **An error analysis that found two rule defects** (Section 8): a building after the house number switched off the check for municipality-name homonyms, and municipalities sharing a name did not bring the towns of that name. Together they caused 486 of the rule engine's 639 wrong town-only answers on test.

JADEN is open source (MIT), runs offline, and has no runtime dependencies; the calibrated resolver ships as `jaden.resolve()`.

## 2. Related work

**Japanese address tools.** Geolonia's normalize-japanese-addresses and jageocoder (Sagara) normalise and geocode Japanese addresses against MLIT and Digital Agency data; both return their best match without a measure of ambiguity. JADEN v0.2 (the previous draft) introduced abstention with candidate lists and JA-AddrBench.

**Geocoding with language models.** End-to-end systems generate coordinates directly (ReaGeo, 2026, which decodes geohashes with chain-of-thought and a distance reward) or ground complex location references with LLMs (Masis and O'Connor, EACL 2026). Benchmarks show that the gap between commercial and open-source geocoders on messy real addresses comes mostly from returning no candidate at all (MESSY STREETS, 2026), and that LLMs hallucinate geographic facts (GeoHaluBench, EMNLP Findings 2025). The closest design to ours is AddrKG-LLM (Scientific Reports, 2026), which retrieves candidate communities with contrastive embeddings and a knowledge graph and lets an on-premise LLM choose only among them, refusing when none fits. We add calibrated probabilities with guarantees, compare choosing with verified proposing, and test on a pre-registered held-out set.

**Selective prediction and calibration.** Reject options go back to Chow (1970); selective classification with a guaranteed risk (Geifman and El-Yaniv, 2017) chooses a confidence threshold whose risk upper bound meets a target. Temperature scaling (Guo et al., 2017) calibrates a scorer with one parameter. Split conformal prediction (Vovk et al., 2005; Angelopoulos and Bates, 2021) gives prediction sets with marginal coverage under exchangeability; pipeline versions extend it to multi-stage language systems (PASC, 2026). Exchangeability is exactly what breaks when development and test data come from different publishers, which our test measures.

## 3. The rule engine

JADEN parses an address into prefecture, municipality, town, 丁目 and block numbers, and checks each against official data: the MIC municipality list, MLIT's 191,100 registered towns and 丁目 (大字・町丁目レベル位置参照情報 19.0b), Japan Post's postal codes, and 1,829 former municipality names. When the municipality is missing, every municipality where the written town is registered becomes a candidate; candidates are removed only by registry facts (the 丁目 does not exist there, the postal code belongs elsewhere). One survivor is ACCEPTED; several are AMBIGUOUS, with the list. On every active company in Japan (5,049,462 registered addresses), the rules name the row's municipality for 99.98% of full addresses with 6 wrong answers, each a row whose own municipality column contradicts its address; on 223,161 hand-typed care-office addresses with the prefecture and municipality columns added, 99.87%.

## 4. Calibrated resolution

**Candidates and evidence.** For an input, the candidates are JADEN's accepted municipality or its ambiguous list (at most 60, keeping municipality-name readings and then the most common towns). Each candidate *c* gets a feature vector *x_c*: the number of companies registered in the matched town there (log) and its share among the candidates; the number of companies in the municipality (log); whether the town and the written 丁目 exist there; whether the rules accepted it or the municipality was written; whether it is a municipality whose name the input uses as a town name; and, when given, whether the organisation's name mentions the municipality or the prefecture. The input also gets a vector *g* describing the evidence that the answer is none of the candidates: their number, what the rules said, whether a town was verified, whether block numbers were written.

**Model.** A conditional logit with an outside option:

  P(c) = exp(w·x_c) / Z,  P(none) = exp(v·g) / Z,  Z = Σ_c exp(w·x_c) + exp(v·g).

The outside option matters: the registry does not hold every local name, so a single candidate is not certain. Parameters are fitted by maximum likelihood (L-BFGS, L2 penalty 10⁻³) on 359,994 inputs built from a random sample of 120,000 company addresses: the town part alone, prefecture + town part, and the full address, each with the company's name. The town prior leaves each training row's own company out of its counts.

**Calibration and guarantees.** On half of the care offices (304,137 inputs, split by office number), a single temperature is fitted; the answer threshold τ is the lowest probability for which, for each input type, the 95% Clopper–Pearson upper bound of the wrong-answer rate among answers with p ≥ τ is at most 1% (τ = 0.882; 0.878 with the name); conformal quantiles per input type give sets {c : 1 − P(c) ≤ q̂} that should hold the right option, possibly "none", 95% of the time. The other half (305,913 inputs) is a development check of everything chosen.

## 5. Language models in the loop

For inputs the calibrated resolver does not answer, a language model receives the address and the organisation's name.

- **Choose** (system 4): JADEN's candidates are listed, numbered; the model returns one number or 0. Only a candidate can come back.
- **Propose and verify** (system 4b): no list; the model names the prefecture and municipality; the answer is mapped to the MIC list by name and kept only if it is one of JADEN's candidates and the model states at least 80% confidence.
- **Alone** (system 5): the free answer, unverified.

Models are called through the Claude Code command line with a fixed prompt, 20 addresses per call; prompts and raw answers are kept. A development trial on 400 ambiguous care addresses (Table 4) motivated system 4b before any test call.

## 6. Evaluation protocol

| Role | Data | Size |
| :--- | :--- | ---: |
| Prior and training | National Tax Agency corporate register (2026-10-30) | 5,049,462 companies; 359,994 training inputs |
| Calibration / development check | MHLW care-office register (June 2026), split by office number | 304,137 / 305,913 inputs |
| **Held-out test** | **MLIT 国土数値情報 welfare facilities P14 (2023), SHA-256 `5d038a85…98d`** | **321,859 facilities × 3 inputs** |

Each test facility gives a town-only input (the address as published), a prefecture + address input and a full input; the facility name is side information. The answer key is the file's own municipality code; an answer is right when it names that municipality or a ward of that designated city. The test's "other" category includes care facilities that may also appear in the development data under another publisher's spelling, so results are also reported for categories that cannot overlap (protective, disability and child-welfare facilities; 59,503 per input type). Before the protocol was written, three Tokyo test addresses were run through JADEN while inspecting the file format; no decision used them.

## 7. Results

### 7.1 Development check (care offices, never fitted or calibrated on)

| Town-only input (101,971) | Right | Wrong among answers | ECE | Conformal coverage / size |
| :--- | ---: | ---: | ---: | :--- |
| Rules | 58.93% | 0.29% | – | – |
| Calibrated | 66.57% | 0.93% | 0.016 | 95.03% / 2.15 |
| Calibrated + name | 67.79% | 0.96% | 0.009 | 95.11% / 1.97 |

### 7.2 Held-out test: JADEN

| Input (318,578 each) | System | Right | Wrong | Wrong among answers (95% CI) | ECE | Conformal coverage / size |
| :--- | :--- | ---: | ---: | :--- | ---: | :--- |
| town only | Rules | 52.16% | 639 | 0.38% (0.35–0.41%) | – | – |
| | Calibrated | 59.78% | 2,115 | 1.10% (1.05–1.15%) | 0.015 | 93.72% / 2.39 |
| | Calibrated + name | **61.20%** | 2,255 | 1.14% (1.10–1.19%) | **0.007** | 93.83% / 2.16 |
| with prefecture | Rules | 81.33% | 374 | 0.14% | – | – |
| | Calibrated + name | **86.93%** | 799 | 0.29% (0.27–0.31%) | 0.004 | 94.11% / 0.96 |
| full | Rules | 99.98% | **0** | 0.00% | – | – |
| | Calibrated + name | 99.98% | **0** | 0.00% | 0.002 | 99.71% / 1.00 |

On the categories that cannot overlap with the care data, the town-only wrong-answer rate at the threshold is 1.02% (0.92–1.13%) and 1.08% with the name. Figures: `benchmarks/heldout/results/risk_coverage.png`, `reliability.png`.

### 7.3 Held-out test: other tools

| Input (318,578 each) | System | Right | Wrong | Wrong among answers (95% CI) | No answer |
| :--- | :--- | ---: | ---: | :--- | ---: |
| town only | JADEN rules | 52.16% | 639 | 0.38% (0.35–0.41%) | 47.64% |
| | JADEN calibrated + name | 61.20% | 2,255 | 1.14% (1.10–1.19%) | 38.09% |
| | jageocoder | **76.46%** | 66,164 | 21.36% (21.22–21.50%) | 2.77% |
| | Geolonia | 0.03% | 6,256 | 98.40% (98.06–98.68%) | 98.00% |
| with prefecture | JADEN calibrated + name | **86.93%** | 799 | 0.29% | 12.82% |
| | jageocoder | 2.51% | 4,758 | 37.28% | 95.99% |
| | Geolonia | 0.03% | 194 | 64.67% | 99.91% |
| full | JADEN rules | 99.98% | 0 | 0.00% | 0.02% |
| | jageocoder | 100.00% | 0 | 0.00% | 0.00% |
| | Geolonia | 100.00% | 0 | 0.00% | 0.00% |

With the full address, all three tools are right on essentially every input. Without the municipality, jageocoder answers almost everything and Geolonia almost nothing; with the prefecture written before the town, both stop at the prefecture. Forced to answer every town-only input, JADEN's top candidate is about as often wrong as jageocoder's answer (the right end of the risk-coverage curve, about 20%); the difference is that JADEN's probability says which answers carry that risk.

### 7.4 Language models

**Table 4. Development trial (400 ambiguous care addresses).**

| | Answered | Wrong | Kept by JADEN: answered / wrong | … and confidence ≥ 80 |
| :--- | ---: | ---: | :--- | :--- |
| haiku chooses from the list | 282 | 78 | – | 185 / 26 |
| haiku proposes | 218 | 70 | 172 / 27 | 103 / 7 |
| sonnet proposes | 262 | 109 | 168 / 17 | 137 / 6 |

**Held-out test (1,000-input samples).**

| System | Sample | Answered | Wrong (95% CI among answers) | Named no existing municipality | Kept by the verifier: answered / wrong (95% CI) |
| :--- | :--- | ---: | :--- | ---: | :--- |
| 4: haiku chooses from JADEN's candidates | unanswered remainder | 526 | 166 (27.7–35.7%) | 0 | – |
| 4b: haiku proposes, JADEN verifies | unanswered remainder | 478 | 184 (34.2–42.9%) | 4 | 172 / 10 (3.2–10.4%) |
| 4b: sonnet proposes, JADEN verifies | unanswered remainder | 851 | 399 (43.6–50.3%) | 2 | 303 / 8 (1.3–5.1%) |
| 5: haiku alone | random town-only | 624 | 166 (23.3–30.2%) | 6 | (318 / 3 if verified) |
| 5: sonnet alone | random town-only | 957 | 340 (32.6–38.6%) | 2 | (510 / 8 if verified) |

The remainder sample is drawn from the 114,277 town-only inputs that the calibrated resolver with the name leaves unanswered but that have candidates. Projected from it, adding Sonnet's verified proposals to the calibrated resolver gives 71.8% right at 1.37% wrong among answers (the added wrong answers, 914, have a 95% range of 464–1,795); with Haiku, 67.0% at 1.57%. The names that do not exist are outdated or mismatched places: 茶屋町 (merged into 倉敷市 in 2005), 浜松市中区 (abolished in 2024), 伊丹市 placed in 大阪府.

### 7.5 Hypotheses

| | Pre-registered statement | Result |
| :--- | :--- | :--- |
| H1 | Rules give fewer wrong town-only answers than jageocoder and Geolonia | **Held**: 639 wrong, against 66,164 (jageocoder) and 6,256 (Geolonia) |
| H2 | Calibration transfers: ECE ≤ 0.03 on test | **Held**: 0.015 (0.007 with name) |
| H3 | The 1% threshold's test wrong-answer rate has a 95% interval including or below 1% | **Failed narrowly**: 1.10% (1.05–1.15%); held on the non-overlapping categories (0.92–1.13%) |
| H4 | The calibrated system answers more than the rules, and the name adds more | **Held**: +7.6 points, +1.4 more with the name |
| H5 | Conformal 95% sets cover ≥ 95% on test | **Failed**: 93.7% (town only), 94.1% (with prefecture) |
| H6 | The model choosing from JADEN's candidates is wrong on < 5% of its answers; alone, it is wrong more often and invents municipalities | **First part failed**: 31.6% (27.7–35.7%). Second part held: alone, the model is wrong on 26.6% (haiku) and 35.5% (sonnet) of its answers, and named 6 and 2 municipalities that do not exist |
| H7 (amendment) | Propose-and-verify: 95% upper bound ≤ 10%, and verification removes most free errors | **Held for sonnet**: 2.6% (1.3–5.1%), 391 of 399 free wrong answers removed. **Failed narrowly for haiku**: 5.8% (3.2–10.4%), upper bound above 10%; 174 of 184 removed |

## 8. Analysis

**Where the calibrated resolver is wrong.** Of its 2,115 wrong town-only answers on test, 1,082 (51%) are inputs whose right municipality is not among the candidates at all, and 1,033 are ranking errors among candidates (`築地4-2-19` read as Tokyo's 築地 for a facility in Amagasaki). Within the first group, one pattern dominates: an address that *starts with a municipality name* (`富岡町1-56-26-2`, `東川町7-9 オフィス1階`). In the care data such inputs nearly always do name their municipality (9,491 answered, 1.0% wrong); in the welfare file the municipality is never written, so they are towns that share a municipality's name (590 answered, 82% wrong). This is the distribution shift behind H3 and H5, and it pointed to two rule defects: a building or floor after the numbers switched off the check for such homonyms (the text the name took was measured by a length difference), and municipalities sharing a name (four are called 池田町) did not bring the towns of that name inside other cities. Both are fixed after the test (commit `db3c9aa`); the reported results use the engine before the fix.

**What the name adds.** Mentions of the municipality are the largest learned weight (+1.09), and the name halves the test calibration error. The feature is crude: `東神楽町立東神楽小学校` *is run by* 東神楽町, a stronger statement than a mention, and the model does not distinguish the two.

**Choosing anchors the model.** Given a list, the model answers more often and is wrong as often as when it answers freely (Table 4); its stated confidence separates right from wrong poorly. Verification works the other way: a wrong free answer is usually a municipality where the town does not exist, which the registry rejects.

## 9. Limitations

- Calibration was fitted on care-office data and tested on welfare-facility data; the two guarantees that rely on exchangeability fell short by about one point. A deployment on different data should recalibrate on a sample of it.
- Town-level and block-level correctness are not scored, only the municipality.
- The language-model results come from one model family, one prompt and 1,000-input samples; they cost money and change as models change.
- The town prior counts companies, not residents; residential addresses may be distributed differently.
- Two rule defects were found on the test data and fixed afterwards; any re-measurement on the same test would be biased and is not reported as a result.

## 10. Reproducibility

```bash
python benchmarks/realdata/download.py care companies welfare
python benchmarks/calibration/build_prior.py           # town prior from the company register
python benchmarks/calibration/make_dev.py               # training, calibration and check sets
python benchmarks/calibration/train.py                  # model.json and dev_report.md
python benchmarks/heldout/make_inputs.py --out DIR
python benchmarks/heldout/evaluate_heldout.py prepare --dir DIR
python benchmarks/heldout/evaluate_heldout.py samples --dir DIR
python benchmarks/heldout/llm.py choose DIR/llm_choose_items.jsonl DIR/llm_choose.jsonl   # and the free runs
python benchmarks/heldout/evaluate_heldout.py report --dir DIR --external geolonia=... jageocoder=...
```

## Data attribution

- 「大字・町丁目レベル位置参照情報 国土交通省」2025年版 (19.0b) を加工して作成
- 「国土数値情報（福祉施設データ）」（国土交通省）（令和5年度）を加工して作成 — CC BY 4.0
- 「国土数値情報（学校データ）」（国土交通省）（令和5年度）を加工して作成 — CC BY 4.0
- 国税庁法人番号公表サイト 全件データ（2026年10月30日）を加工して作成
- 厚生労働省 介護サービス情報公表システム オープンデータ（2026年6月末時点）を加工して作成
- 郵便番号データ（日本郵便株式会社）; 都道府県コード及び市区町村コード（総務省）

## References

- A. N. Angelopoulos and S. Bates. A gentle introduction to conformal prediction and distribution-free uncertainty quantification. arXiv:2107.07511, 2021.
- C. K. Chow. On optimum recognition error and reject tradeoff. *IEEE Transactions on Information Theory*, 16(1):41–46, 1970.
- E. Gaere. MESSY STREETS: A benchmark for geocoding real-world addresses. arXiv:2609.01612, 2026.
- Y. Geifman and R. El-Yaniv. Selective classification for deep neural networks. *NeurIPS*, 2017.
- C. Guo, G. Pleiss, Y. Sun and K. Q. Weinberger. On calibration of modern neural networks. *ICML*, 2017.
- T. Masis and B. O'Connor. Coordinates from context: Using LLMs to ground complex location references. *EACL*, 2026 (arXiv:2510.08741).
- ReaGeo: Reasoning-enhanced end-to-end geocoding with LLMs. arXiv:2604.21357, 2026.
- PASC: Pipeline-aware conformal prediction with joint coverage guarantees for multi-stage NLP and LLM pipelines. arXiv:2605.18812, 2026.
- AddrKG-LLM: knowledge-graph-aware contrastive learning and constrained on-premise LLM inference for patient address parsing. *Scientific Reports*, 2026 (s41598-026-39348-z).
- S. Wang, J. Feng, T. Liu, D. Pei and Y. Li. Mitigating geospatial knowledge hallucination in large language models: Benchmarking and dynamic factuality aligning. *Findings of EMNLP*, 2025.
- V. Vovk, A. Gammerman and G. Shafer. *Algorithmic Learning in a Random World*. Springer, 2005.
- Geolonia. normalize-japanese-addresses. https://github.com/geolonia/normalize-japanese-addresses
- T. Sagara. jageocoder. https://github.com/t-sagara/jageocoder
