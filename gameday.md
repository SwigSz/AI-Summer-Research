# Game Day: the 8 GB wall, built into

I gave three backends the same prompt, one shot, no edits, no iteration: build a playable
Asteroids game as a single self-contained HTML file, eight named features. Then I walked a
size ladder on the RTX 4060 until a model spilled off the card. The point was to feel the
memory limit by building on it, not read about it.

## The showdown

Same prompt to all three. One-shot means it runs with zero edits. Features counts how many
of the eight work: rotate, thrust with momentum, fire, screen wrap, asteroid splitting,
three lives, score by size, restart.

| backend | model | decode tok/s | one-shot | features /8 | result |
|---|---|---|---|---|---|
| frontier | Claude Opus 4.8 | n/a | pass | 8/8 | fully playable |
| big local | qwen3:30b-a3b | 71.62 | fail | 0/8 | crashes on load |
| small local | qwen3:4b | 70.45 | fail | ~1/8 | renders, no mechanics |

Neither local model produced a working game, and they failed in different ways.

The 30B was fast at 71 tok/s and wrote confident, compact code that does not run. Three
real bugs in its output: it references a `keys` object it never declares, a stray `return`
fires every frame and halts the game loop, and it clears all key state each frame so input
could never register. Blank page, JavaScript error on load. Zero features because it never
starts.

The 4B ran at 70 tok/s and produced code that renders but is a hollow shell. Black canvas,
a score readout, drifting circles, no triangular ship, no controls, nothing interactive.
It looks like a game in a screenshot and does nothing. It draws asteroids and stops there.

Frontier did the whole thing in one shot, all eight features, playable.

Reading the gap: the two local models sit at the same decode speed, so speed was never the
differentiator here. Capability was. The lesson I wanted from Game Day is that a fast local
model is not a substitute for a capable one on a one-shot coding task, and the failure modes
are worth naming. Fast-but-broken (the 30B) and running-but-empty (the 4B) are both traps you
only see by running the output, not by reading the tok/s.

## The 4060 ceiling

Same card, same context (4096), models walked up in size. I watched the `ollama ps`
processor split and read decode rate at the two edges.

| model | size | processor | decode tok/s |
|---|---|---|---|
| qwen3:4b | 3.2 GB | 100% GPU | fits |
| qwen2.5:7b | 4.7 GB | 100% GPU | fits |
| qwen3:8b | 5.6 GB | 100% GPU | 44.02 |
| qwen2.5:14b | 10.0 GB | 38%/62% CPU/GPU | 11.12 |

Ceiling: qwen3:8b at 5.6 GB, the largest model that stays entirely on the GPU. Breaking
point: qwen2.5:14b at 10 GB, the first to overflow the 8 GB card and push 38 percent of the
work onto the CPU.

The number that matters is the drop across that boundary. On the GPU, qwen3:8b decodes at
44 tok/s. The moment qwen2.5:14b spills, decode falls to 11, a 4x collapse. Nothing changed
except whether the weights fit in VRAM. When part of the model lives in system RAM, every
token has to cross PCIe, and that path is far slower than the card's own memory. The wall
sits between roughly 5.6 and 8 GB of model, which is what an 8 GB card leaves once the KV
cache and overhead take their share.

## Notes

The qwen3:8b prompt-eval rate reads slow (4.57 tok/s) because that run included an 8.7s
cold model load in the timing. The decode rate of 44.02 is the clean figure.

Both local models are Qwen3 thinking models. The `/no_think` prompt string was ignored via
the Ollama CLI; the 4B burned 1598 tokens deliberating over how to count to five. Disabling
thinking needs the API `"think": false` option, not the prompt suffix.

Capturing model code through the CLI with `--verbose` corrupted the HTML with terminal
escape and cursor codes, which produced fake syntax errors unrelated to the model. The clean
capture path is the `/api/generate` endpoint over HTTP, which returns raw JSON with no
terminal contamination. Score models on API output, not scraped terminal output.

Curator angle: a 4B fits comfortably on the 4060 at ~70 tok/s, so cost is not the blocker
for a cheap local Curator. Whether its summaries are good enough is a separate test, but the
game result says do not trust a small local model on anything that needs working structure
without checking the output.

## Done

Largest model the 4060 runs on-GPU: qwen3:8b (5.6 GB, 44 tok/s). Breaking point recorded:
qwen2.5:14b spills to a 38/62 CPU/GPU split and drops to 11 tok/s. Three-way one-shot game
showdown logged with failure modes.
