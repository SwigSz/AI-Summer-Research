# LoRA fine-tune: teaching a 0.5B model to flag suspicious logs

Question: can a tiny local model that is useless at security-log triage out of the box be
fixed with a small LoRA adapter, on CPU, in minutes? Measured base vs adapter on the same
held-out test set, so the delta is the fine-tune and nothing else.

Model: Qwen2.5-0.5B-Instruct, local, `transformers` + `peft`. Everything ran on CPU (the
box's GPU path needs `python3-dev` headers that are not installed, so the Triton JIT shim
fails to compile; the scripts probe CUDA and fall back to CPU automatically).

## Method

1. **Dataset** (`make_dataset.py` -> `logs.jsonl`): 200 synthetic log lines, 100 benign /
   100 suspicious, in realistic sshd / nginx / syslog formats with varied IPs, users,
   timestamps. Benign: publickey accepts, sudo success, cron, HTTP 2xx/3xx, service starts,
   dpkg installs. Suspicious: ssh brute force, SQLi in URLs, directory traversal, privesc
   attempts, UFW-blocked outbound to odd ports, known-bad user agents (sqlmap/nikto/ZmEu),
   reverse-shell payloads. Seeded, deduped.
2. **Split** (`baseline.py`): shuffle seed 42, 80/20 -> `train.jsonl` (160), `test.jsonl`
   (40, landing 21 benign / 19 suspicious).
3. **Baseline** (`baseline.py`): zero-shot prompt the untuned base model to answer
   benign/suspicious.
4. **Train** (`train_lora.py`): PEFT LoRA r=16, alpha=32, dropout 0.05, targeting the four
   attention projections (q/k/v/o_proj). Each example is the instruction prompt "Classify
   this log line as benign or suspicious:\n<text>" with the label as the completion; loss is
   masked to the completion tokens only. 3 epochs, batch 4, 120 steps.
5. **Evaluate** (`evaluate.py`): same base model with the adapter applied, same `test.jsonl`,
   same prompt format as training.

## Results

| | accuracy | benign recall | suspicious recall |
|---|---|---|---|
| base, zero-shot | 55.0% (22/40) | 21/21 | **1/19** |
| + LoRA adapter | 100.0% (40/40) | 21/21 | **19/19** |

Training cost: 2,162,688 trainable params (0.44% of the model), 3 epochs in ~7 minutes on
CPU. Train loss fell from 0.57 to ~0.09. Adapter on disk: 8.7 MB.

## Findings

**The base model's failure was specific and dangerous, not random.** It scored 55%, but the
error was entirely one-sided: it labeled almost everything benign, catching 21/21 benign
lines and only 1 of 19 actual attacks. In security terms that is the worst possible bias --
it waves brute-force, SQLi, traversal, and reverse-shell lines through as safe. "55%
accuracy" hides a 5%-recall detector.

**A tiny adapter fixed exactly that axis.** Post-tune, suspicious recall went 1/19 -> 19/19
while benign stayed 21/21 (zero false positives). Tuning under half a percent of the
weights, on CPU, in the time it takes to get coffee, flipped the model from useless to
perfect on this test set.

**The cost/benefit here is the real headline.** No GPU, no cloud, 8.7 MB of trained weights
sitting on top of a frozen 0.5B base. This is the case for LoRA in one experiment: you do
not need to touch the base model or its footprint to specialize it for a narrow task.

## Caveat

100% is a clean signal, not a production claim. The data is synthetic and format-regular,
and the test lines come from the same generators as the training lines, so the adapter is
being asked to recognize patterns it has seen the shape of. It proves the adapter learned
*these* patterns cleanly; it does not prove generalization to real, messy, never-before-seen
log formats. The near-zero training loss also means it largely memorized 160 examples -- fine
for this demo, but the honest next step is a held-out set of hand-written or captured
production logs that share no template with the training data.

## Files

```
make_dataset.py        # generate logs.jsonl (200 labeled lines)
baseline.py            # split + zero-shot base-model eval
train_lora.py          # PEFT LoRA fine-tune -> adapter/
evaluate.py            # base + adapter eval on the same test set
logs.jsonl             # full dataset
train.jsonl test.jsonl # 80/20 split (seed 42)
adapter/               # the trained LoRA adapter (8.7 MB)
*_output.txt           # captured console runs for each step
```

The full Qwen2.5-0.5B base model is not included here (~1 GB); pull it separately and point
the scripts at `~/lora/base`.
