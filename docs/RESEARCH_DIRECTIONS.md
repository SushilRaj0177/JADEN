# Research directions

Where this work could go next, each with the evidence already in this repository. The first two can be
done with public data alone; the others need a partner (data access or domain knowledge).

## 1. An independent evaluation of the national geocoder (abr-geocoder)

The Digital Agency publishes the Address Base Registry (アドレス・ベース・レジストリ) and its own
open-source geocoder, `abr-geocoder`. No independent, pre-registered evaluation of it on hand-typed
addresses exists that we know of. The two held-out tests here (welfare and medical facilities, 524,000
facilities, frozen by SHA-256) and the evaluation scripts can be reused as they are: add `abr-geocoder`
as one more system, pre-register the hypotheses, run once. It would also show where ABR's 町字 master
and MLIT's 位置参照情報 disagree.

Status: `abr-geocoder` 2.3.1 is on npm, but its data server (`catalog.registries.digital.go.jp`) could not
be reached from the environment this work was done in; it has to run from a machine in Japan.

## 2. How consistent are Japan's public registers with themselves?

Every register used here carries both an address and a municipality code, and the two do not always
agree. Measured so far (`benchmarks/realdata/results/`, `benchmarks/heldout*/results/`):

| Register | Rows | Code no longer current | Text and code disagree |
| :--- | ---: | ---: | ---: |
| NTA corporations (2026-10) | 5,049,462 | 211 | 6, each a row whose code contradicts its own address |
| MHLW care offices (2026-06) | 223,161 | 15 | 119 where three independent tools agree the code is wrong |
| MLIT welfare facilities P14 (2023) | 321,859 | 3,281 not current in 2026 | 0 on full addresses |
| MHLW medical facilities (2026-06) | 206,043 | 2 missing | 0 on full addresses |

A systematic audit (all registers, all tools, every disagreement classified: typo, merger, renumbered
ward, wrong column) would be directly useful to the publishers and to anyone who links these registers.

## 3. How often is the municipality missing, and does it matter downstream?

In the care-office register, 5.1% of hand-typed addresses leave out the municipality and 13.5% the
prefecture (`benchmarks/posthoc/results/prevalence.md`); MLIT publishes every welfare-facility address
without it. The open question is the cost: how many records end up linked to the wrong municipality in
real pipelines (subsidies, inspections, epidemiology) when a tool guesses, and how much review work
abstention adds. This needs a partner who runs such a pipeline.

## 4. Historical and changing addresses

Municipalities merged from about 3,200 to 1,700 between 1999 and 2010, and wards keep changing
(Hamamatsu, 2024). JADEN already resolves 1,829 former names; on JA-AddrBench it resolves all 411 school
addresses written with Hamamatsu's abolished wards (8.3% without the former-name table). Extending this to
time-aware resolution ("which municipality was this in 1995, and which is it now?") connects to historical
GIS work on Japanese addresses (Ishikawa and Nakayama 2017, Meiji-era Tokyo; Kyoto's street-name
addresses).

## 5. Language models and addresses

The first test showed that a model choosing from a verified list is wrong as often as one answering
freely, while a registry check on free answers removes most of its errors. Open questions: does this hold
across model families, including on-premise open-weight models (as needed for patient data, cf.
AddrKG-LLM), across languages, and at the house-number level? A benchmark of address hallucinations,
checked against official registries, would be a natural next step.

## 6. Linking facilities across registers

The leakage check found 196,451 corporations registered at the same municipality, town and number
sequence as 189,019 of the 524,408 test facilities. Care offices, medical facilities, welfare facilities and
corporations describe overlapping sets of real places under different spellings and codes. Record linkage
across them (Fellegi–Sunter with address match keys plus names) would yield a joined facility registry and
a measure of how much each register misses.
