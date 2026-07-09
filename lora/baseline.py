#!/usr/bin/env python3
"""Zero-shot baseline for the log-classification task.

Loads logs.jsonl, shuffles (seed 42), splits 80/20 into train.jsonl and
test.jsonl, then prompts the base Qwen2.5-0.5B-Instruct model to label each
test line benign/suspicious with no fine-tuning. Prints accuracy and a
confusion count. This is the pre-LoRA reference number.
"""

import json
import random
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = Path.home() / "lora"
DATA_PATH = BASE / "logs.jsonl"
TRAIN_PATH = BASE / "train.jsonl"
TEST_PATH = BASE / "test.jsonl"
MODEL_PATH = BASE / "base"
SEED = 42
LABELS = ("benign", "suspicious")

SYSTEM = (
    "You are a security log classifier. Classify each log line as exactly "
    "one word: either 'benign' or 'suspicious'. Answer with only that one "
    "word, nothing else."
)


def load_rows(path):
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_rows(path, rows):
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def parse_label(text):
    """First label word that appears in the model output wins."""
    low = text.lower()
    hits = [(low.find(lbl), lbl) for lbl in LABELS if lbl in low]
    if hits:
        return min(hits)[1]
    return None


def main():
    rows = load_rows(DATA_PATH)
    random.Random(SEED).shuffle(rows)
    split = int(len(rows) * 0.8)
    train, test = rows[:split], rows[split:]
    save_rows(TRAIN_PATH, train)
    save_rows(TEST_PATH, test)
    print(f"loaded {len(rows)}  ->  train {len(train)}  test {len(test)}")

    tok = AutoTokenizer.from_pretrained(MODEL_PATH)

    def load_on(device):
        m = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            dtype=(torch.bfloat16 if device == "cuda" else torch.float32),
        ).to(device)
        m.eval()
        # warmup probe: some GPU kernel paths on this box fail at generate()
        # time, so verify the device actually works before trusting it.
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

    # counts[true_label][correct?]
    counts = {lbl: {"right": 0, "wrong": 0} for lbl in LABELS}
    unparsed = 0
    correct = 0

    for i, r in enumerate(test):
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Log line:\n{r['text']}\n\nLabel:"},
        ]
        prompt = tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
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
