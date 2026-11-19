# Language-model runs on the held-out test (audit files)

Each `*_items.jsonl.gz` is a sample the protocol drew (seed 2026): the input, the facility name, JADEN's
candidates and the answer key. Each other file holds, per input, the model's parsed answer (`raw`), the
municipality it maps to (`lg_code`), whether the name it gave is no existing municipality (`invented`), and,
on the first input of each 20-input call, the call's raw text (`raw_text`).

| File | System (PROTOCOL.md and its amendment) |
| :--- | :--- |
| `llm_choose.jsonl.gz` | 4: claude-haiku-5-5 chooses from JADEN's candidates |
| `llm_free_on_choose.jsonl.gz` | 4b: claude-haiku-5-5 proposes, on the same sample |
| `llm_free_sonnet_on_choose.jsonl.gz` | 4b: claude-sonnet-5-5 proposes, on the same sample |
| `llm_free.jsonl.gz` | 5: claude-haiku-5-5 alone, random town-only sample |
| `llm_free_sonnet.jsonl.gz` | 5: claude-sonnet-5-5 alone, same random sample |

Addresses and facility names come from 「国土数値情報（福祉施設データ）」（国土交通省）（令和5年度）, CC BY 4.0.
