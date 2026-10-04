# JADEN — Japanese Address Data Engineering & Normalization Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Typing: PEP 561](https://img.shields.io/badge/typing-PEP%20561-green.svg)](https://peps.python.org/pep-0561/)

**JADEN** is a high-performance, deterministic Python engine for Japanese address canonicalization, administrative boundary disambiguation, and statutory classification. It resolves the dual-nature complexity of Japanese addressing without external black-box APIs, operating completely offline at over **35,000 addresses/second**.

*(日本語のドキュメントは [README_JP.md](README_JP.md) をご覧ください。)*

---

## 1. The Core Engineering Challenge

Unlike Western street-grid systems (e.g., `123 Main St, Suite 400`), Japanese addressing is fundamentally topological and historical. A production normalization engine must resolve three distinct layers of complexity:

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
   * **Chiban (地番区域):** Governed by the *Real Property Registration Act (不動産登記法, Act No. 123 of 2004)* and the Civil Code. Organized into land lots (*banchi* / 番地) and branch lots (*edaban* / 枝番).
2. **Conventional Navigation Schemes:**
   * **Kyoto Tōri-mei (通り名):** Relative street-intersection navigation (`上る` / `下る` / `東入` / `西入`). Example: `京都府中京区寺町通御池上る上本能寺前町488番地`.
   * **Hokkaido Cardinal Grids (条・丁目):** Sapporo-style grid coordinates (`北1条西2丁目`).
3. **The CJK Dash Jungle & Proper Noun Ambiguity:**
   * Over 11 Unicode code points represent dashes in Japanese text (`-`, `－`, `‐`, `―`, `ー`, `～`, etc.).
   * The Katakana prolonged sound mark (`ー` / `U+30FC`) is simultaneously a delimiter between block numbers (`1ー2ー3` -> `1-2-3`) and a crucial character in proper nouns (`タワー`, `センター`). Blind regex substitution breaks building names.
   * Proper place names embed Kanji numbers (`六本木`, `八王子`, `十条`, `四日市`, `三番町`). Global Kanji numeral conversion catastrophically corrupts proper names into `6本木` or `4日市市`.

---

## 2. Four-Tier Taxonomy of Truth

To ensure architectural transparency, JADEN categorizes every parsed token and transformation into one of four explicit tiers:

| Tier | Classification | Definition & Examples |
| :--- | :--- | :--- |
| **Tier 1** | **Statutory / Official** | Explicitly defined in Japanese law or national standards: JIS X 0401 (Prefecture codes), JIS X 0402 (Municipality codes), 6-digit Local Government Code with Modulus 11 check digits, *Gaiku* (番), *Jukyo* (号), *Banchi* (番地), *Edaban* (枝番). |
| **Tier 2** | **Documented Convention** | Officially recognized regional conventions: Kyoto Tōri-mei directional clauses, Hokkaido Jo-Chome grid coordinates, standard postal hyphenation (`6-10-1`). |
| **Tier 3** | **Heuristic Disambiguation** | Inferred transformations: Resolving omitted prefectures (`新宿区...` -> `東京都`), context-aware Chōonpu isolation, separating building and floor suffixes without whitespace. |
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
   • Negative lookahead protects proper town names ('三番町', '八幡町')
                                  │
                                  ▼
   [Stage 3: Administrative Boundary Resolver (PrefixTrie)]
   • O(L) prefix matching against all 47 Prefectures (JIS X 0401)
   • Municipality & designated city administrative ward resolution (JIS X 0402)
   • Computes official 6-digit Local Government Code with Modulus 11 validation
   • Heuristically infers omitted prefectures
                                  │
                                  ▼
   [Stage 4: Regional Convention Parsers]
   • Kyoto Parser: Isolates street names & cardinal directions (上る/下る/東入/西入)
   • Hokkaido Parser: Extracts cardinal coordinates (北N条西M丁目)
                                  │
                                  ▼
   [Stage 5: Block & Lot Finite-State Machine (BlockFSM)]
   • Deterministic state progression for Chome, Ban, Go, Banchi, Edaban
   • Resolves both explicit Japanese markers and hyphenated syntax
                                  │
                                  ▼
   [Stage 6: Building, Floor & Unit Disentangler]
   • Isolates floor (50F, 3階, B1F) and unit (301号室) from building names
                                  │
                                  ▼
                 Canonical NormalizedAddress Object
```

---

## 4. Authoritative Standards & Data Provenance

All figures, codes, and schemas bundled in JADEN are verified against official Japanese statutory authorities:

1. **Prefecture Codes (JIS X 0401:1973, revised 2014):**
   * Exactly 47 prefectures (`01` 北海道 to `47` 沖縄県).
2. **Municipality Codes (JIS X 0402:2020 & MIC Local Government Code):**
   * 5-digit JIS X 0402 base code + 1-digit Modulus 11 check digit.
   * Verified check digit formula:
     $$\text{Sum} = \sum_{i=1}^{5} d_i \times w_i, \quad W = [6, 5, 4, 3, 2]$$
     $$R = \text{Sum} \pmod{11}$$
     $$\text{Check Digit} = \begin{cases} (11 - R) \pmod{10} & \text{if } R \le 1 \\ 11 - R & \text{if } R \ge 2 \end{cases}$$
3. **Act on Indication of Residential Address (昭和37年法律第119号):**
   * Legal standard for urban *Gaiku-hoshiki*.
4. **Digital Agency Address Base Registry (アドレス・ベース・レジストリ, 2024–2025):**
   * National address registry specification defining administrative codes and town-block hierarchies.

---

## 5. Empirical Benchmarks

Benchmarks are executed using the reproducible suite in `benchmarks/run_benchmark.py`. Measurements reflect actual performance across three representative corpora without synthetic shortcuts.

### Hardware & Runtime Environment
* **OS:** Windows 11 (10.0.26200)
* **CPU:** x86_64 (12 Logical Cores)
* **Python Runtime:** CPython 3.13.14
* **Sample Size:** 30,000 address evaluations (10,000 per corpus)

### Empirical Performance Results

| Evaluation Corpus | Throughput (addr/sec) | Latency P50 (Median) | Latency P90 | Latency P99 | Mean Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Clean Standard (Gaiku-hoshiki)** | **38,949.5** | 22.10 μs | 34.40 μs | 77.00 μs | 25.39 μs |
| **Complex Conventional (Kyoto/Hokkaido/Chiban)** | **40,312.1** | 23.10 μs | 29.40 μs | 63.10 μs | 24.55 μs |
| **Dirty Real-World (Omitted/Dashes/Tails)** | **28,661.4** | 27.70 μs | 51.80 μs | 124.90 μs | 34.57 μs |
| **Aggregate Benchmark** | **35,140.8** | **24.30 μs** | **38.50 μs** | **88.30 μs** | **28.17 μs** |

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

# Normalize a real-world complex address
result = jaden.normalize("東京都港区六本木6-10-1六本木ヒルズ森タワー50F")

print(result.canonical)
# Output: 東京都港区六本木6丁目10番1号 六本木ヒルズ森タワー 50F

print(result.components.lg_code)
# Output: 131032 (Minato-ku Local Government Code)

print(result.components.chome, result.components.ban, result.components.go)
# Output: 6 10 1

print(result.components.building, result.components.floor)
# Output: 六本木ヒルズ森タワー 50F

print(result.confidence_score)
# Output: 1.0
```

### Kyoto Conventional Address Parsing

```python
result = jaden.normalize("京都府中京区寺町通御池上る上本能寺前町488番地")

print(result.canonical)
# Output: 京都府京都市中京区寺町通御池上る上本能寺前町488番地

print(result.components.kyoto_direction)
# Output: KyotoDirectionClause(street_1='寺町通', street_2='御池', direction='上る', cardinal='north', raw_clause='寺町通御池上る')

print(result.components.town)
# Output: 上本能寺前町

print(result.components.banchi)
# Output: 488
```

### Command-Line Interface (CLI)

```bash
# Single address normalization (pretty JSON)
jaden "東京都港区六本木6-10-1六本木ヒルズ森タワー50F"

# Canonical string output only
jaden -c "新宿区西新宿2-8-1東京都庁 第一本庁舎"
# Output: 東京都新宿区西新宿2丁目8番1号 東京都庁 第一本庁舎

# Batch processing via stdin (JSON Lines streaming)
cat addresses.txt | jaden --jsonl > normalized.jsonl
```

---

## 7. Testing & Quality Assurance

JADEN includes an 87-test verification suite covering:
* All 47 Japanese prefectures (JIS X 0401)
* Kyoto street navigation variations (`上る`, `上ル`, `下る`, `東入`, `西入る`)
* Sapporo cardinal grids (`北1条西2丁目`)
* Dash and hyphen Unicode permutations
* Proper noun collision guards (`六本木`, `八王子`, `四日市`, `三番町`, `十条`)

```bash
pytest -v
```

---

## 8. Explicit Boundaries & Limitations

In accordance with our engineering contract, JADEN states its boundaries clearly:
1. **Cadastral Boundary Coordinates:** JADEN is a text data engineering and normalization engine; it does not contain geospatial polygon shapefiles or latitude/longitude geocoding coordinates.
2. **Ambiguous Omitted Prefectures:** When a user omits the prefecture and enters a duplicated municipality name (e.g., `府中市` exists in both Tokyo and Hiroshima; `伊達市` exists in both Hokkaido and Fukushima), JADEN requires prefecture qualification to ensure deterministic correctness.
3. **Private Building Records:** Building names and room numbers are parsed using syntactic heuristics (Tier 3), as no statutory national registry of private commercial building names exists.

---

## License

MIT License. Designed and maintained by Sushil Raj.
