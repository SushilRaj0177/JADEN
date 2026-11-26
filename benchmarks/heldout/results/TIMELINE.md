# Held-out test 1: timeline

All times are UTC on 19 November 2026. Sources: commit times (`git log --date=iso`), the times at which
each run was started (from the working-session record), and the modification times of the output and
log files (the end of each run). The logs themselves are in `logs/`.

| Time | Event | Source |
| :--- | :--- | :--- |
| 07:29:20 | The test file `P14-23_GML.zip` is downloaded and its SHA-256 computed | session record |
| 07:29:28–07:29:57 | Format check, disclosed in `PROTOCOL.md`: attribute names, category counts, the first rows of the Tokyo file; three of its addresses run through JADEN | session record |
| **07:45:54** | **Protocol committed (`991bffb`)** | git |
| 07:51:14 | Test inputs built (`make_inputs.py`); Geolonia started on them | session record |
| 07:52–07:59 | Language-model development trial on 400 ambiguous **care-office** addresses (development data, not test data) | session record |
| 07:59:34 | Calibrated resolver and evaluation scripts committed (`e7f36ab`) | git |
| 07:59:42 | JADEN (rules and calibrated resolver) started on the test inputs | session record |
| **08:00:51** | **Amendment 1 committed (`01a23ba`)**, based on the development trial; no test result had been produced yet | git |
| 08:05:44 | Geolonia finished (965,577 inputs; `logs/geo.log`) | file time |
| 08:06:02 | JADEN finished (`logs/prepare.log`) | file time |
| 08:06:47 | The five language-model runs (1,000-input samples) and jageocoder started | session record |
| 08:14–08:30 | Language-model runs finished (`logs/llm1.log` … `logs/llm5.log`) | file times |
| 08:15:56 | Two rule defects found in JADEN's test errors fixed (`db3c9aa`); reported results use the engine before this fix | git |
| 08:35:14 | jageocoder finished (`logs/jgc.log`) | file time |
| 08:38:11 | Results and paper draft committed (`2c9a95e`) | git |

The whole run took about 45 minutes because the systems ran at the same time on four processors:
Geolonia at about 1,100 inputs per second, jageocoder with three processes, and the language-model calls
in parallel batches of 20 addresses.

Deviations from the protocol's wording: Geolonia ran with 16 concurrent requests instead of the 8 in
`benchmarks/jabench/baselines/README.md` (concurrency changes speed, not answers). The amendment was
committed 69 seconds after JADEN's run had started and 5 minutes before it finished; it changed only the
language-model systems and was based on development data.
