# Pre-merger address study: change made after the results

Reported separately, as `PROTOCOL.md` requires. The pre-registered results in `report.md` are not replaced.

**The defect.** Of the 1,472 eligible facilities for which the reverse lookup gave no answer, 633 were read to a
registered district that is a 小字 (`藤沢町大籠字右名沢`), while the 2000 district table is keyed at 大字 level
(`藤沢町大籠`). `jaden.history.former_municipality` looked only for the district as read.

**The change.** When the read district ends with its 小字 and the 小字 is marked as such (`字` or `小字` before it,
not `大字`), the lookup falls back to the 大字. A first version stripped any parsed 小字; it gave two wrong answers
(`大字東貝塚` parsed with 小字 `貝塚` fell back to a district `東` of another former town) and was narrowed to marked
小字 before this report. No other part of JADEN changed.

**Re-measured** with `posthoc_reverse.py` on the same 3,794 eligible facilities:

| | Agrees with the 2006 code | Wrong | No answer |
| :--- | ---: | ---: | ---: |
| As pre-registered (`report.md`) | 2,322 (61.2%) | 0 | 1,472 |
| After the change | 2,699 (71.1%) | 0 | 1,095 |

H5 (at least 97% agreement) still fails. The remaining misses: districts not in the gazetteer (573), addresses
whose municipality could not be read (204), 小字 written without a `字` marker (`藤沢町藤沢町裏`), and districts
without a matching 町字 or 丁目. Because the change was designed after seeing these addresses, the 71.1% is a
development figure, not a held-out one.
