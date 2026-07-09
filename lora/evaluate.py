#!/usr/bin/env python3
"""Evaluate the LoRA-tuned model on the held-out test set.

Same as baseline.py, but loads ~/lora/base with the ~/lora/adapter LoRA
applied (PEFT), and uses the exact instruction prompt format from training
("Classify this log line as benign or suspicious:\n<text>"). Runs on the same
test.jsonl. Prints accuracy and the per-label confusion table so the number
is directly comparable to the pre-tuning baseline.
"""

import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = Path.home() / "lora"
TEST_PATH = BASE / "test.jsonl"
MODEL_PATH = BASE / "base"
ADAPTER_PATH = BASE / "adapter"
LABELS = ("benign", "suspicious")

INSTRUCTION = "Classify this log line as benign or suspicious:"


def load_rows(path):
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_label(text):
    """First label word that appears in the model output wins."""
    low = text.lower()
    hits = [(low.find(lbl), lbl) for lbl in LABELS if lbl in low]
    if hits:
        return min(hits)[1]
    return None


def main():
    test = load_rows(TEST_PATH)
    print(f"test lines: {len(test)}")

    tok = AutoTokenizer.from_pretrained(MODEL_PATH)

    def load_on(device):
        base = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            dtype=(torch.bfloat16 if device == "cuda" else torch.float32),
        )
        m = PeftModel.from_pretrained(base, str(ADAPTER_PATH)).to(device)
        m.eval()
        # warmup probe: the GPU Triton path fails to compile on this box
        # (missing python3-dev headers), so verify before trusting cuda.
        probe = tok("hi", return_tensors="pt").to(device)
        with torch.no_grad():
            m.generate(**probe, max_new_tokens=1, do_sample=False,
                       pad_token_id=tok.eos_token_id)
        return m

    device, model = "cpu", None
    if torch.cuda.is_available():
        try:
            model = load_on("cuda")
            device = "cuda"
        except Exception as exc:
            print(f"cuda probe failed ({type(exc).__name__}), "
                  f"falling back to cpu")
    if model is None:
        model = load_on("cpu")
    print(f"device: {device}")

    counts = {lbl: {"right": 0, "wrong": 0} for lbl in LABELS}
    unparsed = 0
    correct = 0

    for i, r in enumerate(test):
        user = f"{INSTRUCTION}\n{r['text']}"
        prompt = tok.apply_chat_template(
            [{"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=5, do_sample=False,
                pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0][inputs["input_ids"].shape[1]:],
                         skip_special_tokens=True)
        pred = parse_label(gen)
        true = r["label"]
        if pred is None:
            unparsed += 1
            counts[true]["wrong"] += 1
        elif pred == true:
            correct += 1
            counts[true]["right"] += 1
        else:
            counts[true]["wrong"] += 1
        print(f"[{i + 1:3d}/{len(test)}] true={true:10s} "
              f"pred={str(pred):10s} raw={gen.strip()[:30]!r}", flush=True)

    acc = correct / len(test) if test else 0.0
    print(f"\naccuracy: {correct}/{len(test)} = {acc * 100:.1f}%")
    print(f"unparsed (no label word in output): {unparsed}")
    print("\nconfusion (per true label):")
    print(f"{'label':12s} {'right':>6s} {'wrong':>6s} {'total':>6s}")
    for lbl in LABELS:
        r, w = counts[lbl]["right"], counts[lbl]["wrong"]
        print(f"{lbl:12s} {r:>6d} {w:>6d} {r + w:>6d}")


if __name__ == "__main__":
    main()
