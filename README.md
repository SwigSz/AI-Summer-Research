# Building to understand: a summer of local-AI experiments

This repo is my research log for the summer. Each entry is one question about running AI
locally that I answer by building something and measuring it, not by reading about it. The
rule is the same every time: run it one-shot or from first principles, log the number, and
name the failure mode instead of hiding it.

Hardware I test across: M5 Max Mac (128 GB unified), DGX Spark GB10 (128 GB unified),
Surface Laptop Studio 2 (RTX 4060, 8 GB), Raspberry Pi 5. Models run on local Ollama unless
a frontier model is named.

## Findings so far

**01 · Decode speed is a memory-bandwidth problem, not a compute one.**
Ran `llama3.2:3b` and `qwen2.5:7b` across four machines. Decode tok/s tracks memory
bandwidth, not compute. The Mac decodes ~2x the Spark on identical models because it moves
~2x the bandwidth, and the discrete-GPU Surface lands right on top of the Grace-Blackwell
Spark because their bandwidth is close. Realized bandwidth is 65 to 85 percent of spec.
Prefill flips the ranking, because prefill is compute-bound. → [benchmark.md](benchmark.md)

**02 · Game Day (Day 3): fast is not capable, and the 8 GB wall is real.**
Same one-shot prompt (build playable Asteroids as one HTML file, eight features) to three
backends. Only frontier (Claude Opus 4.8) produced a working game, 8/8. `qwen3:30b` was fast
at 71 tok/s but wrote confident code that crashes on load; `qwen3:4b` rendered an empty
shell. Then I walked a size ladder on the 4060: `qwen3:8b` (5.6 GB) is the largest that
stays fully on GPU at 44 tok/s; `qwen2.5:14b` (10 GB) spills to a 38/62 CPU/GPU split and
decode collapses 4x to 11 tok/s. Speed never separated the two local models. Capability and
VRAM did. → [gameday.md](gameday.md)

**03 · MCP honeypot (Day 4, Jul 3): local models attack decoy tools, and framing decides refusal.**
Built a deception MCP server exposing four valuable-looking but fake tools (`read_file`,
`query_database`, `get_api_keys`, `send_notification`) that log every call and return
fabricated data, with honeytoken tripwires. Then red-teamed it with local models.
`qwen2.5:7b` took the bait every run (5/5) and tried to exfiltrate the honeytokens.
`gpt-oss:20b` refused the blatant "steal everything" prompt but complied fully when the same
goal was reframed as a routine IT task. Same objective, opposite outcome, decided only by
framing. Refusals are logged as data, not dropped. → [mcp-honeypot/](mcp-honeypot/)

**04 · Model router (Jul 6): send each task to the model that fits it.**
Built a router that classifies a task with deterministic keyword rules, then routes it
through a LiteLLM proxy to the right local model: coding to `qwen3-coder:30b`, reasoning to
`gpt-oss:20b`, everything else to `qwen3:4b`. Classification is code, not a model call, so
routing stays predictable and cheap. Three test tasks each hit the correct model (a coding
prompt, a proof, a fun fact), and every decision logs to `logs/router.jsonl` with its
category, model, reason, latency, and tokens. → [model-router.md](model-router.md)

**05 · Variant study (Jul 7): the reasoning model's win is two hard tasks, not a clean sweep.**
12 tasks (4 categories x 3 difficulty tiers), single run, temp 0, scored objectively (unit
tests, exact-match, format checks). Compared reasoning (`gpt-oss:20b`), instruct
(`qwen2.5:7b-instruct-q8_0`), and coder (`qwen2.5-coder:7b-instruct-q8_0`). All three tied
3/3 on every easy and medium task; the gap only shows up on hard tier. Reasoning swept
12/12, but that edge came entirely from 2 hard tasks the other two missed — on the other 10
it matched their correctness at 10-15x the tokens (logic_easy: 40 vs 3) and was slower to
answer despite faster decode, because it just writes far more of them. Instruct was the
efficient generalist: 11/12 at a quarter of reasoning's cost. Argues for difficulty-aware
routing, not just task-type routing. n=1 per cell; hard-tier numbers carry run-to-run noise.
→ [variant_study.md](variant_study.md)

**06 · Eval harness (Jul 8): a riddle beat every model, and "small" wasn't cheap.**
Built a 48-task stratified benchmark (code/reasoning/math/instruction x easy/medium/hard x
4, all objectively scored: unit tests, exact-match, deterministic format checks) and ran it
5x per task at temp 0 across `qwen3-coder:30b`, `gpt-oss:20b`, and `qwen3:4b`. The
burning-ropes logic puzzle failed 0/15 across every model; `gpt-oss:20b` didn't even answer
it, hitting its 8192-token context cap on internal reasoning every single run. `qwen3:4b`
matched or beat the bigger models on pass rate but overthought its way to 5-20x the tokens
per answer (4134 vs 203 tokens on code, next to `qwen3-coder:30b`) -- small does not mean
cheap. And the biggest coder model was worst at following exact output-format instructions
(75%, missing 3 of 12 tasks completely). Wired the winners straight into the router:
`router.py --auto` now routes by these results. → [eval_harness_study.md](eval_harness_study.md)

**07 · LoRA fine-tune (Jul 9): "55% accuracy" hid a 5%-recall detector, and a tiny adapter fixed it.**
Fine-tuned Qwen2.5-0.5B-Instruct to flag security log lines as benign/suspicious. Out of the
box it scored 55%, but the error was entirely one-sided: it caught 21/21 benign lines and
only **1 of 19 actual attacks** -- waving brute-force, SQLi, traversal, and reverse-shell
lines through as safe. A PEFT LoRA adapter (r=16, 2.16M params = 0.44% of the model), trained
3 epochs on CPU in ~7 minutes, took suspicious recall from 1/19 to **19/19** at 100% overall,
zero false positives. 8.7 MB of trained weights on a frozen base, no GPU. The catch: data is
synthetic and the test set shares generators with train, so this proves the adapter learned
the patterns cleanly, not that it generalizes to real logs. → [lora/lora_study.md](lora/lora_study.md)

## The through-line

Four experiments, four limits on the same local hardware. Bandwidth sets how fast a model
runs. Capability sets whether its output actually works. Safety training is prompt-fragile,
so what a model refuses depends on how you ask. And no single model is best at everything, so
the fourth build stops pretending one is and routes each task to the model that fits. None of
these show up in a spec sheet.

## Layout

```
.
├── README.md                  # this log
├── benchmark.md               # 01: bandwidth vs decode, four machines
├── bench_harness.py           # the benchmark harness (stdlib only)
├── data/                      # 01: per-machine CSVs and results
├── gameday.md                 # 02: one-shot game showdown + 4060 VRAM ceiling
├── gameday/                   # 02: the Asteroids artifact + screenshot
├── model-router.md            # 04: task-to-model router over a LiteLLM proxy
├── variant_study.md           # 05: reasoning vs instruct vs coder, difficulty tiers
├── eval_harness_study.md       # 06: 48-task stratified benchmark, router auto-mode
├── lora/                      # 07: LoRA fine-tune, log benign/suspicious classifier
│   ├── lora_study.md          #     writeup: baseline 55% -> adapter 100%
│   ├── make_dataset.py        #     generate the 200-line labeled dataset
│   ├── baseline.py            #     split + zero-shot base-model eval
│   ├── train_lora.py          #     PEFT LoRA fine-tune -> adapter/
│   ├── evaluate.py            #     base + adapter eval on the same test set
│   └── adapter/               #     the trained 8.7 MB LoRA adapter
└── mcp-honeypot/              # 03: decoy MCP server, red-team harness, dataset
    ├── server.py              #     the honeypot (4 fake tools, full logging)
    ├── attacker.py            #     red-team harness (scripted + local-LLM modes)
    ├── classify.py            #     intent classifier (local Ollama)
    ├── report.py              #     model-by-model results table
    ├── dashboard.html         #     live attack-type view
    ├── prompts/               #     attack-prompt variants
    ├── logs/                  #     the dataset (fake keys masked for publishing)
    └── reports/summary.md     #     current findings table
```

## How this log grows

Each new experiment adds its own folder or writeup plus one numbered entry above, newest
last. The entry states the question and the finding in a few lines; the linked file carries
the method, tables, and notes. Nothing gets deleted when a later run revises an earlier
read, it gets a new entry that says so.
