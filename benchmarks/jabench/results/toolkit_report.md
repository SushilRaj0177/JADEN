## Matching (名寄せ)

* Noisy spellings that get the same key as their clean address: 33,976 / 33,976 (100.0%)
* Addresses whose room is written four ways but keyed differently: 0
* Distinct published addresses sharing a key: 5 pairs of 4,692 (listed in toolkit_scores.json; each is one place written two ways)

## Typos (one character of the town replaced)

* Correct address offered in `suggestions`: 2,478 / 2,640 (93.9%)
* Autocorrect applied and right: 1,891 / 2,640 (71.6%)
* Autocorrect applied and wrong: 0
* Left uncorrected (more than one candidate, or none): 749

## Town written in hiragana

* Same result as the kanji spelling: 3,925 / 3,927 (99.9%)
* Not resolved (two towns share the reading, or no reading on file): 2
* Resolved to a different town: 0

## Hyphen form round trip

* Same result after normalizing the 4-2-8 form: 4,700 / 4,700 (100.0%)

## Extraction from text

| Context | Tested | Address found | Exact span | Extra spans |
|---|---:|---:|---:|---:|
| sentence | 4,700 | 100.0% | 99.9% | 0 |
| label | 4,700 | 100.0% | 99.9% | 0 |
| parentheses | 4,700 | 100.0% | 99.9% | 0 |
| postal | 4,609 | 100.0% | 99.9% | 0 |
| with_room | 4,700 | 100.0% | 99.9% | 0 |

* Text with a school name, date, phone number and price but no address: 0 false positives in 4,700

## Autocomplete (real town among the first 10 suggestions)

* After typing the municipality and 2 characters of the town: 2,581 / 2,841 (90.8%)
* After 3 characters: 2,179 / 2,841 (76.7%)

## Postal lookup

* Filled-in postal code looks up to the same municipality: 4,609 / 4,609 (100.0%)

## Reverse geocoding (surveyed school point -> address)

| Data | Municipality | Town | 丁目 (when town right) | Median distance to matched point |
|---|---:|---:|---:|---:|
| bundled town points | 98.5% | 67.6% | 91.0% | 287 m |
| + block data | 99.2% | 87.3% | 96.2% | 53 m |
