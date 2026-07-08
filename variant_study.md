# Variant Study: reasoning vs instruct vs coder

12 tasks (4 categories x 3 difficulty tiers), single run, temp 0, on the Spark via Ollama.
Models: reasoning = gpt-oss:20b, instruct = qwen2.5:7b-instruct-q8_0, coder =
qwen2.5-coder:7b-instruct-q8_0. Scored objectively: unit tests for code, exact-match for
logic/math, deterministic format checks for instruction-following.

## Results

| variant | logic | coding | math | instruction | total | mean tokens/task | mean wall_ms |
|---|---|---|---|---|---|---|---|
| reasoning | 3/3 | 3/3 | 3/3 | 3/3 | 12/12 | 268 | 6421 |
| instruct | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 | 76 | 3724 |
| coder | 2/3 | 3/3 | 3/3 | 2/3 | 10/12 | 99 | 4766 |

## Findings

All failures were hard-tier. Easy and medium were 3/3 for every model. The tiers worked:
the gap only appears on hard tasks. Specific misses: logic_hard (instruct and coder failed,
reasoning solved), instruction_hard (coder failed, reasoning and instruct solved).

The reasoning model swept 12/12 but paid for it. On tasks all three solved, it spent 10-15x
the tokens of the instruct model (logic_easy: 40 vs 3; logic_medium: 251 vs 17). Its win
came entirely from 2 hard tasks the others missed. On the other 10, identical correctness at
several times the token and wall-time cost.

The instruct model is the efficient generalist: 11/12 at 76 tokens/task, a quarter of the
reasoning model's cost. It edged the coder overall.

Wall time tracks token count, not decode speed. The reasoning model's high decode tok/s is
offset by generating far more tokens, so it is slower to an answer (logic: 9912ms vs
1410ms for instruct).

## Practical rule

Route to the reasoning model only when a task is hard or high-stakes. For everything else
the instruct model gives the same answer at a fraction of the cost. This argues for
difficulty-aware routing, not just task-type routing.

## Caveat

Single run per cell (n=1). The pattern holds across categories, but exact hard-tier results
carry run-to-run noise. A 3-run pass on the 6 hard tasks would firm up those numbers.
