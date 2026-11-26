# Pre-merger address study: run notes

What happened during the run, as `PROTOCOL.md` requires.

- **Commits.** The protocol (with the files' SHA-256 in `data_sha256.txt`) was committed at `b982ef7`, the
  script with the next commits. `src/jaden` did not change between the protocol and the reported results; JADEN
  ran at `af8e154`.
- **Each stage ran once**: inputs (287,775 inputs: 197,013 from P02-06 and 90,762 from P14-11; 18 P02 facilities
  had no usable point), JADEN, reverse lookup (3,794 eligible facilities), the other tools' inputs (every changed
  input and 5,000 unchanged inputs per source: 19,878), jageocoder, Geolonia (48 concurrent requests, no errors),
  report.
- **The answer key.** On the unchanged controls, every wrong answer is shared by all three tools (P02-06: the same
  10 facilities; P14-11: the same 3). Three independent readings that agree against the key point to errors in the
  key (the facility's published point lying in another municipality), not in the tools. H4 is reported as
  failed, as pre-registered.

## What the results show (analysis after the run)

- **H3 fails only against Geolonia**, which answers 0.5% (2006) and 18% (2011) of the changed addresses and so
  has no wrong answers. Against jageocoder, JADEN is right more often (91.0% vs 82.8% in 2006; 99.2% vs 86.5% in
  2011) and wrong far less often (1.0% vs 10.2%; 0.07% vs 9.5% of answers).
- **JADEN's 2006 errors** are concentrated in cities that became designated cities after 2006 and now have wards
  (熊本市, 新潟市, 浜松市, 岡山市, 相模原市): an address written as `新潟市向陽2-6-1` has to be placed in a ward, and
  76 of the 80 wrong answers are such cases. On these "status or name change" inputs jageocoder is right more
  often (95.4% vs 88.5%).
- **The reverse lookup** returned an answer for 2,322 of 3,794 eligible facilities, and every answer it gave
  matched the 2006 code. The 1,472 without an answer: the district is not in the gazetteer (573), the address
  could not be read (204), the district has no 丁目 or town match (52), and 640 whose district was read but not
  found in the 2000 district table, mostly because the district was read with a 字 or 大字 prefix (`字三納`) that the
  table's keys do not carry. That last group is a defect of `jaden.history`, addressed after this report (see
  `POSTHOC.md` when present); these results stay as reported.
