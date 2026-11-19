# Held-out evaluation protocol (pre-registered)

Written on 19 November 2026, before any system is evaluated on the test data below. The commit
that adds this file is the record of what was decided in advance. Results are reported whatever
they are, including hypotheses that fail.

## Question

**Can an address resolver know when it does not know?** Concretely: when a Japanese address does
not name its municipality, can JADEN attach a probability to each candidate that is *calibrated*
(answers given with probability 0.9 are right about 90% of the time on data it has never seen),
answer as many addresses as possible at a chosen error rate, and return candidate lists with a
coverage guarantee? And does a language model that may only choose among JADEN's candidates
answer more of the rest without the wrong answers a free-running model makes?

## Data

| Role | Data | Used for |
| :--- | :--- | :--- |
| Development | National Tax Agency corporate register (5,049,462 active companies, data of 2026-10-30) | the town-frequency prior; training the scorer |
| Development | MHLW care-office register (223,161 offices, end of June 2026) | calibration, threshold selection, conformal quantiles; split by office number, one half for calibration and one half as a development check |
| Development | JA-AddrBench (4,700 school addresses) | regression checks |
| **Test (frozen)** | **MLIT 国土数値情報 福祉施設 P14, 2023 edition (`P14-23_GML.zip`, SHA-256 `5d038a85…98d`, 324,358 facilities, 321,859 with an address)** | **the results below, once** |

The test file holds, for each facility, its name, its prefecture, its official municipality code
(the answer key) and its address *without the municipality* (`神田佐久間町3-16-6`), as MLIT
publishes it. JADEN's rules were never developed on it. Disclosure: while checking the file
format on 19 November, the first rows of the Tokyo file were printed and three of their
addresses (`関町北3-36-12`, `旭丘2-34-14`, `神明2-10-4`) were run through JADEN. No design decision
used them. The test file's large "other" category includes care facilities that may also be in
the MHLW development data, under a different publisher's spelling; results are therefore also
reported for the categories that cannot overlap (codes 01, 03, 04, 05, 06: protective, disability
and child-welfare facilities such as nurseries).

Three inputs are built from each test row:

| Input | Text | Side information |
| :--- | :--- | :--- |
| town only | the address as published (`神田佐久間町3-16-6`) | none |
| with prefecture | prefecture + address | none |
| full | prefecture + municipality + address | none |
| town only + name | the address | the facility name (`グループホームジロール神田佐久間町`) |

## Systems

1. **JADEN rules**: the engine at the commit that adds this file. Answers when it returns ACCEPTED.
2. **JADEN calibrated**: the same engine plus a scorer learned only on development data. For each
   candidate municipality (and a "none of these" option) it gives a probability; it answers the
   top candidate when that probability clears a threshold.
3. **JADEN calibrated + name**: the scorer may also use the facility name.
4. **JADEN + language model**: for inputs system 3 does not answer, a language model sees the
   address, the facility name and JADEN's candidate list, and either picks one candidate or
   declines. Its choice is accepted only if it is one of the candidates.
5. **Language model alone**: the same model names the municipality with no candidate list.
6. **Geolonia** normalize-japanese-addresses 3.1.3 and **jageocoder** 2.2.1.1 (dictionary
   `gaiku_all_v22.20260417`), read as in `benchmarks/jabench/baselines/README.md`.

The language model is `claude-haiku-5-5` through the Claude Code command line, temperature
not set (default). Because each call costs money and time, systems 4 and 5 run on a random
sample (seed 2026) of 1,000 test rows each, drawn from the rows the system concerned applies to;
everything else runs on every test row.

## Measures

For every system and input: right, wrong and no-answer counts with Wilson 95% intervals; the
risk-coverage curve (wrong answers among answers, against the share answered) and its area
(AURC). For the calibrated systems also: expected calibration error (15 equal-mass bins) and the
reliability diagram; the wrong-answer rate on test at the thresholds chosen on development data;
the coverage and the mean size of conformal candidate sets. A municipality answer counts as right
when it is the row's municipality or a ward of the row's designated city.

## Hypotheses (directions stated before the run)

- **H1**: On town-only input, JADEN rules give fewer wrong answers than jageocoder and Geolonia.
- **H2**: The calibrated scorer's probabilities transfer: ECE on the test set is at most 0.03.
- **H3**: The threshold chosen on development data for a 1% wrong-answer target gives a test
  wrong-answer rate whose 95% interval includes or lies below 1%.
- **H4**: At that threshold the calibrated system answers more town-only inputs than JADEN rules,
  and the name adds coverage on top.
- **H5**: Conformal candidate sets calibrated on development data for 95% coverage reach at least
  95% on test. (Development and test data come from different publishers, so this may fail; the
  size of any shortfall is itself the result.)
- **H6**: The language model choosing among JADEN's candidates answers part of what the calibrated
  system leaves, with a wrong-answer rate below 5% on what it answers; the language model alone
  has a higher wrong-answer rate, and some of its answers name municipalities that do not exist.

## Rules

- No test row is used for training, calibration, thresholds or any code change.
- The rule engine (`src/jaden` outside the new scorer) stays as it is at this commit; any change
  made to it before the test run is listed in the results with its reason.
- The test is run once, at the commit recorded in the results file. If a bug forces a rerun, both
  runs are reported.
- The scripts are `benchmarks/heldout/` and `benchmarks/calibration/`; the results go to
  `benchmarks/heldout/results/`.
