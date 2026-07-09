#!/usr/bin/env python3
"""LoRA fine-tune Qwen2.5-0.5B-Instruct to classify a log line benign/suspicious.

Each train.jsonl example becomes an instruction prompt with the label as the
completion; loss is masked to the completion tokens only, so the model learns
to emit the label, not to reconstruct the prompt. Adapter saved to
~/lora/adapter. CPU by default (the GPU Triton path needs python3-dev headers
that are not installed here).
"""

import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments)

BASE = Path.home() / "lora"
MODEL_PATH = BASE / "base"
TRAIN_PATH = BASE / "train.jsonl"
ADAPTER_OUT = BASE / "adapter"
SEED = 42
EPOCHS = 3
BATCH_SIZE = 4
MAX_LEN = 256

INSTRUCTION = "Classify this log line as benign or suspicious:"


def load_rows(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def build_example(tok, text, label):
    """Full sequence = chat(instruction+text) + label; loss only on label."""
    user = f"{INSTRUCTION}\n{text}"
    prompt = tok.apply_chat_template(
        [{"role": "user", "content": user}],
        tokenize=False, add_generation_prompt=True)
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    completion = f"{label}{tok.eos_token}"
    completion_ids = tok(completion, add_special_tokens=False)["input_ids"]

    input_ids = (prompt_ids + completion_ids)[:MAX_LEN]
    labels = ([-100] * len(prompt_ids) + completion_ids)[:MAX_LEN]
    return {"input_ids": input_ids, "labels": labels,
            "attention_mask": [1] * len(input_ids)}


class Collator:
    def __init__(self, pad_id):
        self.pad_id = pad_id

    def __call__(self, batch):
        maxlen = max(len(b["input_ids"]) for b in batch)
        ids, labs, mask = [], [], []
        for b in batch:
            pad = maxlen - len(b["input_ids"])
            ids.append(b["input_ids"] + [self.pad_id] * pad)
            labs.append(b["labels"] + [-100] * pad)
            mask.append(b["attention_mask"] + [0] * pad)
        return {
            "input_ids": torch.tensor(ids),
            "labels": torch.tensor(labs),
            "attention_mask": torch.tensor(mask),
        }


def main():
    torch.manual_seed(SEED)
    rows = load_rows(TRAIN_PATH)
    print(f"train examples: {len(rows)}")

    tok = AutoTokenizer.from_pretrained(MODEL_PATH)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    dataset = [build_example(tok, r["text"], r["label"]) for r in rows]

    model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, dtype=torch.float32)
    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    args = TrainingArguments(
        output_dir=str(BASE / "trainer_out"),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        seed=SEED,
        use_cpu=True,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        data_collator=Collator(tok.pad_token_id),
    )

    start = time.time()
    trainer.train()
    elapsed = time.time() - start

    ADAPTER_OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_OUT))
    tok.save_pretrained(str(ADAPTER_OUT))
    print(f"\nsaved adapter to {ADAPTER_OUT}")
    print(f"train time: {elapsed:.1f}s "
          f"({elapsed / 60:.1f} min) for {EPOCHS} epochs")


if __name__ == "__main__":
    main()
