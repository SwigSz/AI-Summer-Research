"""Classify honeypot events by attacker intent.

Reads new lines from logs/honeypot_events.jsonl, asks a local Ollama model
(default qwen2.5:7b) to label each one, and appends the verdict to
logs/honeypot_classified.jsonl. Every model call is logged to
logs/classify_model_calls.jsonl for observability.

Only unseen events are processed: a byte offset is kept in
logs/.classify_offset so reruns pick up where the last one stopped.

Model call resolution, in order:
  1. an O20-style wrapper — `from o20 import call_model` — if importable
  2. Ollama's REST API at $OLLAMA_HOST (default http://localhost:11434)
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
EVENTS_FILE = LOG_DIR / "honeypot_events.jsonl"
OUT_FILE = LOG_DIR / "honeypot_classified.jsonl"
CALLS_FILE = LOG_DIR / "classify_model_calls.jsonl"
OFFSET_FILE = LOG_DIR / ".classify_offset"

LABELS = [
    "benign",
    "reconnaissance",
    "tool_poisoning_attempt",
    "data_exfiltration",
    "privilege_escalation",
]

SYSTEM_PROMPT = (
    "You are a security analyst reviewing calls made to a honeypot MCP server. "
    "Every tool is a decoy (read_file, query_database, get_api_keys, "
    "send_notification). Classify the intent behind a single tool call into "
    "exactly one label:\n"
    "- benign: ordinary, non-probing use\n"
    "- reconnaissance: mapping the system, listing, reading configs to learn structure\n"
    "- tool_poisoning_attempt: injecting instructions/payloads to alter behavior\n"
    "- data_exfiltration: pulling credentials/PII or routing data outward "
    "(e.g. get_api_keys, send_notification to external targets)\n"
    "- privilege_escalation: seeking admin access, keys, or higher-privileged paths\n"
    "Respond ONLY with JSON: "
    '{"intent": "<label>", "confidence": <0-1>, "reasoning": "<one sentence>"}'
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_call(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with CALLS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# --------------------------------------------------------------- model call

def _via_wrapper(prompt: str, model: str) -> str | None:
    try:
        from o20 import call_model  # user's observability wrapper
    except Exception:
        return None
    return call_model(model=model, system=SYSTEM_PROMPT, prompt=prompt, format="json")


def _via_ollama(prompt: str, model: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    body = json.dumps({
        "model": model,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    req = urllib.request.Request(f"{host}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["message"]["content"]


def call(prompt: str, model: str) -> tuple[str, str]:
    """Return (raw_response, backend). Tries the wrapper, then Ollama."""
    raw = _via_wrapper(prompt, model)
    if raw is not None:
        return raw, "o20"
    return _via_ollama(prompt, model), "ollama"


# --------------------------------------------------------------- classify

def classify_event(event: dict, model: str) -> dict:
    prompt = "Tool call to classify:\n" + json.dumps(
        {"tool": event.get("tool"), "arguments": event.get("arguments"),
         "source": event.get("source")}, indent=2)

    started = time.monotonic()
    call_log = {"timestamp": now(), "model": model, "session_id": event.get("session_id"),
                "tool": event.get("tool")}
    try:
        raw, backend = call(prompt, model)
        parsed = json.loads(raw)
        intent = parsed.get("intent")
        if intent not in LABELS:
            intent, parsed = "unknown", {"intent": "unknown", "raw": parsed}
        call_log.update(backend=backend, ok=True,
                        latency_ms=round((time.monotonic() - started) * 1000))
        log_call(call_log)
        return {
            "classified_at": now(),
            "session_id": event.get("session_id"),
            "tool": event.get("tool"),
            "arguments": event.get("arguments"),
            "source": event.get("source"),
            "event_timestamp": event.get("timestamp"),
            "intent": intent,
            "confidence": parsed.get("confidence"),
            "reasoning": parsed.get("reasoning"),
        }
    except Exception as e:
        call_log.update(ok=False, error=str(e),
                        latency_ms=round((time.monotonic() - started) * 1000))
        log_call(call_log)
        return {
            "classified_at": now(),
            "session_id": event.get("session_id"),
            "tool": event.get("tool"),
            "arguments": event.get("arguments"),
            "source": event.get("source"),
            "event_timestamp": event.get("timestamp"),
            "intent": "error",
            "error": str(e),
        }


def read_new_events() -> tuple[list[dict], int]:
    if not EVENTS_FILE.exists():
        return [], 0
    offset = 0
    if OFFSET_FILE.exists():
        try:
            offset = int(OFFSET_FILE.read_text().strip())
        except Exception:
            offset = 0
    events = []
    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        f.seek(offset)
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        new_offset = f.tell()
    return events, new_offset


def save_offset(offset: int) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset))


def run_once(model: str) -> int:
    events, new_offset = read_new_events()
    if not events:
        return 0
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("a", encoding="utf-8") as out:
        for ev in events:
            result = classify_event(ev, model)
            out.write(json.dumps(result, default=str) + "\n")
            out.flush()
            print(f"[{result['intent']}] {result.get('tool')} "
                  f"session={result.get('session_id', '')[:8]}")
    save_offset(new_offset)
    return len(events)


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify honeypot events by intent.")
    ap.add_argument("--model", default=os.environ.get("HONEYPOT_MODEL", "qwen2.5:7b"))
    ap.add_argument("--follow", action="store_true",
                    help="keep running, polling for new events")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="seconds between polls in --follow mode")
    ap.add_argument("--reset", action="store_true",
                    help="reprocess from the start (clears the offset)")
    args = ap.parse_args()

    if args.reset and OFFSET_FILE.exists():
        OFFSET_FILE.unlink()

    if args.follow:
        print(f"following {EVENTS_FILE} with model {args.model} (ctrl-c to stop)")
        try:
            while True:
                n = run_once(args.model)
                if n == 0:
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nstopped")
    else:
        n = run_once(args.model)
        print(f"classified {n} event(s) -> {OUT_FILE}")


if __name__ == "__main__":
    main()
