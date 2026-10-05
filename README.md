# JADEN — Japanese Address Data Engineering & Normalization Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Typing: PEP 561](https://img.shields.io/badge/typing-PEP%20561-green.svg)](https://peps.python.org/pep-0561/)

**JADEN** is a deterministic Python engine and CLI for Japanese address canonicalization, structured decomposition, statutory validation, and optional geospatial resolution.

Operating completely offline at **~30,000 addresses/second** with a lean **4.28 MB memory footprint** (4.48 MB peak heap during batch execution), JADEN resolves the real-world complexity of Japanese addressing without external black-box APIs, heuristic hallucinations, or mandatory cloud dependencies.

*(日本語のドキュメントは [README_JP.md](README_JP.md) をご覧ください。)*

---

## 1. Overview & The Core Engineering Challenge

### What JADEN Is & What It Solves
Unlike Western street-grid systems (e.g., `123 Main St, Suite 400`), Japanese addressing is fundamentally topological, cadastral, and historical. Standardizing raw Japanese addresses is notoriously difficult:
- **Two competing statutory regimes:** Urban residential block indications (*Gaiku-hoshiki* / 住居表示) vs. rural and unadjusted land-lot numbers (*Chiban* / 地番区域).
- **Regional navigation conventions:** Kyoto street-intersection clauses (*Tōri-mei* / 通り名) and Hokkaido cardinal coordinate grids (条・丁目).
- **Proper noun Kanji numeral collisions:** Place names embedding numbers (`一番街`, `麻布十番`, `六本木`, `八王子`) that naive tokenizers mistakenly convert into block numbers.
- **Omitted-prefecture municipal collisions:** 37 municipality and ward names shared across multiple prefectures (`府中市`, `中央区`, `伊達市`), plus intra-prefecture duplicate ward/town jurisdictions (`南区`, `緑区` in Kanagawa; `北区`, `西区` in Osaka; `泊村` in Hokkaido), which commercial engines often silently misassign.

JADEN parses raw address text into a granular Abstract Syntax Tree (`AddressComponents`), canonicalizing notation, validating against official government registries, and offering optional coordinate resolution.

### What JADEN Can Do
- **Deterministic Canonicalization & Normalization:** Standardizes Unicode variations (NFKC, 11+ dash forms including box dashes and small hyphens, context-aware Katakana prolonged sound marks, embedded newline/CR collapse, postal code prefix stripping) and formats clean, canonical address strings.
- **Granular Syntactic AST Parsing:** Decomposes inputs into prefecture, county, city/ward, oaza/koaza, town, chome, ban, go, banchi, edaban, building, floor, and unit fields.
- **Statutory Registry Verification:** Validates against **1,918 official MIC municipal records** (verified with Modulus 11 check digits) and maps **374 statutory counties** (367 distinct names, 7 shared across prefectures; JIS X 0401/0402).
- **Regional Convention Grammars:** Fully parses Kyoto intersection navigation clauses and Hokkaido cardinal grid coordinates.
- **Ambiguity Detection:** Explicitly flags inputs with ambiguous jurisdictions as ambiguous (`is_ambiguous=True`) and lists candidates with statutory LG codes rather than guessing.
- **Professional CLI & Python API:** First-class CLI (`normalize`, `parse`, `validate`, `geocode`) supporting human-readable output, JSON piping, dedicated shell exit codes, and standard input reading via `-`.
- **Optional Geospatial Resolution Layer:** A pluggable, zero-credential coordinate resolver (`jaden geocode` / `jaden.geocode()`) backed by the Geospatial Information Authority of Japan (GSI / 国土地理院).

### Local / Offline Core vs. Optional Geospatial Layer
> [!IMPORTANT]
> **Strict Offline Guarantee:** JADEN's core parsing, normalization, and validation engine is **100% local, deterministic, and offline**. It requires zero network connectivity, zero API keys, and zero heavyweight GIS libraries.
> 
> Geospatial resolution is an **explicitly decoupled, optional layer**. Running `jaden normalize`, `jaden parse`, or `jaden validate` will never execute a network request. Coordinates are resolved only when explicitly calling `jaden geocode` or `jaden.geocode()`.

### The Core Engineering Challenge
Unlike Western street-grid systems, a normalization engine must resolve four distinct layers of complexity:

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
   * Over 11 Unicode code points represent dashes in Japanese text (`-`, `－`, `‐`, `―`, `ー`, `～`, `─`, `━`, `﹣`, `﹘`, etc.).
   * The Katakana prolonged sound mark (`ー` / `U+30FC`) is simultaneously a delimiter between block numbers (`1ー2ー3` -> `1-2-3`) and a crucial character in proper nouns (`タワー`, `センター`).
   * Proper place names embed Kanji numbers (`六本木`, `八王子`, `十条`, `四日市`, `三番町`, `一番街`, `麻布十番`, `八重洲`). JADEN's multi-stage FSM protects proper nouns across both compound numeral patterns and single-digit tail notations (e.g., `六本木1`, `十条1`, `一番町1`, `八重洲1`, `麻布十番1-1`), preventing false tokenization into block numbers, while preserving ordinal building names like `第一-3ビル`.
4. **Multi-Jurisdiction Collisions on Omitted Prefectures:**
   * 37 municipal and ward names are shared across multiple prefectures (e.g. `中央区` in Tokyo and 10 designated cities; `府中市` in Tokyo and Hiroshima; `伊達市` in Hokkaido and Fukushima), and 5 name pairs collide intra-prefecture. A robust system must report ambiguity rather than silently guessing.

---

## 2. Four-Tier Taxonomy of Truth

To ensure architectural transparency, JADEN categorizes every parsed token and transformation into one of four explicit tiers:

| Tier | Classification | Definition & Examples |
| :--- | :--- | :--- |
| **Tier 1** | **Statutory / Official** | Entities strictly verified against official national registries: JIS X 0401 (Prefecture codes), JIS X 0402 (Municipality codes), 6-digit Local Government Code with Modulus 11 check digits, statutory counties (郡). |
| **Tier 2** | **Documented Convention** | Regional navigation conventions and syntactic block parsing: Kyoto Tōri-mei directional clauses, Hokkaido Jo-Chome grid coordinates, and syntactic block numbers (*Chome*, *Ban*, *Go*, *Banchi*, *Edaban*) parsed via deterministic FSM without parcel-polygon maps. |
| **Tier 3** | **Heuristic Disambiguation** | Linguistic extraction and heuristics: Town (*Machi-aza*), *Oaza*, *Koaza*, inferred prefectures/wards, and building/floor/unit extraction. |
| **Tier 4** | **System Artifact** | JADEN-specific conventions: Canonical string formatting, confidence scoring (0.0 to 1.0), serialized JSON schema, unparsed tails. |

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
   • Strips leading postal code prefixes (〒NNN-NNNN, NNN-NNNN)
                                  │
                                  ▼
   [Stage 2: Context-Bounded Kanji Numeral Converter]
   • Converts block numerals ('三丁目' -> '3丁目', '488番地')
   • Context-bounded patterns protect proper nouns ('一番街', '麻布十番', '三番町')
     and building names ('第一-3ビル')
                                  │
                                  ▼
   [Stage 3: Administrative Boundary Resolver (PrefixTrie)]
   • O(L) prefix matching against all 47 Prefectures (JIS X 0401)
   • 1,918 Municipalities & Administrative Wards (JIS X 0402 / MIC)
   • 374 Statutory Counties (郡) (367 distinct names, 7 shared across prefectures) mapped to 932 towns and villages, supporting [郡名][町村名] syntax
   • Multi-jurisdiction collision detection on omitted prefectures (中央区, 府中市, 伊達市) and duplicate intra-prefecture jurisdictions
   • Returns is_ambiguous=True with candidate lists when ambiguous
                                  │
                                  ▼
   [Stage 4: Regional Convention Parsers]
   • Kyoto Parser: Thoroughfare-aware intersection parsing without character exclusions,
     handling thoroughfares with cardinal names (東洞院通, 下立売通, 上長者町通)
   • Hokkaido Parser: Extracts cardinal coordinates (北N条西M丁目) restricted to Hokkaido jurisdictions
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
                                  │
                                  ▼ (optional explicit resolution)
   [Optional Geospatial Resolution Layer: BaseGeospatialResolver]
   • Pluggable backends: GSIGeocoder (Official 国土地理院 API)
   • Zero API keys, zero 3rd-party dependencies (urllib.request)
   • Resolves to JGD2011 / WGS 84 compatible (EPSG:6668 / EPSG:4326) coordinates without manufactured confidence scores
   • Transparent status: SUCCESS, NO_MATCH, AMBIGUOUS, ERROR
                                  │
                                  ▼
                     GeospatialResult Object
```

> [!NOTE]
> **Core Architecture Principle:** JADEN's core parsing engine (`normalize`, `parse`, `validate`) is strictly local, deterministic, and 100% offline. It never executes network calls or requires API keys or GIS dependencies. Geospatial coordinate resolution is an explicit, optional layer invoked only when calling `jaden.geocode()` or running `jaden geocode`.

---

## 4. Administrative Standards & Data Provenance

Administrative reference data in JADEN is based on public government standards and datasets:

1. **Prefecture Codes (JIS X 0401:1973, revised 2014):**
   * Exactly 47 prefectures (`01` 北海道 to `47` 沖縄県) as defined in JIS X 0401.
   * *Note on Provenance:* `src/jaden/data/jis_prefectures.json` is bundled directly without a raw source file in the repository; its provenance is not reproducible from this repository.
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
   * **Reproducibility:** The bundled `src/jaden/data/municipalities.json` is reproducible from the bundled `src/jaden/data/soumu_000925835.xlsx` via `src/jaden/data/build_municipalities.py` (pinned SHA256 in `src/jaden/data/provenance.json`).
3. **County (郡) Association:**
   * **Coverage:** 932 towns and villages (743 町 + 189 村):
     - 374 statutory counties (郡) (367 distinct names, 7 shared across prefectures), encompassing 923 county-affiliated towns and villages.
     - 9 Tokyo island municipalities explicitly verified without county jurisdiction (`大島町`, `利島村`, `新島村`, `神津島村`, `三宅村`, `御蔵島村`, `八丈町`, `青ヶ島村`, `小笠原村`).
     - Northern Territories (北方領土) villages mapped to statutory counties (`色丹郡色丹村`, `国後郡泊村`, `国後郡留夜別村`, `択捉郡留別村`, `紗那郡紗那村`, `蘂取郡蘂取村`).
   * *Note on Provenance:* `src/jaden/data/county_mapping.json` is bundled directly without a raw source file in the repository; its provenance is not reproducible from this repository.
4. **Statutory Addressing Acts:**
   * *Act on Indication of Residential Address (昭和37年法律第119号)*: Defines urban *Gaiku-hoshiki* (Chome-Ban-Go).
   * *Real Property Registration Act (平成16年法律第123号)*: Governs cadastral *Chiban* (Oaza-Koaza-Banchi-Edaban).
5. **Digital Agency Address Base Registry (アドレス・ベース・レジストリ):**
   * JADEN models ABR statutory taxonomy (Machi-aza, Gaiku, Chiban). Note: JADEN is an offline linguistic engine and intentionally does not bundle the multi-gigabyte spatial polygon GIS shapefiles of the full ABR.
6. **Open Data Attribution & Licensing Terms:**
   * **MIC Municipality Data:** Ministry of Internal Affairs and Communications (総務省自治行政局) *都道府県コード及び市区町村コード*. Governed by the Ministry of Internal Affairs and Communications Terms of Use (政府標準利用規約 第2.0版 / CC BY 4.0 compatible): `https://www.soumu.go.jp/menu_kyotsuu/important/kizoku.html`.
     Attribution: *本製品の全国地方公共団体マスターデータは、総務省「都道府県コード及び市区町村コード」を加工・構造化して作成したものです。*
   * **GSI Geospatial Data:** Geospatial Information Authority of Japan (国土地理院) Address Search API. Governed by the GSI Content Terms of Use: `https://www.gsi.go.jp/kikakukouhou/kikakukouhou40012.html`.
     Attribution: *出典：国土地理院 (地名検索API)。座標系は世界測地系 JGD2011 (WGS 84 準拠互換, EPSG:6668 / EPSG:4326) に準拠します。*
   * Complete notices and terms citations are preserved in [NOTICE](NOTICE).

---

## 5. Empirical Benchmarks

Benchmarks are executed using the reproducible suite in `benchmarks/run_benchmark.py`. Measurements reflect actual performance across a **representative 500-address corpus** without repeated-string caching. Timed loops execute with `tracemalloc` stopped to avoid profiler overhead.

> [!NOTE]
> **Benchmark Scope:** The evaluation corpus is synthetic, and the benchmark measures execution speed, latency, and memory allocations. It does not measure parsing accuracy against real-world ground truth.

### Hardware & Runtime Environment
* **OS:** Windows 11 (10.0.26200)
* **CPU:** Intel64 Family 6 Model 151 (12 Logical Cores)
* **Python Runtime:** CPython 3.13.14 (64-bit)
* **Memory Footprint:** 4.28 MB baseline heap (full registry + tries), 4.48 MB peak heap during batch execution
* **Corpus Diversity:** 500 unique addresses evaluated over 5,000 operations (10 passes)

### Empirical Performance Results

| Evaluation Corpus | Unique Addrs | Operations | Throughput (addr/sec) | Latency P50 | Latency P90 | Latency P99 | Mean Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clean Standard (Gaiku-hoshiki)** | 200 | 2,000 | **35,023.9** | 27.20 μs | 31.20 μs | 44.50 μs | 28.35 μs |
| **Complex Conventional (Kyoto/Hokkaido/Cadastral)** | 150 | 1,500 | **31,500.5** | 31.30 μs | 33.50 μs | 41.00 μs | 31.52 μs |
| **Dirty Real-World (Omitted/Dashes/Buildings)** | 150 | 1,500 | **25,356.2** | 38.40 μs | 43.10 μs | 50.00 μs | 39.19 μs |
| **Aggregate Workload** | **500** | **5,000** | **30,510.3** | **31.30 μs** | **38.40 μs** | **47.00 μs** | **32.55 μs** |

---

## 6. Installation & Usage

### Installation

```bash
# Clone the repository
git clone https://github.com/SushilRaj0177/JADEN.git
cd JADEN

# Install production package (zero external dependencies)
pip install .

# Or install with development and test tooling
pip install ".[dev]"

# Verify CLI installation
jaden normalize "東京都港区六本木1-2-3"
```

### Python Library API

```python
import jaden

# 1. Real-world urban address with landmark building & floor
res1 = jaden.normalize("東京都港区六本木6-10-1六本木ヒルズ森タワー50F")
print(res1.canonical)
# Output: 東京都港区六本木6丁目10番1号 六本木ヒルズ森タワー 50F
print(res1.components.lg_code)        # '131032' (Minato-ku)
print(res1.components.address_regime) # 'gaiku_hoshiki'

# 2. Component AST parsing
components = jaden.parse("京都府中京区御池通東洞院東入笹屋町436")
print(components.city)                      # '京都市'
print(components.ward)                      # '中京区'
print(components.kyoto_direction.street_1) # '御池通'
print(components.banchi)                    # 436

# 3. Statutory validation and ambiguity assessment
val = jaden.validate("府中市宮西町2-24")
print(val.status)                # 'AMBIGUOUS'
print(val.valid)                 # False
print(val.ambiguous_candidates)  # ('東京都府中市 (132063)', '広島県府中市 (342084)')

# 4. County (郡) resolution with omitted prefecture inference
res4 = jaden.normalize("中郡大磯町国府本郷547")
print(res4.canonical)         # '神奈川県中郡大磯町国府本郷547番'
print(res4.components.county) # '中郡'
print(res4.components.city)   # '大磯町'
print(res4.components.lg_code)# '143413'

# 5. Optional geospatial coordinate resolution (JGD2011 / WGS 84 compatible via GSI)
geo = jaden.geocode("東京都港区六本木6-10-1")
print(geo.status)                 # 'SUCCESS'
print(geo.coordinates.latitude)  # 35.660206
print(geo.coordinates.longitude) # 139.729202
print(geo.matched_address)       # '東京都港区六本木六丁目１０番'
```

### Command-Line Interface (CLI)

JADEN provides four high-performance CLI commands: `normalize`, `parse`, `validate`, and `geocode`.

#### 1. `normalize`: Canonical Address Formatting
```bash
# Clean human-readable summary
jaden normalize "東京都港区六本木1-2-3"

# Machine-readable JSON
jaden normalize "東京都港区六本木1-2-3" --json

# Canonical string only (ideal for shell scripts)
CANON=$(jaden normalize "新宿区西新宿2-8-1東京都庁 第一本庁舎" -c)
```

#### 2. `parse`: Granular Component AST Decomposition
```bash
# Pretty-printed syntactic decomposition
jaden parse "京都府中京区御池通東洞院東入笹屋町436"

# Structured AST JSON
jaden parse "京都府中京区御池通東洞院東入笹屋町436" --json
```

#### 3. `validate`: Statutory Registry & Integrity Verification
```bash
# Valid address verification (Exit code 0)
jaden validate "東京都港区六本木1-2-3"

# Ambiguity detection with candidate reporting (Exit code 2)
jaden validate "府中市宮西町2-24"

# Malformed / foreign input rejection (Exit code 1)
jaden validate "123 Main St, New York"

# Machine-readable JSON output
jaden validate "東京都港区六本木1-2-3" --json
```

#### 4. `geocode`: Optional Geospatial Resolution (JGD2011 / WGS 84 compatible)
```bash
# Human-readable coordinate summary (Exit code 0 on SUCCESS)
jaden geocode "東京都港区六本木6-10-1"

# Machine-readable JSON with WGS 84 latitude & longitude
jaden geocode "東京都港区六本木6-10-1" --json

# Ambiguous address candidate reporting (Exit code 1 on non-resolution)
jaden geocode "府中市"
```

#### Exit Codes for Shell Automation
| Exit Code | Meaning | Example Scenario |
| :---: | :--- | :--- |
| `0` | **ACCEPTED / SUCCESS** | Valid address verified (`validate`) or coordinates successfully resolved (`geocode`) |
| `1` | **MALFORMED / REJECTED** | Structurally invalid, foreign, or unparseable input (`validate`) |
| `2` | **AMBIGUOUS** | Omitted prefecture or multi-candidate municipal jurisdiction (`validate`) |
| `3` | **UNSUPPORTED** | Structurally unsupported or unparsed trailing tokens (`validate`) |
| `64` | **CLI_USAGE_ERROR** | Missing required arguments, invalid CLI options, or empty stdin input |
| `70` | **INTERNAL_ERROR** | Unhandled internal software exception |

#### Unix Standard Input Piping
```bash
# Pipe address string directly via '-'
echo "東京都港区六本木1-2-3" | jaden normalize - -c
```

---

## 7. Testing & Quality Assurance

JADEN maintains a 223-test verification suite (222 offline tests passing, 1 live network test opt-in) running continuously in GitHub Actions across Python 3.10, 3.11, 3.12, and 3.13 on both Ubuntu and Windows:
* **All 47 Prefectures:** Deep decomposition asserting prefecture, city/county, town, oaza/koaza, and exact block numbers (`chome`, `ban`, `go`, `banchi`, `edaban`) across all 47 prefectures, plus dedicated `郡` test cases across multiple prefectures (Kanagawa, Tokyo, Hokkaido, Saitama, Nagano, Okinawa).
* **Adversarial & Edge Case Payloads:** Complete regression validation against proper noun collisions (`一番街`, `麻布十番`, `三番町`, `六本木1`, `十条1`, `一番町1`, `八重洲1`), building names (`第一-3ビル`), multi-jurisdiction collisions (`中央区`, `府中市`, `泊村`), cardinal Kyoto streets (`東洞院通`, `下立売通`), and foreign/gibberish input rejection.
* **CLI & Public API Verification Tests:** Complete validation of CLI commands (`normalize`, `parse`, `validate`, `geocode`), `--json` formatting, `-c` canonical flag, standard input reading (`-`), and shell automation exit codes (0, 1, 2, 3, 64, 70).
* **Geospatial Layer Verification Tests:** Complete unit tests for `GSIGeocoder`, `BaseGeospatialResolver` custom extensibility, HTTP error handling, connection failures, network timeouts, multi-candidate ambiguity short-circuiting, offline parser independence guarantees, and query string secondary token stripping.
* **Packaging & Distribution Integrity Tests:** Verification of standalone package data loading, executable entrypoints, and public symbol exports.
* **JIS X 0402 Modulus 11 Check Digit Validation:** Algorithmic verification across all codes.

```bash
pytest -v
```

---

## 8. Explicit Boundaries & Limitations

In accordance with our engineering principles, JADEN documents its exact operational boundaries:
1. **Separation of Core Parsing and Geospatial Resolution:** JADEN's core parser is 100% offline and does not bundle multi-gigabyte spatial polygon GIS shapefiles. Geospatial resolution is provided as an optional, decoupled layer via the official open government GSI API or custom user-provided resolvers.
2. **Ambiguous Omitted Jurisdictions:** When a user omits the prefecture and enters a duplicated municipality name (e.g. `中央区`, `府中市`, `伊達市`), JADEN explicitly reports `is_ambiguous=True` and lists candidates rather than silently guessing.
3. **Private Building Records:** Building names and room numbers are parsed using syntactic heuristics (Tier 3), as no statutory national registry of private commercial building names exists. Hyphenated kanji numeral conversions protect ordinal building names such as `第一-3ビル`.
4. **Cadastral vs. Residential Distinction in Plain Hyphenated Strings:** When an input consists solely of `町名 X-Y` or `X-Y-Z` without `丁目`, `大字`, `字`, `番地`, or `号`, JADEN canonicalizes the notation to conventional residential format (`X丁目Y番Z号` or `X番Y号`) while explicitly marking `address_regime="unspecified"` in `AddressComponents`. Because determining true cadastral boundaries requires municipal cadastral maps, downstream applications requiring strict cadastral preservation should inspect `components.address_regime` and discrete block fields.
5. **Omitted Prefecture and Municipality:** Inputs that omit both the prefecture and municipality (e.g., `銀座4-1`, `道玄坂1-2`) cannot be unambiguously identified against a national registry and yield `confidence=0.0`.
6. **GSI Address Search Rate and Availability:** The optional geospatial resolution layer communicates with GSI's public `AddressSearch` endpoint. Users should consult GSI's terms of use at `https://www.gsi.go.jp/kikakukouhou/kikakukouhou40012.html`. Users deploying automated batch workloads should maintain reasonable request intervals to avoid server burden and consider deploying local geocoding caches.

---

## License

MIT License. Designed and maintained by Sushil Raj.
