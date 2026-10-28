# Knowing When an Address Is Ambiguous: Gazetteer-Grounded Resolution of Japanese Addresses

**Draft — Sushil Raj**

> Status: working draft. All numbers in Sections 5–6 are produced by `benchmarks/jabench/evaluate.py` at the commit this file is in. The comparison with other open-source tools (Section 6.4) is pending; the runners are in `benchmarks/jabench/baselines/`.

## Abstract

Japanese addresses are hard to resolve automatically: municipality names repeat across the country (11 wards are called 中央区), many municipality names are also town names elsewhere (栄町, 錦町), block numbers mean different things in residential (住居表示) and cadastral (地番) areas, and the same place is written in many ways (霞ヶ関 / 霞が関, 四丁目 / 4-, の / -, romaji). Tools that always return an answer turn these ambiguities into silent errors. We present JADEN, an offline, deterministic resolver that grounds every decision in two official open datasets — MLIT's list of all 191,100 registered towns and 丁目, and Japan Post's postal-code list — and returns *ambiguous, with candidates* whenever the data do not single out one place. To measure this, we build JA-AddrBench from 4,700 real addresses whose municipality and location come from an independent source (MLIT school data), with label-preserving variants (no prefecture, municipality omitted, formatting noise, romaji) and inputs that must be rejected (wrong prefecture, nonexistent 丁目, place names that are not addresses). On 18,100 inputs that keep the municipality, JADEN is correct on 18,099 and wrong on none; with the municipality removed, it resolves 50.4% and is wrong on 1 of 4,700, returning candidate lists that contain the right municipality 98.6% of the time. It rejects all 4,700 wrong-prefecture inputs and 4,698 of 4,700 school names. Without the gazetteer, the same parser accepts 58% of school names and every nonexistent 丁目.

## 1. Introduction

Address resolution is usually evaluated by how often a system returns the right answer. For Japanese addresses this hides the important failure: an answer that is confidently wrong. `港区芝公園4-2-8` is a valid address, but 港区 exists in Tokyo, Nagoya and Osaka; a resolver that picks the first match is right one time in three for inputs like this, and gives no signal when it is wrong.

The information needed to do better is public. MLIT publishes every registered town (大字・町丁目) with a representative point; Japan Post publishes every postal code with readings and romanization. Only Tokyo's 港区 has a 芝公園, so the address is not ambiguous at all — once one checks.

This paper makes three contributions:

1. **A resolution procedure that abstains by construction** (Section 3). Candidate municipalities are narrowed only by facts recorded in official data (the town exists there, the 丁目 exists, the postal code belongs there). When more than one candidate survives, the output is AMBIGUOUS with the surviving list; nothing is ranked or guessed.
2. **Registry-guided reading of the address structure** (Section 3.3). Whether `6-10` means 6丁目10番 or 6番10号, whether `20-113-1` is a 丁目 or a three-part lot number, and whether `栄町7-7` names a municipality or a town are decided by how the town is registered, not by surface patterns.
3. **JA-AddrBench** (Section 4), a reproducible benchmark with independent ground truth that scores wrong answers and false accepts separately from coverage, so that abstention is rewarded only when it is correct to abstain.

JADEN is open source (MIT), has no runtime dependencies, and runs offline.

## 2. Background

**Administrative levels.** An address names a prefecture (47), a municipality (1,747 cities, towns, villages and Tokyo special wards, plus 171 wards of the 20 designated cities), a town (町・大字, often divided into 丁目), and block numbers. Municipal codes (全国地方公共団体コード) are 6 digits with a modulus-11 check digit.

**Two numbering systems.** Under the 1962 Act on Indication of Residential Addresses (住居表示), urban towns are divided into 丁目, blocks (番) and house numbers (号). Elsewhere, addresses use cadastral lot numbers (地番, 番地) with branch numbers (枝番), sometimes grouped under 大字 and 字. Both are written with hyphens in practice, so `1-2-3` is 1丁目2番3号 in one town and a three-part lot number in another (e.g. Iwate's 地割).

**Regional conventions.** Kyoto addresses often add a street-intersection clause (寺町通御池上る); Sapporo and other Hokkaido cities use grid towns (北1条西2丁目).

**Name collisions.** 37 municipal names repeat across prefectures; many municipality names are also town names in other municipalities (`栄町` is a town in Chiba and a town name in dozens of cities).

## 3. Method

### 3.1 Data

| Source | Content | Records | Terms |
|---|---|---:|---|
| MIC 都道府県コード及び市区町村コード (2024-01-01) | municipalities and codes | 1,918 | MIC terms |
| MLIT 大字・町丁目レベル位置参照情報 19.0b (2025) | towns and 丁目 with representative points | 191,100 | free use with attribution |
| Japan Post 郵便番号データ (UTF-8 and romaji) | postal codes, readings, romanization, 丁目 flag | 124,526 | copyright not claimed |
| MLIT 街区レベル位置参照情報 24.0a (optional) | block points, 住居表示 / 地番 flag | 17.7 M | free use with attribution |

A build script downloads the sources, records each file's SHA256, and compiles them into compact tables bundled with the package (7 MB wheel). Every town name is reduced to a matching key that folds spelling variants found in practice: ヶ/ケ/が/ヵ, の/ノ, kanji and Arabic numerals, traditional kanji, an optional 大字/字 prefix, and 通り/通. All municipality codes in the MLIT and Japan Post data join to the MIC list.

### 3.2 Pipeline

1. Unicode normalization, dash and postal-code handling, kanji numerals in block positions, の between block numbers.
2. Prefecture and municipality matching with prefix tries; a written prefecture that contradicts the municipality is rejected; an omitted prefecture with a repeated name yields a candidate set.
3. Kyoto intersection and Hokkaido grid clauses.
4. A block FSM that separates the town text from the numbers and the building.
5. **Gazetteer resolution** (3.3).
6. Validation: ACCEPTED, AMBIGUOUS, MALFORMED (contradiction or nonexistent unit), or UNSUPPORTED (not an address).

### 3.3 Gazetteer resolution

Let *C* be the candidate municipalities: the matched one, the ambiguous set, all municipalities of a written prefecture when no municipality was written, the wards of a designated city, or — when nothing administrative was written — every municipality that registers the town. For each *c* ∈ *C* we check:

- **town**: the longest registered town whose key is a prefix of the town text (a partial match counts only if the rest is a 字/小字 or a lot-series prefix such as 甲 or イ), with registered spelling variants as alternatives (伊勢宮 → 伊勢宮町; つつじが丘南 1 → つつじが丘南一番町; 本町 6 → 本町六の 1丁目);
- **丁目**: if the 丁目 was written, or the town is divided into 丁目 throughout, that it is one of the town's registered 丁目;
- **postal code**: if one was written, that it belongs to *c*.

If exactly one candidate passes, it is chosen; whole-name matches beat partial ones. Otherwise the result is AMBIGUOUS with the passing candidates (or all of *C* if none passes). A chosen municipality is never preferred for being larger, more common, or first.

Two cases need extra care:

- **Municipality or town?** Without a prefecture, `栄町7-7` may be the municipality 栄町 (Chiba) or a town called 栄町 in another city. If the name is also a registered town elsewhere, both readings are kept; the town reading wins only when it is registered and the municipality reading is not (`松川町沼袋…` is a town in 福島市, not the municipality 松川町).
- **Contradicted prefecture.** If the town is not in the chosen municipality but exists in a municipality of the same name in another prefecture (`静岡県中央区日本橋兜町` → 東京都中央区), the address is MALFORMED.

**Reading the numbers.** The matched town decides the structure: in a town registered entirely as 丁目 (六本木), `6-10` is 6丁目10番 and `6` is 6丁目; in a registered 大字, a pair is 番地と枝番; in a town without 丁目, a triple is kept as a lot number (`西見前20-113-1`); with block data installed, the block's 住居表示 flag fixes the regime.

**Outputs.** The registered spelling, the MLIT town ID, the Japan Post postal code (filled in when the town has exactly one), the katakana reading, an English-order line in Japan Post romanization, and the representative point of the block, 丁目 or town.

### 3.4 Romanized input

Latin-script input is folded to a key (macrons, doubled vowels, ou, m/n before labials, English suffixes City/Ward/Town/Village/Prefecture) and matched against Japan Post's romanization of prefectures, municipalities (with and without suffix, including the wards of each designated city and Tokyo's wards as "City") and towns. The segment carrying the house numbers is always read as the town, so towns named like wards or cities (Minami, Chuo, Kochi) are not mistaken for them. A bare word is never enough to choose a municipality ("USA" romanizes like 宇佐市). The Japanese string is then resolved by the same pipeline.

## 4. JA-AddrBench

**Source.** MLIT 国土数値情報 学校データ P29 (2023, CC BY 4.0): 56,807 schools, each with its address as published, the municipality code of its site, and a surveyed point. We drop records whose code is no longer a municipality (411, all in Hamamatsu's wards abolished on 2024-01-01), whose address does not start with its own prefecture and municipality or has no number after it (269), and duplicate addresses (3,263), then sample 100 per prefecture with a fixed seed (4,700 addresses).

**Independence.** The gold municipality and point come from P29, not from MIC, MLIT town data or Japan Post. The only use of Japan Post in construction is (a) its 丁目 flag, to decide where a "99丁目" certainly does not exist and where a kanji 丁目 rewrite preserves meaning, and (b) its romanization, to write the romaji variant the way it appears on international mail.

**Variants.** Valid, with the gold municipality unchanged: `original`; `no_pref`; `town_only` (prefecture and municipality removed); `noisy` (full-width digits, other dashes, kanji 丁目 with 番/号, の delimiters, a space after the municipality); `romaji` (English order, Japan Post romanization; 3,657 addresses whose town is in the romaji list). Invalid: `wrong_pref` (another prefecture substituted), `chome_99` (99丁目 in a town divided into 丁目; 1,026), `non_address` (the school's name).

**Metrics.** A system *answers* when it commits to one municipality. For valid inputs: accuracy (correct answers / items), coverage, precision, and the wrong-answer count. For invalid inputs: false accepts. When a system abstains with candidates, we report whether the gold municipality is among them. For correctly resolved items, the distance to the surveyed point.

## 5. Results

**Table 1. Valid inputs.**

| Variant | n | JADEN accuracy | JADEN wrong | Parser-only accuracy | Parser-only wrong |
|---|---:|---:|---:|---:|---:|
| original | 4,700 | 100.0% | 0 | 100.0% | 0 |
| no_pref | 4,700 | 99.98% | 0 | 99.7% | 0 |
| noisy | 4,700 | 100.0% | 0 | 100.0% | 0 |
| romaji | 3,657 | 100.0% | 0 | 0.0% | 0 |
| town_only | 4,700 | 50.4% | 1 | 0.1% | 100 |

Parser-only is the same engine with the gazetteer disabled (JADEN v0.1 behaviour).

**Table 2. Inputs that must be rejected (false accepts).**

| Variant | n | JADEN | Parser-only |
|---|---:|---:|---:|
| wrong_pref | 4,700 | 0 | 0 |
| chome_99 | 1,026 | 74 | 1,026 |
| non_address | 4,700 | 2 | 2,723 |

**Abstention.** On `town_only`, JADEN abstains on 2,328 inputs; 2,125 carry a candidate list, which contains the gold municipality in 98.6% of cases (median list size 8). The remainder are towns registered in more places than a list is useful for, or not registered at all.

**Geocoding.** For correctly resolved `original` inputs, the median distance from JADEN's point to the surveyed school point is 360 m with the bundled 丁目/town points (79.3% within 1 km) and 71 m with block-level data (89.0% within 1 km). School sites are large, so this distance includes the site extent.

**Throughput.** On the `original` inputs, about 11,500 addresses per second on one core with town verification and 18,800 in parser-only mode (same machine); the gazetteer uses about 90 MB of memory and 0.4 s to load.

## 6. Analysis

### 6.1 What the gazetteer adds

Comparing the two systems isolates the gazetteer's effect: it changes no correct answer on full addresses, makes romaji input possible, turns `town_only` from almost always wrong-or-silent (100 wrong answers, 0.1% correct) into 50.4% correct with 1 wrong answer, and removes almost all false accepts.

### 6.2 Remaining errors

- **The one wrong answer** (`小俣町3-50`): the school is in 奄美市名瀬小俣町; with no municipality written, the only registered town matching `小俣町` exactly is in 足利市. Matching would need suffix search over registered names, which would also make many other inputs ambiguous.
- **74 chome_99 accepts**: all are towns that MLIT records as only partly divided into 丁目 (some areas still use lot numbers). There, `99-x-y` is a valid lot-number reading, so the gold label is itself uncertain; a stricter reading would reject real addresses such as `岐阜市御望971-1-2`.
- **2 non_address accepts**: `向日市立第4向陽小学校` and `…第5…` contain a digit that reads as a block number.
- **One no_pref abstention**: `中央区明石町10-1`, where two 中央区 register 明石町.
- **Coverage gaps**: 1.6% of addresses use a town missing from the MLIT list; the Japan Post list covers half of these, leaving 0.8% verified only at the municipality level.

### 6.3 Design lessons

1. *Abstention has to be designed into the search, not added as a threshold.* Every rule that narrows candidates states a fact that can be checked in the data; ties stay ties.
2. *Structure depends on the town.* About 1% of real addresses (mostly Iwate's 地割) were misread as 丁目 by a pattern-based parser until the town's registered structure was consulted.
3. *Spelling variants must widen, not narrow.* Treating 伊勢宮 as possibly 伊勢宮町 adds candidates, which is what keeps town-only resolution from claiming false uniqueness.

### 6.4 Comparison with other tools (pending)

Runners for @geolonia/normalize-japanese-addresses (3.1.3) and jageocoder (2.2, dictionary gaiku_all_v22) are provided. Neither reports ambiguity, so every returned municipality counts as an answer; the comparison will show how often each commits to a wrong municipality on `town_only` and how often each accepts invalid inputs.

## 7. Limitations

The benchmark addresses are schools, which are well-registered public facilities; residential addresses with building names and room numbers are not covered. Town lists lag municipal changes (data as of 2024–2025). Representative points are not rooftop coordinates. The method resolves the municipality and town; it does not verify house numbers beyond MLIT's block list.

## 8. Reproducibility

```bash
pip install .
python benchmarks/jabench/build_benchmark.py
python benchmarks/jabench/evaluate.py
jaden data fetch-blocks $(seq 1 47)        # optional: block-level points
python benchmarks/jabench/evaluate.py --systems jaden+blocks --blocks-dir ~/.local/share/jaden/blocks
```

Source data URLs and SHA256 digests are recorded in `src/jaden/data/gazetteer_provenance.json` and `benchmarks/jabench/jabench_meta.json`.

## Data attribution

- 「大字・町丁目レベル位置参照情報 国土交通省」2025年版 (19.0b) を加工して作成
- 「街区レベル位置参照情報 国土交通省」24.0a を加工して作成
- 「国土数値情報（学校データ）」（国土交通省）（令和5年度）を加工して作成 — CC BY 4.0
- 郵便番号データ（日本郵便株式会社）
- 都道府県コード及び市区町村コード（総務省）

## References

- C. K. Chow. On optimum recognition error and reject tradeoff. *IEEE Transactions on Information Theory*, 16(1):41–46, 1970.
- R. El-Yaniv and Y. Wiener. On the foundations of noise-free selective classification. *Journal of Machine Learning Research*, 11:1605–1641, 2010.
- Y. Geifman and R. El-Yaniv. Selective classification for deep neural networks. *Advances in Neural Information Processing Systems*, 2017.
- Geolonia. normalize-japanese-addresses. https://github.com/geolonia/normalize-japanese-addresses
- T. Sagara. jageocoder. https://github.com/t-sagara/jageocoder
- A. Barrentine. libpostal. https://github.com/openvenues/libpostal
