# Analyses after the held-out tests

Everything in this folder was done **after** both pre-registered tests (`benchmarks/heldout/`,
`benchmarks/heldout2/`), mostly in answer to a critical review of the paper. None of it was
pre-registered, and none of it replaces a pre-registered result: each script reads the stored outputs
of the tests (or reruns a system on the same frozen inputs) and writes its own report to `results/`.

| Script | Question | Result file |
| :--- | :--- | :--- |
| `fair_comparison.py` | Is JADEN better than jageocoder at resolving, or only at declining? jageocoder that abstains, and JADEN at the same share of answers | `fair_comparison_*.md` |
| `recalibrate.py` | The pre-registered threshold search had no multiple-testing control and reused one data split for three choices; what changes with a corrected procedure? | `recalibration.md` |
| `leakage.py` | Does the town prior, counted from corporations that include the test facilities' operators, leak answers? | `leakage.md` |
| `analysis.py` | The numbers behind the paper's analysis sections: forced answers, error types, inputs that start with a municipality name, the language-model filters separated, the projection, clustered intervals | `analysis.md` |
| `defects.py` | How many of test 1's wrong rule answers the two defects found there explain | `defects.md` |
| `prevalence.py` | How often hand-typed addresses leave out the prefecture or municipality | `prevalence.md` |

jageocoder with all candidates (`benchmarks/jabench/baselines/jageocoder_candidates_run.py`) is slow,
so the fair comparison uses a random sample of 40,000 town-only inputs per test (seed 2026), drawn by
`fair_comparison.py sample`.

## Reproduce

```bash
# T1 = folder of test 1's run (inputs.jsonl, jaden_items.pkl.gz, jageocoder.jsonl, llm_*.jsonl)
# T2 = folder of test 2's run (inputs.jsonl, items_final.pkl.gz, jageocoder.jsonl)
python benchmarks/posthoc/fair_comparison.py sample --inputs T1/inputs.jsonl --out sample_t1.jsonl
python benchmarks/posthoc/fair_comparison.py sample --inputs T2/inputs.jsonl --out sample_t2.jsonl
python benchmarks/jabench/baselines/jageocoder_candidates_run.py sample_t1.jsonl jgc_cand_t1.jsonl 2
python benchmarks/jabench/baselines/jageocoder_candidates_run.py sample_t2.jsonl jgc_cand_t2.jsonl 2
python benchmarks/posthoc/fair_comparison.py score --items T1/jaden_items.pkl.gz --sample sample_t1.jsonl \
    --first T1/jageocoder.jsonl --candidates jgc_cand_t1.jsonl --name "test 1"
python benchmarks/posthoc/fair_comparison.py score --items T2/items_final.pkl.gz --sample sample_t2.jsonl \
    --first T2/jageocoder.jsonl --candidates jgc_cand_t2.jsonl --name "test 2"
python benchmarks/posthoc/recalibrate.py --test1 T1/jaden_items.pkl.gz --test2 T2/items_final.pkl.gz
python benchmarks/posthoc/leakage.py --test1 T1 --test2 T2 --work SCRATCH
python benchmarks/posthoc/analysis.py --test1 T1 --test2 T2
python benchmarks/posthoc/defects.py --test1 T1 --before WORKTREE_AT_01a23ba --after WORKTREE_AT_db3c9aa
python benchmarks/posthoc/prevalence.py
```
