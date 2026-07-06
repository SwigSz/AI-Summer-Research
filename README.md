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
