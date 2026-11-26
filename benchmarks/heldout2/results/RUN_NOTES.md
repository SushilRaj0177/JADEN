# Held-out test 2: run notes

What happened during the run, in order, as `PROTOCOL.md` requires.

- **Commits.** The protocol was committed at `2422526`, the scripts at `c7a22d2` (written against the
  column headers and synthetic rows only). The run used `c7a22d2`; `src/jaden` is identical at both
  commits. "Before the audits" is the engine at `01a23ba`, run from a separate worktree with the same
  scripts.
- **Data.** The five frozen files matched their SHA-256. 206,043 rows; 2 pharmacy rows without a
  municipality code were excluded; 211 rows got no town-only input because their address does not start
  with the prefecture and municipality names exactly. 180,655 of 206,041 facilities are "unseen".
- **Geolonia, speed.** Geolonia was first started with 8 concurrent requests, as in
  `benchmarks/jabench/baselines/README.md`. In its first minutes, while JADEN's runs used the other
  processors, it managed about 40 inputs per second, so it was stopped and restarted from the beginning
  with 48. (An earlier version of these notes said the first rate "would have needed about a day"; that
  extrapolated from those first minutes and was wrong.) The restarted run took 23 minutes, 444 inputs per
  second on average (`logs/geolonia.log`). Concurrency changes only the speed, not the answers; the
  partial first output was discarded. The full timeline is in `TIMELINE.md`.
- **Geolonia, network errors.** In the full run, 50 inputs (24 full, 21 without prefecture, 5 town only)
  failed with a network error while Geolonia fetched its town data (`fetch failed`, or an HTML page
  where JSON was expected). They were retried once, alone, and all 50 got an answer. `report.md` and
  `scores.json` use the retried answers. Without the retry, Geolonia's results differ only in those 50
  no-answers (town only: 4,382 wrong instead of 4,385); no hypothesis changes.
- **No other reruns.** JADEN (both engines), the calibrated resolver and jageocoder ran once.

## After the run (analysis; nothing here changes a reported number)

- **H6 failed narrowly.** On full and no-prefecture input, the final engine has 0 wrong answers, like the
  engine before the audits, but 17 fewer right answers (28 lost, 11 gained, of 206,041). All 28 losses
  have the same form: a registered town followed directly by a building name and a floor, with no house
  number (`愛知県名古屋市中村区名駅ミッドランドスクエア8階`, `大阪府大阪市阿倍野区阿倍野筋あべのハルカス5階`).
  A check added during the audits (text after the municipality that is not a registered town and has no
  number is a name, not an address) now rejects them; the older engine accepted them at town level.
- **The audits did generalise on town-only input**: wrong answers fell from 774 to 279 (484 of the old
  wrong answers became no answer, 11 became right), at the cost of 138 right answers that became no
  answer.
- **Other tools without the prefecture.** Geolonia's 50 wrong answers are all municipality names that exist
  in two prefectures (府中市: Tokyo or Hiroshima, 43; 伊達市: Hokkaido or Fukushima, 7), where it picks one.
  jageocoder's 2 are a name typed twice (`西宮市西宮市東鳴尾町…`) and a district name (`那賀郡那賀町…`).
