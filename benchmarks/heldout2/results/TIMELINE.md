# Held-out test 2: timeline

All times are UTC on 25 November 2026. Sources: commit times (`git log --date=iso`), the times at which
each run was started (from the working-session record), and the modification times of the output and
log files (the end of each run). The logs themselves are in `logs/`.

| Time | Event | Source |
| :--- | :--- | :--- |
| 17:00 | The five test files are downloaded; only column headers, row counts and aggregate counts are looked at (disclosed in `PROTOCOL.md`) | session record |
| **17:02:25** | **Protocol committed (`2422526`)** | git |
| 17:04:47 | Scripts committed (`c7a22d2`), written against the headers and synthetic rows | git |
| ≈17:05 | Run started: download check, inputs, then JADEN (final engine), Geolonia and jageocoder | session record |
| 17:06:13 | Test inputs written (617,912) | file time |
| 17:10:20 | JADEN, final engine, finished | file time |
| ≈17:11 | Geolonia stopped and restarted with 48 concurrent requests (see `RUN_NOTES.md`) | session record |
| 17:13:09 | JADEN, engine before the audits, finished (`logs/jaden.log`) | file time |
| 17:32:44 | jageocoder finished (`logs/jageocoder.log`) | file time |
| 17:33:56 | Geolonia finished (`logs/geolonia.log`: 444 inputs per second on average) | file time |
| 17:35:22 | Geolonia's 50 network failures retried | file time |
| 17:36:55 | Results committed (`0cc9738`) | git |
