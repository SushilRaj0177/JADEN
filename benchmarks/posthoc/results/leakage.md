# Post-hoc: town-prior leakage check

Test facilities keyed by municipality, registered town and numbers: 395,384 distinct keys (524,408 facilities of both tests). Corporations in the National Tax Agency register with the same key: **196,451**, sharing a key with **189,019** test facilities. They are removed from the prior, and every town-only test input is rebuilt with each prior and scored with the same model and threshold.

Both priors are used with the current engine. For test 2 that is the engine the test ran (the full-prior rows reproduce its reported numbers exactly); for test 1 it is not: the engine has changed since test 1, partly through fixes found on test 1's own errors, so test 1's absolute numbers here are not test results. Only the difference between the two priors is the measurement.

| Test | Model | Prior | Right | Wrong | Wrong among answers (95% CI) |
| :--- | :--- | :--- | ---: | ---: | :--- |
| test 1 | calibrated | full | 59.80% | 1,460 | 0.76% (0.72–0.80%) |
| test 1 | calibrated | reduced | 59.71% | 1,505 | 0.78% (0.75–0.83%) |
| test 1 | calibrated + name | full | 61.23% | 1,555 | 0.79% (0.75–0.83%) |
| test 1 | calibrated + name | reduced | 61.15% | 1,567 | 0.80% (0.76–0.84%) |
| test 2 | calibrated | full | 58.59% | 880 | 0.72% (0.68–0.77%) |
| test 2 | calibrated | reduced | 58.50% | 906 | 0.75% (0.70–0.80%) |
| test 2 | calibrated + name | full | 59.80% | 1,075 | 0.87% (0.82–0.92%) |
| test 2 | calibrated + name | reduced | 59.73% | 1,079 | 0.87% (0.82–0.92%) |
