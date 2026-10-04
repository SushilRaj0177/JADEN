# JADEN — Japanese Address Data Engineering & Normalization Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Typing: PEP 561](https://img.shields.io/badge/typing-PEP%20561-green.svg)](https://peps.python.org/pep-0561/)

**JADEN** is a high-performance, deterministic Python engine for Japanese address canonicalization, administrative boundary disambiguation, and statutory classification. It resolves the dual-nature complexity of Japanese addressing without external black-box APIs, operating completely offline at **~3,000 addresses/second** across diverse, uninterned real-world corpora with a tiny **3.6 MB memory footprint**.

*(日本語のドキュメントは [README_JP.md](README_JP.md) をご覧ください。)*

---

## 1. The Core Engineering Challenge

Unlike Western street-grid systems (e.g., `123 Main St, Suite 400`), Japanese addressing is fundamentally topological, cadastral, and historical. A production normalization engine must resolve four distinct layers of complexity:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   JAPANESE ADDRESS DUAL ARCHITECTURE                     │
├─────────────────────────────────────┬────────────────────────────────────┤
│ 住居表示 (Residential Indication)   │ 地番区域 (Land Lot / Cadastral)     │
│ (Urban: Tokyo 23 wards, Osaka, etc.)│ (Rural / Unconsolidated Urban)     │
├─────────────────────────────────────┼────────────────────────────────────┤
│ 都道府県 ──> 市区町村 ──> 町名      │ 都道府県 ──> 市区町村 ──> 大字     │
│ ──> 街区符号 (番)                   │ ──> 字 / 小字                      │
│ ──> 住居番号 (号)                   │ ──> 地番 (番地) ──> 支号 (枝番)    │
└─────────────────────────────────────┴────────────────────────────────────┘
```

1. **Dual Statutory Regimes:**
   * **Gaiku-hoshiki (街区方式):** Established by the *Act on Indication of Residential Address (住居表示に関する法律, Act No. 119 of 1962)*. Organized into blocks (*ban* / 番) and house numbers (*go* / 号).
   * **Chiban (地番区域):** Governed by the *Real Property Registration Act (不動産登記法, Act No. 123 of 2004)* and the Civil Code. Organized into land lots (*banchi* / 番地) and branch lots (*edaban* / 枝番), often structured under *Oaza* (大字) and *Koaza* (字 / 小字).
2. **Conventional Navigation Schemes:**
   * **Kyoto Tōri-mei (通り名):** Relative street-intersection navigation (`上る` / `下る` / `東入` / `西入`). Example: `京都府中京区御池通東洞院東入笹屋町436`. Crucially, Kyoto streets frequently embed cardinal characters (`東洞院通`, `西洞院通`, `下立売通`, `上長者町通`).
   * **Hokkaido Cardinal Grids (条・丁目):** Sapporo-style grid coordinates (`北1条西2丁目`).
3. **The CJK Dash Jungle & Proper Noun Preservation:**
   * Over 11 Unicode code points represent dashes in Japanese text (`-`, `－`, `‐`, `―`, `ー`, `～`, etc.).
   * The Katakana prolonged sound mark (`ー` / `U+30FC`) is simultaneously a delimiter between block numbers (`1ー2ー3` -> `1-2-3`) and a crucial character in proper nouns (`タワー`, `センター`).
   * Proper place names embed Kanji numbers (`六本木`, `八王子`, `十条`, `四日市`, `三番町`, `一番街`, `麻布十番`). Blind regex substitution corrupts proper names into `1番 街` or `麻布10番`.
4. **Multi-Jurisdiction Collisions on Omitted Prefectures:**
   * 38 municipal and ward names are shared across multiple prefectures. For example, `中央区` exists in Tokyo and 10 designated cities; `府中市` exists in Tokyo and Hiroshima; `伊達市` exists in Hokkaido and Fukushima. A production system must report ambiguity rather than silently guessing Tokyo.

---

## 2. Four-Tier Taxonomy of Truth

To ensure architectural transparency, JADEN categorizes every parsed token and transformation into one of four explicit tiers:

| Tier | Classification | Definition & Examples |
| :--- | :--- | :--- |
| **Tier 1** | **Statutory / Official** | Explicitly defined in Japanese law or national standards: JIS X 0401 (Prefecture codes), JIS X 0402 (Municipality codes), 6-digit Local Government Code with Modulus 11 check digits, *Gaiku* (番), *Jukyo* (号), *Banchi* (番地), *Edaban* (枝番), *Oaza* (大字), *Koaza* (字). |
| **Tier 2** | **Documented Convention** | Officially recognized regional conventions: Kyoto Tōri-mei directional clauses, Hokkaido Jo-Chome grid coordinates, standard postal hyphenation (`6-10-1`). |
| **Tier 3** | **Heuristic Disambiguation** | Inferred transformations: Resolving omitted prefectures, context-aware Chōonpu isolation, separating building and floor suffixes without whitespace. |
| **Tier 4** | **System Artifact** | JADEN-specific conventions: Canonical string formatting, confidence scoring (0.0 to 1.0), serialized JSON schema. |

---

## 3. Architecture & Processing Pipeline

JADEN executes a multi-stage deterministic pipeline:

```
                      Raw Japanese Address Input
                                  │
                                  ▼
   [Stage 1: Context-Aware Sanitizer & Unicode Homogenizer]
   • Unicode NFKC Normalization (UAX #15)
   • Contextual Chōonpu (U+30FC) resolution: converted only between digits,
     strictly preserved in Katakana loanwords (e.g., 'タワー')
   • Unconditional dash unification to ASCII '-'
                                  │
                                  ▼
   [Stage 2: Context-Bounded Kanji Numeral Converter]
   • Converts block numerals ('三丁目' -> '3丁目', '488番地')
   • Context-bounded patterns protect proper nouns ('一番街', '麻布十番', '三番町')
                                  │
                                  ▼
   [Stage 3: Administrative Boundary Resolver (PrefixTrie)]
   • O(L) prefix matching against all 47 Prefectures (JIS X 0401)
   • 1,918 Municipalities & Administrative Wards (JIS X 0402 / MIC)
   • Multi-jurisdiction collision detection on omitted prefectures (中央区, 府中市, 伊達市)
   • Returns is_ambiguous=True with candidate lists when ambiguous
                                  │
                                  ▼
   [Stage 4: Regional Convention Parsers]
   • Kyoto Parser: Thoroughfare-aware intersection parsing without character exclusions,
     handling thoroughfares with cardinal names (東洞院通, 下立売通, 上長者町通)
   • Hokkaido Parser: Extracts cardinal coordinates (北N条西M丁目)
                                  │
                                  ▼
   [Stage 5: Block & Lot Finite-State Machine (BlockFSM)]
   • Segments Oaza (大字) and Koaza (字 / 小字)
   • Explicitly classifies statutory regime: 'gaiku_hoshiki' vs 'chiban' vs 'unspecified'
   • Cadastral addresses map numbers to banchi/edaban; residential map to ban/go
                                  │
                                  ▼
   [Stage 6: Building, Floor & Unit Disentangler]
   • Isolates floor (50F, 3階, B1F, B2F) and unit (301号室, 301) from building names
                                  │
                                  ▼
                 Canonical NormalizedAddress Object
```

---

## 4. Authoritative Standards & Data Provenance

All figures, codes, and schemas bundled in JADEN are verified against official Japanese statutory authorities:

1. **Prefecture Codes (JIS X 0401:1973, revised 2014):**
   * Exactly 47 prefectures (`01` 北海道 to `47` 沖縄県). Verified against official gazettes.
2. **Municipality Codes (JIS X 0402:2020 & MIC Local Government Code):**
   * **Issuing Body:** Ministry of Internal Affairs and Communications (総務省自治行政局)
   * **Official File:** 都道府県コード及び市区町村コード (令和6年1月1日更新 / Jan 1, 2024 update)
   * **Source URL:** `https://www.soumu.go.jp/main_content/000925835.xlsx`
   * **Source SHA256:** `7d04c8a7f6a6e76a7823a0414a8422bf2b26bb6070766971df76eab58ea6ff78`
   * **Bundled Record Count:** Exactly **1,918 verified records**:
     - 47 Prefectures
     - 1,747 Municipalities: 23 Special Wards (東京都特別区), 20 Designated Cities (政令指定都市), 772 Standard Cities (市), 743 Towns (町), 189 Villages (村, including Northern Territories / 北方領土 6村)
     - 171 Administrative Wards (行政区, reflecting the Jan 1, 2024 Hamamatsu City consolidation)
   * **Check Digit Formula:** 100% of bundled codes validate against the official Modulus 11 algorithm:
     $$\text{Sum} = \sum_{i=1}^{5} d_i \times w_i, \quad W = [6, 5, 4, 3, 2]$$
     $$R = \text{Sum} \pmod{11}$$
     $$\text{Check Digit} = \begin{cases} (11 - R) \pmod{10} & \text{if } R \le 1 \\ 11 - R & \text{if } R \ge 2 \end{cases}$$
3. **Statutory Addressing Acts:**
   * *Act on Indication of Residential Address (昭和37年法律第119号)*: Defines urban *Gaiku-hoshiki* (Chome-Ban-Go).
   * *Real Property Registration Act (平成16年法律第123号)*: Governs cadastral *Chiban* (Oaza-Koaza-Banchi-Edaban).
4. **Digital Agency Address Base Registry (アドレス・ベース・レジストリ):**
   * JADEN models ABR statutory taxonomy (Machi-aza, Gaiku, Chiban). Note: JADEN is an offline linguistic engine and intentionally does not bundle the multi-gigabyte spatial polygon GIS shapefiles of the full ABR.

---

## 5. Empirical Benchmarks

Benchmarks are executed using the reproducible suite in `benchmarks/run_benchmark.py`. Measurements reflect actual performance across a **representative 500-address corpus** without synthetic micro-benchmark bias or repeated-string caching.

### Hardware & Runtime Environment
* **OS:** Windows 11 (10.0.26200)
* **CPU:** AMD Ryzen (12 Logical Cores)
* **Python Runtime:** CPython 3.13.14 (64-bit)
* **Memory Footprint:** 3.17 MB baseline heap (full registry + tries), 3.64 MB peak heap during batch execution
* **Corpus Diversity:** 500 unique, uninterned addresses evaluated over 5,000 operations (10 passes)

### Empirical Performance Results

| Evaluation Corpus | Unique Addrs | Operations | Throughput (addr/sec) | Latency P50 | Latency P90 | Latency P99 | Mean Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clean Standard (Gaiku-hoshiki)** | 200 | 2,000 | **2,901.7** | 275.10 μs | 485.50 μs | 861.30 μs | 337.55 μs |
| **Complex Conventional (Kyoto/Hokkaido/Cadastral)** | 150 | 1,500 | **3,487.5** | 233.40 μs | 386.50 μs | 639.50 μs | 280.98 μs |
| **Dirty Real-World (Omitted/Dashes/Buildings)** | 150 | 1,500 | **2,693.1** | 315.45 μs | 534.50 μs | 883.80 μs | 364.96 μs |
| **Aggregate Workload** | **500** | **5,000** | **2,982.7** | **275.10 μs** | **485.50 μs** | **861.30 μs** | **332.81 μs** |

---

## 6. Installation & Usage

### Installation

```bash
# Clone the repository
git clone https://github.com/SushilRaj0177/JADEN.git
cd JADEN

# Install in editable mode
pip install -e .
```

### Python Library API

```python
import jaden

# 1. Real-world urban address with landmark building & floor
res1 = jaden.normalize("東京都港区六本木6-10-1六本木ヒルズ森タワー50F")
print(res1.canonical)
# Output: 東京都港区六本木6丁目10番1号 六本木ヒルズ森タワー 50F
print(res1.components.lg_code)      # '131032' (Minato-ku)
print(res1.components.address_regime) # 'gaiku_hoshiki'

# 2. Rural cadastral lot address (Chiban with Oaza & Koaza)
res2 = jaden.normalize("長野県長野市大字南長野字幅下692-2")
print(res2.components.oaza)          # '南長野'
print(res2.components.koaza)         # '幅下'
print(res2.components.banchi)        # 692
print(res2.components.edaban)        # 2
print(res2.components.address_regime) # 'chiban'

# 3. Kyoto conventional navigation address
res3 = jaden.normalize("京都府中京区御池通東洞院東入笹屋町436")
print(res3.components.kyoto_direction.street_1)  # '御池通'
print(res3.components.kyoto_direction.street_2)  # '東洞院'
print(res3.components.kyoto_direction.direction) # '東入'
print(res3.components.banchi)                    # 436 (cadastral lot)

# 4. Ambiguous omitted prefecture detection
res4 = jaden.normalize("府中市宮西町2-24")
print(res4.components.is_ambiguous)           # True
print(res4.components.ambiguous_candidates)   # ('東京都府中市 (132063)', '広島県府中市 (342084)')
print(res4.confidence_score)                  # 0.50
```

### Command-Line Interface (CLI)

```bash
# Single address normalization (formatted JSON)
jaden "東京都港区六本木6-10-1六本木ヒルズ森タワー50F"

# Canonical string output only
jaden -c "新宿区西新宿2-8-1東京都庁 第一本庁舎"
# Output: 東京都新宿区西新宿2丁目8番1号 東京都庁 第一本庁舎

# Streaming JSON Lines processing via stdin
cat addresses.txt | jaden --jsonl > normalized.jsonl
```

---

## 7. Testing & Quality Assurance

JADEN maintains a 107-test verification suite covering:
* **All 47 Prefectures:** Deep decomposition asserting prefecture, city, ward, town, oaza/koaza, and block numbers across all 47 prefectural administrative centers.
* **19 Adversarial Payloads:** Complete regression validation against proper noun collisions (`一番街`, `麻布十番`, `三番町`), multi-jurisdiction collisions (`中央区`, `府中市`), cardinal Kyoto streets (`東洞院通`, `下立売通`), and foreign/gibberish input rejection.
* **JIS X 0402 Modulus 11 Check Digit Validation:** Algorithmic verification across all codes.

```bash
pytest -v
```

---

## 8. Explicit Boundaries & Limitations

In accordance with our engineering principles, JADEN documents its exact operational boundaries:
1. **No Spatial Polygon GIS Coordinates:** JADEN is an offline linguistic and administrative normalization engine; it does not contain geospatial polygon shapefiles or latitude/longitude geocoding coordinates.
2. **Ambiguous Omitted Jurisdictions:** When a user omits the prefecture and enters a duplicated municipality name (e.g. `中央区`, `府中市`, `伊達市`), JADEN explicitly reports `is_ambiguous=True` and lists candidates rather than silently guessing.
3. **Private Building Records:** Building names and room numbers are parsed using syntactic heuristics (Tier 3), as no statutory national registry of private commercial building names exists.
4. **Cadastral vs. Residential Distinction in Plain Hyphenated Strings:** When an input consists solely of `町名 X-Y` without `丁目`, `大字`, `字`, `番地`, or `号`, JADEN marks `address_regime="unspecified"`, as determining the regime requires local municipal boundary maps.

---

## License

MIT License. Designed and maintained by Sushil Raj.
