# Local LLM benchmark: memory bandwidth vs decode speed

I ran the same two models across four machines to test one claim: when you run an LLM
locally, decode speed is set by memory bandwidth, not by compute. The data backs it.

Each generated token reads the model's weights out of memory once. The math per token is
small, so the read is the slow part. That makes decode a memory-bandwidth problem. Prefill
(processing the prompt) is the opposite, since it does one large matmul over many tokens at
once, so it leans on compute.

## Setup

One Python script (`bench_harness.py`, standard library only) hits each machine's local
Ollama at `localhost:11434`, pins context to 8192, warms each model with a throwaway call,
then times four prompts (short, medium, long, summarize) at temp 0. It logs decode tok/s,
prefill tok/s, time to first token, and loaded memory from `ollama ps`. Every machine
writes its own CSV and a results markdown.

| machine | hardware | spec mem bandwidth |
|---|---|---|
| Mac | M5 Max, 128 GB unified | ~500-550 GB/s |
| spark-8040 | DGX Spark GB10, 128 GB unified | 273 GB/s |
| VeranixWindows | Surface Laptop Studio 2, RTX 4060 8 GB | ~256 GB/s |
| raspberrypi | Pi 5, CPU only | ~17 GB/s |

Models: `llama3.2:3b` and `qwen2.5:7b`, both Q4_K_M.

## Decode tok/s

| model | Mac | spark-8040 | Surface 4060 | Pi 5 |
|---|---|---|---|---|
| llama3.2:3b | 187.75 | 91.75 | 86.95 | 4.91 |
| qwen2.5:7b | 103.75 | 45.73 | 46.30 | 2.39 |

Three things fall out of this table.

The Mac decodes about twice as fast as the Spark on the identical models. The Spark has the
larger compute budget and still loses, because the Mac moves roughly twice the memory
bandwidth and decode rides that number. Compute does not enter.

The Surface and the Spark sit on top of each other. Their memory bandwidth is close (~256
vs 273 GB/s), so their decode lands in the same place even though one is a discrete GPU and
the other is a Grace-Blackwell SoC.

The Pi is the floor. At ~17 GB/s it manages 5 tok/s on the 3B and 2.4 on the 7B, which is
about one eighteenth of the Mac. The ratio tracks the bandwidth ratio, not any compute
spec.

Within each machine the size effect repeats: the 7B decodes roughly half as fast as the 3B,
matching the size ratio, because there are about twice as many weight bytes to read per
token.

## Effective bandwidth

Multiply decode tok/s by the Q4 weight size to back out the bandwidth each machine actually
realizes during decode.

| machine | 3B eff GB/s | 7B eff GB/s | spec GB/s |
|---|---|---|---|
| Mac | 379 | 486 | ~500-550 |
| spark-8040 | 185 | 214 | 273 |
| Surface 4060 | 176 | 217 | ~256 |
| Pi 5 | 10 | 11 | ~17 |

Realized bandwidth lands at 65 to 85 percent of spec on every machine. The 7B reads closer
to the ceiling than the 3B because a larger model spends more of each token on weight reads
and less on fixed per-token overhead. Use the 7B column as the better estimate of each
machine's decode ceiling.

## Prefill goes the other way

Prefill is compute-bound, so the ranking flips on the parts where compute leads. The Spark
posts the highest prefill on the 3B (4721 tok/s mean) and beats the Mac there, even though
it loses decode. So the Spark is not slow, it is bandwidth-starved on decode and strong on
prefill. That split is the clearest single illustration of the two regimes.

## Limitations and notes

The Surface time-to-first-token runs high on every prompt (~3000-4000 ms), not only the
first. Decode is healthy, so the model is GPU-resident. I read this as Windows
prefill/scheduling overhead and did not chase it further.

The Pi runs Ollama on CPU. It does not touch the Hailo-10H NPU, which needs its own SDK and
compiled models. So the Pi number is a CPU edge floor, not an NPU result.

I did not run the VRAM-wall case. A model larger than the 4060's 8 GB (for example
`qwen2.5:14b` at ~9 GB Q4) would spill to shared memory and drop decode into single digits,
which would show capacity as a separate bottleneck from bandwidth. That run is the obvious
next addition.

Everything here is single-stream, batch 1. Under concurrency the picture changes,
especially for the Spark, where batched serving recovers a lot of throughput.

## Reproduce

Start Ollama, then run the harness with bare Python 3.

```
# macOS / Linux
python3 bench_harness.py

# Windows
py bench_harness.py
```

Each machine writes `comparison_<hostname>.csv` and `results_<hostname>.md`. Missing models
get pulled on first run.

## Layout

```
.
├── bench_harness.py          # the harness
├── README.md
└── data/
    ├── comparison_all.csv             # all four machines, merged
    ├── summary.csv                    # per machine+model means + effective bandwidth
    ├── comparison_VeranixWindows.csv
    ├── results_Mac.md
    ├── results_spark-8040.md
    ├── results_VeranixWindows.md
    └── results_raspberrypi.md
```

## Log

Day 3 (Game Day): one-shot game showdown and 4060 VRAM ceiling. See [gameday.md](gameday.md).
