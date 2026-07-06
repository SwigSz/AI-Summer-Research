# Monday: Model Router (open-model families)

A tool that takes a task, decides which local model is the right one for it, and routes the
request through a LiteLLM proxy. Built as the afternoon deliverable for the open-model
families unit. The point: different models are good at different things, so route each task
to the one that fits instead of sending everything to one model.

## What it does

Given a task string, the router classifies it into a category with deterministic keyword
rules (first match wins), maps that category to a model, sends the request through the
LiteLLM proxy at localhost:4000, and logs the decision.

Routing rules:

| category | trigger keywords | model |
|---|---|---|
| coder | code, function, script, debug, bug, python, javascript, compile, refactor, api, class, regex | qwen3-coder:30b |
| reasoning | prove, reason, step by step, math, logic, calculate, why, explain how, derive | gpt-oss:20b |
| default | anything with no keyword match | qwen3:4b |

Keyword rules are deterministic on purpose. The task is classified by code, not by asking a
model to classify it, so routing is predictable and cheap.

## Architecture

- `route(task)` returns (category, model, reason) from the keyword rules.
- `send(task)` calls route(), POSTs to the LiteLLM proxy's /v1/chat/completions with the
  chosen model, returns the response text.
- Every decision is logged to `logs/router.jsonl`: timestamp, task, category, model, reason,
  latency, prompt/completion tokens.
- LiteLLM sits in front of Ollama and exposes all three local models behind one
  OpenAI-compatible endpoint on port 4000.

## Stack

- LiteLLM proxy (port 4000) fronting Ollama (port 11434) on the DGX Spark
- Three local models, all via Ollama: qwen3-coder:30b, gpt-oss:20b, qwen3:4b
- router.py: standard library + requests only
- All-local, no frontier/cloud tier in this build (no API key needed)

## Test results

Three tasks, three different models chosen correctly:

| task | routed to | reason |
|---|---|---|
| "write a python function to reverse a string" | qwen3-coder:30b | matched "function" |
| "prove the square root of 2 is irrational" | gpt-oss:20b | matched "prove" |
| "give me a fun fact about otters" | qwen3:4b | no match, default |

Each produced an appropriate answer: the coder model returned multiple correct
implementations, the reasoning model returned a full proof by contradiction (plus an
infinite-descent alternate), the small default model returned a quick fun fact. Routing
behaved exactly as designed, right task to right model.

## Quality gate

- Works end to end: task in, correct model selected, answer out
- Observability on: every routing decision logged to logs/router.jsonl
- Routes multiple task types to distinct models: confirmed across three categories
- Documented: this file
- UI: current build is a CLI tool (not user-facing); a designed UI mockup is the optional
  next step if it gets a front end

## Run it

```
python3 router.py "your task here"
```

Example:
```
python3 router.py "debug this regex"          # -> qwen3-coder:30b
python3 router.py "explain how gradient descent works"   # -> gpt-oss:20b
python3 router.py "what's the capital of France"         # -> qwen3:4b
```

## How to extend

- Add a frontier tier: register an Anthropic/OpenAI model in the LiteLLM config and add a
  "high stakes" category that routes to it.
- Add confidence: return how many keywords matched, surface it in the output.
- Add a UI: mock it in Claude Design, wire the Route button to router.py.
- Smarter routing: fall back to a small model classifying the task only when keyword rules
  don't match, keeping the deterministic path as the default.

## Context for another Claude session

If you are picking this up in a fresh chat: this is a local model router built on the DGX
Spark. It routes coding tasks to qwen3-coder:30b, reasoning tasks to gpt-oss:20b, and
everything else to qwen3:4b, all served locally through a LiteLLM proxy on port 4000 that
fronts Ollama. Classification is deterministic keyword matching, not model-based. The build
works end to end and logs every decision to logs/router.jsonl. Next possible steps are a
designed UI, a frontier tier, and confidence scoring.
