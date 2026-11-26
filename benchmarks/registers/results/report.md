# Register consistency study

Run under `benchmarks/registers/PROTOCOL.md` with JADEN at `af8e154`. Shares are of all records of the register (or of those whose address writes its municipality); intervals are Wilson 95%.

## Verdicts

| Register | Records | consistent | consistent_former_name | code_retired | conflict | district_not_in_claimed | undetermined | unreadable | code_invalid |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NTA corporations (2026-10-30) | 5,049,462 | 5,048,431 | 0 | 144 | 6 | 0 | 206 | 675 | 0 |
| MHLW care offices (2026-06) | 223,161 | 218,076 | 354 | 12 | 136 | 38 | 4,129 | 416 | 0 |
| MHLW medical facilities (2026-06-01) | 206,043 | 205,931 | 0 | 0 | 0 | 0 | 2 | 110 | 0 |
| MLIT welfare facilities P14 (2023) | 321,859 | 166,107 | 0 | 1,908 | 208 | 935 | 144,506 | 8,195 | 0 |

## Records whose address writes its municipality

| Register | Such records | Consistent (incl. former name, retired code) | 95% CI | Conflict | Code retired | Address uses a former name |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: |
| NTA corporations (2026-10-30) | 5,049,151 | 99.987% | 99.985–99.988% | 6 | 90 | 89 |
| MHLW care offices (2026-06) | 212,382 | 99.931% | 99.919–99.942% | 124 | 11 | 363 |
| MHLW medical facilities (2026-06-01) | 206,043 | 99.946% | 99.935–99.955% | 0 | 0 | 0 |
| MLIT welfare facilities P14 (2023) | 169 | 61.538% | 54.024–68.540% | 64 | 0 | 9 |

## Location signal (published coordinates in the 2026-01-01 boundaries)

| Register | Sampled consistent records: point in the code's municipality | Conflicts: point in code's / text's / both / neither |
| :--- | :--- | :--- |
| NTA corporations (2026-10-30) | 0 of 0 (0.0%, 0.0–100.0%) | 0 / 0 / 0 / 0 |
| MHLW care offices (2026-06) | 1,991 of 1,997 (99.7%, 99.3–99.9%) | 17 / 118 / 0 / 1 |
| MHLW medical facilities (2026-06-01) | 1,989 of 2,000 (99.5%, 99.0–99.7%) | 0 / 0 / 0 / 0 |
| MLIT welfare facilities P14 (2023) | 1,996 of 2,000 (99.8%, 99.5–99.9%) | 208 / 0 / 0 / 0 |

## Second reader on conflicts whose address writes its municipality (jageocoder)

| Register | Agrees with JADEN | Agrees with the code | Neither | No answer |
| :--- | ---: | ---: | ---: | ---: |
| NTA corporations (2026-10-30) | 0 | 6 | 0 | 0 |
| MHLW care offices (2026-06) | 119 | 3 | 2 | 0 |
| MHLW medical facilities (2026-06-01) | 0 | 0 | 0 | 0 |
| MLIT welfare facilities P14 (2023) | 5 | 51 | 2 | 6 |

## Inspection (categories defined in the protocol)

| Register | Verdict | Inspected | C code wrong | T text wrong | R reading wrong | G gazetteer gap | U cannot tell |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| NTA corporations (2026-10-30) | conflict | 6 | 0 | 0 | 0 | 0 | 6 |
| MHLW care offices (2026-06) | conflict | 100 | 85 | 9 | 5 | 0 | 1 |
| MHLW care offices (2026-06) | district_not_in_claimed | 38 | 2 | 4 | 27 | 1 | 4 |
| MLIT welfare facilities P14 (2023) | conflict | 100 | 0 | 0 | 100 | 0 | 0 |
| MLIT welfare facilities P14 (2023) | district_not_in_claimed | 50 | 0 | 0 | 37 | 13 | 0 |

## Hypotheses

- **H1**: does not hold
- **H2**: holds
- **H3**: does not hold
- **H4**: holds
  - H1, consistent share of records that write their municipality: NTA corporations (2026-10-30) 99.987%, MHLW care offices (2026-06) 99.931%, MHLW medical facilities (2026-06-01) 99.946%, MLIT welfare facilities P14 (2023) 61.538%
  - H2, share of records with a retired code: NTA corporations (2026-10-30) 0.004%, MHLW care offices (2026-06) 0.007%, MHLW medical facilities (2026-06-01) 0.000%, MLIT welfare facilities P14 (2023) 1.019%
  - H3, reading errors among inspected conflicts whose address writes its municipality: MHLW care offices (2026-06) 3 of 92, MLIT welfare facilities P14 (2023) 32 of 32

## Exploratory: codes that recur among conflicts

| Register | Code | Municipality | Conflicts with this code | Of them, point in the text's municipality |
| :--- | :--- | :--- | ---: | ---: |
| MHLW care offices (2026-06) | 084433 | 茨城県阿見町 | 15 | 15 |
| MHLW care offices (2026-06) | 022012 | 青森県青森市 | 5 | 5 |
| MLIT welfare facilities P14 (2023) | 232033 | 愛知県一宮市 | 25 | 0 |
| MLIT welfare facilities P14 (2023) | 402133 | 福岡県行橋市 | 15 | 0 |
| MLIT welfare facilities P14 (2023) | 182109 | 福井県坂井市 | 12 | 0 |
