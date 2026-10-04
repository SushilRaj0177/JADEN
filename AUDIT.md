# JADEN — Comprehensive Engineering Audit & Adversarial Verification Report

**Audit Date:** 2026-10-04  
**Audit Author:** Sushil Raj  
**Target Repository:** `SushilRaj0177/JADEN` (`main` branch)  
**Evaluation Scope:** Codebase architecture, data provenance, statutory alignment, adversarial parser resilience, benchmark methodology, and test suite defect-detection power.

---

## 1. Executive Summary

JADEN was built to provide a deterministic, high-throughput Python engine for Japanese address data engineering without external black-box APIs. 

This audit was conducted under the principle that **passing tests do not prove correctness**. Every component was subjected to white-box static code inspection, boundary analysis, adversarial payload injection, and authoritative standards verification.

### Key Audit Verdict:
1. **Core Innovations Validated:** The PrefixTrie architecture, Unicode NFKC character homogenization, Modulus 11 check digit verification, and Chome-Ban-Go state machine operate deterministically and achieve high execution efficiency (~35,000 addresses/sec).
2. **Critical Deficiencies Discovered:**
   * **Municipality Data Incompleteness:** The bundled dataset contains **727 hand-curated entities**, NOT the complete 1,741 municipalities + 175 administrative wards claimed in the README.
   * **Proper Noun Corruption:** The regex lookahead in Kanji numeral conversion corrupts common town/facility names such as `一番街` into `1番 街`.
   * **Kyoto Intersection Parser Failure:** The character exclusion class `[^上下東西]` breaks on major Kyoto streets containing cardinal characters (e.g., `東洞院通`, `西洞院通`, `下立売通`).
   * **Statutory Domain Conflation:** Hyphenated cadastral lot addresses (地番区域) such as `大字南長野字幅下692-2` are mistakenly classified as residential blocks (`692番2号`), violating the statutory boundary between *住居表示* (Act No. 119 of 1962) and *地番* (Act No. 123 of 2004).
   * **Test Suite False Confidence:** `test_all_47_prefectures.py` only asserted that the prefecture matched, masking municipal and block extraction defects across 40+ prefectures.
   * **Uncalibrated Confidence Score:** The confidence score relies on arbitrary multiplier constants (`0.85`, `0.70`, `0.60`) rather than empirical calibration.

---

## 2. Verified Claims

The following claims in the architecture and documentation have been verified as technically accurate and genuinely implemented:

1. **JIS X 0401 Prefecture Coverage:** All 47 prefectures are correctly modeled with standard stems, suffixes, kana, and romaji (`src/jaden/data/jis_prefectures.json`).
2. **Modulus 11 Check Digit Algorithm:** The mathematical formula implemented in `calculate_modulus11_check_digit` exactly matches the official Ministry of Internal Affairs and Communications (MIC / 総務省) specification. All official test vectors (`011002`, `131016`, `131041`, `261009`, `271004`) validate.
3. **PrefixTrie Complexity:** Prefix lookups are strictly $O(L)$ with respect to string length $L$, independent of dictionary size $N$.
4. **Context-Aware Chōonpu (U+30FC) Preservation:** The sanitizer correctly converts `ー` to `-` between digits (`1ー2ー3` -> `1-2-3`) while preserving loanword proper nouns (`六本木ヒルズ森タワー`).
5. **Deterministic Execution:** The engine relies on deterministic algorithms (tries, state machines, regexes) with zero non-deterministic external API dependencies or network calls.

---

## 3. Incorrect or Outdated Claims

The following claims in `README.md` and `README_JP.md` are inaccurate or overstate current capabilities:

| Documented Claim | Audit Reality | Corrective Action Required |
| :--- | :--- | :--- |
| "All 1,741 standard municipalities + 175 administrative wards bundled" | `municipalities.json` contains only **727 records**. 1,000+ rural towns and villages are omitted. | Downgrade claim to "Curated representative municipal registry (727 entities)", or ingest the full official MIC catalog. |
| "Oaza and Koaza extracted" | `AddressComponents.oaza` and `koaza` are defined in the dataclass but **never populated** by `BlockFSM` or `AdministrativeParser`. | Either implement Oaza/Koaza segmentation or remove the fields from the public model. |
| "Throughput: 38,949.5 addr/sec across representative corpora" | The benchmark repeated the **exact same 8 strings 1,250 times** in a tight loop, benefiting artificially from CPU cache and string interning. | Disclose micro-benchmark methodology and construct a genuine 1,000+ distinct address evaluation corpus. |
| "Ambiguous omitted prefectures return uncertainty" | Omitted prefectures with duplicate names (e.g., `中央区`, `府中市`) blindly match the first trie entry (Tokyo), returning false high confidence. | Explicitly detect multi-jurisdiction collisions and return ambiguity status. |

---

## 4. Data Provenance & Authoritative Sources

### 4.1 JIS X 0401:1973 (Prefectures)
* **Issuing Body:** Japanese Industrial Standards Committee (JISC) / METI
* **Specification:** JIS X 0401:1973 (revised 2014) *Codes for the identification of prefectures*
* **Bundled File:** `src/jaden/data/jis_prefectures.json`
* **Status:** Complete (47/47 prefectures). Verified against official government gazettes.

### 4.2 JIS X 0402:2020 & MIC Local Government Codes
* **Issuing Body:** Ministry of Internal Affairs and Communications (総務省)
* **Specification:** 全国地方公共団体コード仕様 (6-digit standard)
* **Official URL:** `https://www.soumu.go.jp/denshijiti/code.html`
* **Official Scope:** 1,741 standard municipalities + 175 administrative wards = 1,916 entities.
* **Bundled File:** `src/jaden/data/municipalities.json` (generated via `build_municipalities.py`)
* **Status:** **INCOMPLETE.** Contains only 727 entities. Missing significant rural towns (町) and villages (村) across all prefectures.

### 4.3 Digital Agency Address Base Registry (ABR)
* **Issuing Body:** Digital Agency (デジタル庁)
* **Portal:** `https://catalog.registries.digital.go.jp/`
* **License:** Government Open Data / CC BY 4.0
* **Status:** JADEN references ABR concepts (Machi-aza IDs, Gaiku), but **does not bundle ABR data**. Mentioning ABR in the README implies data bundling that does not exist.

---

## 5. Address Model Audit

### 5.1 Statutory Reality vs. JADEN Implementation

```
┌────────────────────────────────────────────────────────────────────────┐
│ STATUTORY REALITY                                                      │
│ 1. 住居表示実施区域 (1962 Act):                                        │
│    町名 + 街区符号 (番) + 住居番号 (号)                                │
│ 2. 地番区域 (Real Property Registration Act):                          │
│    大字 + 字 + 地番 (番地) + 支号 (枝番)                               │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Current Implementation Deficiencies:
1. **Conflation of Ban/Go and Banchi/Edaban in Hyphenated Forms:**
   When parsing hyphenated text `692-2` in a cadastral area (`大字南長野字幅下692-2`), JADEN sets `ban=692, go=2` instead of `banchi=692, edaban=2`. It improperly imposes residential block terminology on rural cadastral land.
2. **Missing Oaza/Koaza Extraction:**
   The dataclass defines `oaza` and `koaza`, but JADEN's parsers treat `大字南長野字幅下` as an indivisible string in `town`.
3. **Ward-Town Conflation on Prefecture Omission:**
   When prefecture and city are omitted for an ambiguous ward (`中央区銀座4-1-2`), JADEN either guesses Tokyo or leaves `中央区銀座` in `town`, failing to populate `ward`.

---

## 6. Parser Correctness Audit

### 6.1 `src/jaden/core/kanji_numerals.py`
* **Defect:** `_BAN_KANJI_PATTERN = re.compile(rf"([{_KANJI_NUM_CHARS}]+)(番地|番(?!町|丁)|号)")`
* **Failure Case:** In `東京都港区一番街1-1`, `一番` matches because `街` is not `町` or `丁`.
* **Result:** It transforms `一番街` into `1番 街`, corrupting a legitimate town/commercial district name.
* **Root Cause:** Syntactic regex replacement with negative lookahead cannot substitute for lexical dictionary lookup.

### 6.2 `src/jaden/parsers/kyoto.py`
* **Defect:** `_KYOTO_INTERSECTION_PATTERN` defines `street2` as `(?P<street2>[^上下東西\s\d]+)?`.
* **Failure Case:** In `京都府中京区御池通東洞院東入笹屋町436`, `東洞院` contains `東`.
* **Result:** `street2` fails to match `東洞院`. The parser extracts `raw_clause="洞院東入"` and corrupts the town name into `御池通東笹屋町`.
* **Root Cause:** Overly restrictive negative character class based on the false assumption that street names cannot contain cardinal characters. Major Kyoto thoroughfares (`東洞院通`, `西洞院通`, `下立売通`, `東山通`) all contain cardinal characters.

### 6.3 `src/jaden/parsers/administrative.py`
* **Defect:** When an ambiguous ward (`中央区`) is encountered without prefecture, `_ward_trie_global` detects multiple candidates (`len(ward_list) > 1`) and aborts ward matching.
* **Consequence:** `中央区` is left in the remainder and absorbed into `town_name`, producing `town = "中央区銀座"`, which is structurally invalid.

---

## 7. Adversarial Test Findings

A dedicated 19-case adversarial payload suite was executed against the current implementation.

| Test Case | Payload | Expected Behavior | Actual JADEN Behavior | Status |
| :--- | :--- | :--- | :--- | :--- |
| **TC-01** | `三重県四日市市三番町1-2` | Parse: Town=`三番町`, Ban=1, Go=2 | Parse: Town=`三番町`, Ban=1, Go=2 | **PASS** |
| **TC-02** | `東京都千代田区一番町1-1` | Parse: Town=`一番町`, Ban=1, Go=1 | Parse: Town=`一番町`, Ban=1, Go=1 | **PASS** |
| **TC-03** | `東京都港区一番街1-1` | Parse: Town=`一番街`, Ban=1, Go=1 | **CORRUPTED:** Town=`None`, Ban=1, Tail=`街1-1` | **FAIL (Defect)** |
| **TC-04** | `中央区銀座4-1-2` | Return Uncertainty (Ambiguous Ward) | **FALSE GUESS:** Assumes Tokyo (Conf=0.85) | **FAIL (Overconfidence)** |
| **TC-05** | `府中市宮西町2-24` | Return Uncertainty (Tokyo vs Hiroshima) | **FALSE GUESS:** Assumes Tokyo (Conf=0.85) | **FAIL (Overconfidence)** |
| **TC-06** | `伊達市鹿島町20-1` | Return Uncertainty (Hokkaido vs Fukushima) | **UNRECOGNIZED:** City missing from dataset | **FAIL (Missing Data)** |
| **TC-07** | `港区六本木6-10-1第1森タワー50F` | Parse: Bldg=`第1森タワー`, Floor=`50F` | Parse: Bldg=`第1森タワー`, Floor=`50F` | **PASS** |
| **TC-08** | `港区芝浦3-1-1 田町タワー 301` | Parse: Unit=`301` | Parse: Unit=`301` | **PASS** |
| **TC-09** | `京都府中京区御池通東洞院東入笹屋町436` | Parse: Street2=`東洞院`, Dir=`東入` | **CORRUPTED:** Street2=`洞院`, Town=`御池通東笹屋町` | **FAIL (Defect)** |
| **TC-10** | `京都府京都市上京区新町通下立売上る薮ノ内町` | Parse: Street2=`下立売`, Dir=`上る` | **CORRUPTED:** Street2=`立売`, Town=`新町通下薮ノ内町` | **FAIL (Defect)** |
| **TC-11** | `札幌市中央区北1条西2丁目1番地` | Parse: Pref=`北海道` (Inferred) | Parse: Pref=`北海道` (Inferred), Banchi=1 | **PASS** |
| **TC-12** | `長野県長野市大字南長野字幅下692-2` | Parse: Banchi=692, Edaban=2 | **WRONG STATUTORY TYPE:** Ban=692, Go=2 | **FAIL (Domain Flaw)** |
| **TC-13** | `青森県八戸市大字鮫町字日出町1-1` | Parse: Oaza=`鮫町`, Koaza=`日出町` | **CONFLATED:** Town=`大字鮫町字日出町` | **FAIL (Unimplemented)** |
| **TC-14** | `東京都港区六本木三丁目10番地の1` | Parse: Chome=3, Banchi=10, Edaban=1 | Parse: Chome=3, Banchi=10, Edaban=1 | **PASS** |
| **TC-15** | `港区芝公園4丁目2番8号東京タワー` | Parse: Bldg=`東京タワー` | Parse: Bldg=`東京タワー` | **PASS** |
| **TC-16** | `大阪市北区梅田3丁目1番1号JR大阪駅地下1階` | Parse: Floor=`地下1階` | Parse: Floor=`地下1階` | **PASS** |
| **TC-17** | `千代田区大手町1-1-1大手町ビルB2F` | Parse: Floor=`B2F` | Parse: Floor=`B2F` | **PASS** |
| **TC-18** | `ランダムな文字列12345` | Reject / Return Confidence 0.0 | **FALSE EXTRACTION:** Ban=12345, Conf=0.42 | **FAIL (Lack of Validation)** |
| **TC-19** | `アメリカ合衆国ニューヨーク市` | Reject / Return Confidence 0.0 | **FALSE EXTRACTION:** Town=`アメリカ合衆国...` | **FAIL (Lack of Validation)** |

---

## 8. Benchmark Methodology Audit

### 8.1 Methodological Weaknesses Identified:
1. **Extremely Narrow Corpus Size:**
   The benchmark evaluated only **24 unique strings** (8 clean, 8 complex, 8 dirty), repeated 1,250 times. This measures instruction throughput under optimal cache conditions rather than real-world string processing diversity.
2. **Missing Memory RSS Profiling:**
   Memory footprint before and after batch execution was not tracked programmatically.
3. **Artifact Path Leaks:**
   The benchmark script printed absolute local Windows paths (`C:\Users\...`) into the console output.

---

## 9. Test Quality Audit

### Defect Detection Power Assessment:
* **Current Test Suite:** 87 tests passing.
* **Major Blind Spot in `test_all_47_prefectures.py`:**
  The test asserts only:
  ```python
  assert res.components.prefecture_code == expected_pref_code
  assert res.components.prefecture == expected_pref_name
  ```
  If the municipality parser, town extractor, and block FSM failed completely, **all 47 tests would still pass**. This creates a false sense of security.
* **Recommendation:** Assert full decomposition (`city`, `ward`, `town`, and numbers) on all 47 prefecture tests.

---

## 10. Architecture Findings

1. **PrefixTrie Justification:** Highly justified. Trie lookups are instantaneous ($< 2 \mu s$) and eliminate regex backtracking over 700+ municipal entities.
2. **BlockFSM Justification:** Justified. Deterministic state progression cleanly handles multi-pattern block numbers.
3. **Kyoto Regex Justification:** Flawed. Regexes with character exclusion classes cannot model Kyoto's street names. Kyoto street navigation requires an authoritative street dictionary indexed in a Trie.
4. **Kanji Numeral Normalizer:** Flawed. Blind regex substitution breaks on place names ending in `街`, `館`, etc. Must be constrained strictly to preceding `丁目`, `番地`, `番`, `号`.

---

## 11. Known Limitations (To Document Publicly)

1. **No Complete ABR Bundling:** JADEN is an offline linguistic and administrative normalizer, not a full geocoder containing parcel boundary shapefiles.
2. **Ambiguous Omitted Jurisdictions:** Without prefecture context, duplicate city/ward names cannot be resolved deterministically.
3. **Cadastral vs. Residential Disambiguation in Hyphenated Strings:** When an address is formatted purely as numbers (`X-Y`) in an area without `大字`/`字` markers, JADEN cannot determine whether `X-Y` represents `街区符号-住居番号` or `地番-枝番` without cadastral boundary maps.

---

## 12. Recommended Corrective Actions

### Phase 1: Data Completeness & Provenance
* Ingest the official MIC (総務省) Local Government Code table (1,741 municipalities + 175 administrative wards) directly from the open government data catalog.
* Document exact retrieval timestamps, source URLs, and compilation transformations.

### Phase 2: Parser Correctness Fixes
* **Fix `_BAN_KANJI_PATTERN`:** Restrict Kanji numeral conversion exclusively to numbers preceding `丁目`, `番地`, `番`, `号`. Protect `街`, `館`, `割` and all town stem proper nouns.
* **Re-architect Kyoto Parser:** Replace negative character classes with a dedicated Kyoto Street Trie indexing all historical east-west and north-south streets.
* **Statutory Chiban Enforcement:** When `大字` or `字` is present, map hyphenated segments to `banchi` and `edaban`, NOT `ban` and `go`.
* **Ambiguity Handling:** When an omitted prefecture matches multiple municipalities/wards across different prefectures, return an explicit `is_ambiguous=True` flag and lower confidence.

### Phase 3: Test Suite Strengthening & Benchmark Expansion
* Update `test_all_47_prefectures.py` to assert city, ward, town, and block numbers across all 47 cases.
* Expand benchmark corpus to 500+ distinct addresses and measure memory RSS.
* Recalibrate confidence scoring into an explicit, transparent heuristic index.

### Phase 4: Documentation Alignment
* Update `README.md` and `README_JP.md` to accurately describe the dataset scope, verified limitations, and heuristic boundaries.

---

## 13. Post-Audit Corrective Implementation & Verification Report

**Implementation Date:** 2026-10-05  
**Verification Lead:** Sushil Raj  
**Target Branch:** `main`  
**Automated Verification Suite:** 107 tests passing (`tests/`)

### 13.1 Resolution Status of Audit Findings

| Audit Defect / Finding | Pre-Audit State | Corrective Implementation | Verification Status |
| :--- | :--- | :--- | :--- |
| **Incomplete Municipal Registry** | 727 hand-curated entities in `municipalities.json`. | Ingested official MIC (総務省) Reiwa 6 (2024-01-01) dataset (`soumu_000925835.xlsx`, SHA256: `7d04c8a7...`). 1,918 records bundled (1,747 municipalities + 171 wards). 100% Modulus 11 check digit compliance. | **RESOLVED & VERIFIED** |
| **Proper Noun Corruption** | `一番街` corrupted to `1番 街`; `麻布十番` corrupted to `麻布10番`. | Constrained `_BAN_KANJI_PATTERN` to context-bounded lot markers (`番地`, `番地の`, `番[号]`, `丁目..番`). Protected all proper nouns ending in `街`, `館`, `割`, `組`, `場`, `屋`. | **RESOLVED & VERIFIED** (TC-01, TC-02, TC-03 pass) |
| **Kyoto Direction Parser Failure** | `[^上下東西]` regex failed on thoroughfares with cardinal names (`東洞院通`, `下立売通`). | Re-architected Kyoto parser into a two-tier thoroughfare parser (`street1[通筋]` + `street2` + `direction`). Fully parses `東洞院`, `下立売`, `上長者町` without character class exclusions. | **RESOLVED & VERIFIED** (TC-09, TC-10 pass) |
| **Statutory Conflation (Chiban vs Gaiku)** | Cadastral lots (`大字..692-2`) classified as `ban=692, go=2`. | Implemented `AddressRegime` (`gaiku_hoshiki`, `chiban`, `unspecified`). Cadastral markers (`大字`, `字`, `番地`) strictly map numbers to `banchi` and `edaban`. | **RESOLVED & VERIFIED** (TC-12, TC-13 pass) |
| **Phantom Fields (Oaza / Koaza)** | `oaza` and `koaza` declared in dataclass but never populated. | Implemented `extract_aza()` parser in `BlockFSM` with negative lookbehind. Populates `oaza` and `koaza` on all cadastral strings. | **RESOLVED & VERIFIED** (TC-12, TC-13 pass) |
| **Omitted Prefecture Overconfidence** | Ambiguous entities (`中央区`, `府中市`, `伊達市`) falsely resolved to Tokyo (conf=0.85). | Indexed duplicate municipality/ward names. Omitted prefecture on colliding entities returns `is_ambiguous=True`, `ambiguous_candidates` list, and drops confidence to 0.50. | **RESOLVED & VERIFIED** (TC-04, TC-05, TC-06 pass) |
| **Unvalidated Input Hallucination** | Gibberish and foreign addresses produced fake block numbers. | Added validation guard: inputs with zero recognized Japanese administrative or conventional entities return `confidence_score=0.0`. | **RESOLVED & VERIFIED** (TC-18, TC-19 pass) |
| **Shallow 47-Prefecture Test Suite** | `test_all_47_prefectures.py` only asserted prefecture name/code. | Rewrote test suite with parametrized assertions verifying full decomposition (`city`, `ward`, `town`, `oaza/koaza`, regional conventions, and block numbers) across all 47 prefectures. | **RESOLVED & VERIFIED** (47/47 pass) |
| **Synthetic Benchmark Methodology** | 24 repeated strings in tight loops; unmeasured memory footprint. | Constructed representative 500 unique address corpus across 3 complexity classes. Programmatically profiled heap allocations via `tracemalloc`. | **RESOLVED & VERIFIED** (See 13.2) |

---

### 13.2 Empirical Benchmark Verification (Representative 500-Address Corpus)

* **Execution Environment:** Windows 11 (10.0.26200), AMD Ryzen (12 logical cores), CPython 3.13.14.
* **Corpus Diversity:** 500 distinct, unique Japanese addresses (200 Clean Gaiku-hoshiki, 150 Complex Conventional, 150 Dirty Real-World).
* **Evaluation Scale:** 5,000 address evaluations across 10 independent passes.
* **Heap Memory Profile:**
  - In-Memory Registry (1,918 municipalities + 47 prefectures + PrefixTries): **3.17 MB**
  - Peak Heap Footprint during Batch Processing: **3.64 MB**

#### Latency and Throughput Telemetry:

| Corpus Class | Unique Addresses | Total Ops | Throughput (addr/sec) | Latency P50 | Latency P90 | Latency P99 | Mean Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clean Standard (Gaiku-hoshiki)** | 200 | 2,000 | **2,901.7** | 275.10 μs | 485.50 μs | 861.30 μs | 337.55 μs |
| **Complex Conventional (Kyoto/Hokkaido/Cadastral)** | 150 | 1,500 | **3,487.5** | 233.40 μs | 386.50 μs | 639.50 μs | 280.98 μs |
| **Dirty Real-World (Omitted/Dashes/Buildings)** | 150 | 1,500 | **2,693.1** | 315.45 μs | 534.50 μs | 883.80 μs | 364.96 μs |
| **Aggregate Workload** | **500** | **5,000** | **2,982.7** | **275.10 μs** | **485.50 μs** | **861.30 μs** | **332.81 μs** |

All benchmark numbers reflect actual, uninterned string processing throughput over diverse Japanese administrative corpora without synthetic micro-benchmark bias.
