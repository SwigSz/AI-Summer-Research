# Eval Harness: 48-task stratified benchmark of the router's models

A research eval built to answer one question: which local model is actually best at what,
measured objectively instead of assumed from model cards. Ran on the Spark via Ollama
directly (not the LiteLLM proxy, to get real token/timing counters).

## Method

48 tasks, hardcoded: 4 categories (code, reasoning, math, instruction-following) x 3
difficulty tiers (easy/medium/hard) x 4 tasks per cell. Every task has an objective scorer,
no LLM judge:

- **code**: generated function + unit tests, executed in a sandboxed subprocess
  (`python -I`, no network, 10s timeout).
- **reasoning / math**: exact-match against one verified canonical answer (numeric answers
  checked with Python before being written into the suite, not by hand).
- **instruction-following**: deterministic format checkers (exact word/line counts, valid
  JSON shape, palindrome check, CSV/Markdown table structure) -- no judgment on content,
  only on whether the output obeys the stated format.

Every model x task ran 5 times at temperature 0, to catch flakiness rather than to average
over randomness. Models tested: `qwen3-coder:30b`, `gpt-oss:20b`, `qwen3:4b` (every model in
the router's registry).

## Results (pass rate, all 3 tiers combined)

| model | code | reasoning | math | instruction |
|---|---|---|---|---|
| gpt-oss:20b | 100% | 91.7% | 100% | 100% |
| qwen3-coder:30b | 100% | 83.3% | 98.3% | 75.0% |
| qwen3:4b | 90% | 91.7% | 100% | 91.7% |

**Best by category** (tiebreak: cheaper mean tokens wins):

- code -> `qwen3-coder:30b` (100%, 203 tokens/answer)
- reasoning -> `gpt-oss:20b` (91.7%, 999 tokens/answer)
- math -> `gpt-oss:20b` (100%, 859 tokens/answer)
- instruction -> `gpt-oss:20b` (100%, 258 tokens/answer)

## Findings

**One classic logic puzzle beat every model tested, 0/15.** The "two ropes, uneven burn
rate, measure 45 minutes" riddle failed on all three models across all 5 runs each.
`qwen3-coder:30b` and `qwen3:4b` both answered a wrong number (30 or 15 instead of 45).
`gpt-oss:20b` never answered at all: every single run hit exactly the 8192-token context
cap and produced no final output, after ~200 seconds of internal reasoning each time. The
biggest "reasoning" model in the set spent the most compute and returned nothing.

**qwen3:4b's low price tag is misleading -- it overthinks by 5-20x.** On code tasks it
averaged 4134 tokens and 76.5 seconds per answer, against `qwen3-coder:30b`'s 203 tokens and
2.0 seconds for the same 100%/90% pass rates. Same pattern on math (1145 vs 859 tokens) and
instruction tasks (1970 vs 258 tokens, next to gpt-oss). Model size does not predict
per-answer cost here; qwen3:4b's default extended-thinking behavior does.

**qwen3-coder:30b, despite being the largest coder model, is the weakest at following exact
instructions.** It scored only 75% on instruction-following, missing 3 of 12 tasks
completely (0/5 on "exactly 4 lines of 5 words each", "exactly 8 lowercase words", "exactly
10-word sentence"). A model can be excellent at generating working code and still ignore
precise structural constraints.

**All other misses**, for completeness: `qwen3-coder:30b` got a day-of-week question wrong
every single time (0/5) and undercounted a coin-combination problem once (4/5). `qwen3:4b`
failed a hard regex-matching coding task completely (0/5).

## Practical rule

Route code to `qwen3-coder:30b`; route reasoning, math, and format-constrained tasks to
`gpt-oss:20b`; treat qwen3:4b as a fallback for cheap/simple tasks only, since its actual
cost per answer is not small. `router.py --auto` now implements exactly this, reading
`best_by_category.json` from this eval.

## Caveat

5 runs per task at temperature 0 catches flakiness and timeouts, not genuine variance across
different samples -- most cells were unanimous (5/5 or 0/5), meaning temperature-0 decoding
is highly consistent here, but a single hard puzzle failing everywhere is still an n=1 result
at the level of "is this puzzle representative of the reasoning category." Widening the
reasoning and math task pools would be the next step before trusting the category winners
much further.
