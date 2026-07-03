# Friday: parallel serving on the Spark, what 128GB actually buys you

I loaded two models on the Spark at once, gpt-oss:20b and qwen3-coder:30b, and hit both
with concurrent requests to see what the DGX's 128GB unified memory unlocks. The capacity
question and the speed question turned out to have different answers.

## Capacity: yes

Both models loaded together with no OOM and no spill. gpt-oss:20b at roughly 13GB and
qwen3-coder:30b at 31GB fit side by side inside 128GB with room left over. `ollama ps`
showed qwen3-coder at 100% GPU the whole time. On capacity alone, the Spark handles this
without complaint.

## Bandwidth under concurrent load: no

That's where it breaks. I ran 5 concurrent requests against qwen3-coder alone, then 5
against it while gpt-oss also had 5 in flight.

| condition | qwen3-coder:30b tok/s | wall time (its 5 reqs) |
|---|---|---|
| solo, 5 concurrent | 25.21 | 0.88s |
| shared with gpt-oss, 5+5 concurrent | 1.44 | part of 45.62s total |

A 17x collapse in per-request speed, and roughly a 50x collapse in total system
throughput, caused by nothing except a second model competing for the same memory bus at
the same time. gpt-oss held up comparably better under the same load (13.60 tok/s), so the
degradation wasn't even across models, it hit the larger one hardest.

This is the same cliff shape as Wednesday's RTX 4060 result, a model that fits fine and
then falls off a cliff under one specific condition, except Wednesday's cliff was VRAM
capacity and this one is memory bandwidth contention. Two different mechanisms, same
lesson: having room isn't the same as having throughput.

## What this means

128GB of unified memory buys you the ability to *hold* multiple large models
simultaneously. It does not buy you the ability to *serve* them at full speed at the same
time, because decode is bandwidth-bound (this week's running theme) and two models sharing
one memory bus split that bandwidth between them, unevenly, with the larger model losing
more.

Practical read: on this hardware, running two big models concurrently for production
serving is a bad idea unless the workload can tolerate a shared, degraded rate. Sequential
serving, or picking one smaller resident model, gets far more real throughput than trying
to keep two heavyweight models hot at once.

## Curator decision

This changes the standardization call. qwen3-coder:30b is the wrong pick if Curator might
ever run alongside another workload on the same box, it's the model that loses the most
under contention. gpt-oss:20b degrades far less under the same shared load, so it's the
safer standard if concurrent serving is ever in play. If Curator will always run alone,
this doesn't matter and the choice reverts to whichever model summarizes best.

## Numbers

- qwen3-coder:30b solo, 5 concurrent: 25.21 tok/s, 0.88s wall
- qwen3-coder:30b shared with gpt-oss:20b, 5+5 concurrent: 1.44 tok/s
- gpt-oss:20b shared with qwen3-coder, 5 concurrent: 13.60 tok/s
- Total wall time, 10 concurrent requests split across both models: 45.62s
