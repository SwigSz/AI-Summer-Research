#!/usr/bin/env python3
# =============================================================================
# bench_harness.py  -  local Ollama benchmark, standard library only.
#
# Hand-copy this single file onto each machine and run it locally.
# No git, no pip, no downloads. Needs only a bare Python 3 and Ollama running.
#
# Run commands:
#   macOS/Linux:            python3 bench_harness.py
#   Windows:                py bench_harness.py
#   Surface VRAM-wall line: py bench_harness.py --models qwen2.5:14b
#
# Flags: --models llama3.2:3b,qwen2.5:7b   --temp 0
#
# Produces two files next to this script, both named with the hostname:
#   comparison_<hostname>.csv   raw rows, appended each run
#   results_<hostname>.md       clean paste-ready summary, overwritten each run
# Open results_<hostname>.md (also printed to the terminal) and paste into Claude.
# =============================================================================

import argparse
import csv
import json
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OLLAMA_URL = "http://localhost:11434"
GENERATE = OLLAMA_URL + "/api/generate"
TAGS = OLLAMA_URL + "/api/tags"

NUM_CTX = 8192
NUM_PREDICT = 256  # cap decode so runs are bounded and comparable

DEFAULT_MODELS = ["llama3.2:3b", "qwen2.5:7b"]

# Fixed prompt suite, tagged.
_LONG_PARA = (
    "The retrieval pipeline ingests documents, chunks them on semantic "
    "boundaries, embeds each chunk, and stores the vectors with source "
    "metadata. At query time the question is embedded with the same model, the "
    "top-k nearest chunks are retrieved by cosine similarity, and those chunks "
    "are concatenated into the context window ahead of the instruction. "
)
_CURATOR_BLOB = (
    "Anthropic released a new Claude model citing agentic coding gains. A "
    "critical CVE was disclosed in a vLLM serving path allowing remote memory "
    "disclosure; a patch landed within 48 hours. NVIDIA shipped a driver update "
    "improving unified-memory throughput. A supply-chain advisory flagged a "
    "typosquatted package mimicking a LangChain integration. A research group "
    "published prompt-injection defenses for MCP servers that intercept tool "
    "calls before execution."
)
PROMPTS = {
    "short": "In one sentence, explain what a vector database is.",
    "medium": (
        "You are a senior infrastructure engineer. Explain how to choose between "
        "running a 7B model on a single consumer GPU versus a small "
        "unified-memory box. Cover memory footprint, decode throughput, "
        "batching, and quantization trade-offs in two short paragraphs."
    ),
    "long": (
        "You are reviewing the following system description.\n\n"
        + (_LONG_PARA * 22)
        + "\n\nList the three most likely failure modes and one mitigation each."
    ),
    "summarize": (
        "Summarize the following AI-news items into a tight 4-bullet digest for a "
        "security-minded reader, leading with anything security-relevant:\n\n"
        + _CURATOR_BLOB
    ),
}

CSV_COLUMNS = [
    "machine", "model", "prompt_tag", "temp", "decode_tps", "prefill_tps",
    "ttft_ms", "mem_mb", "mem_method", "ctx", "ts", "status",
]


# --------------------------------------------------------------------------- #
# Machine facts
# --------------------------------------------------------------------------- #

def os_arch() -> str:
    return f"{platform.system()} {platform.machine()}"


def total_ram_gb() -> str:
    system = platform.system()
    try:
        if system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = float(line.split()[1])
                        return f"{kb / 1024 / 1024:.1f} GB"
        elif system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                return f"{int(out.stdout.strip()) / 1024**3:.1f} GB"
        elif system == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return f"{ms.ullTotalPhys / 1024**3:.1f} GB"
    except Exception:
        pass
    return "unknown"


# --------------------------------------------------------------------------- #
# Ollama helpers
# --------------------------------------------------------------------------- #

def ollama_up() -> bool:
    try:
        with urllib.request.urlopen(TAGS, timeout=3) as resp:
            resp.read()
        return True
    except Exception:
        return False


def model_present(model: str) -> bool:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True,
                             text=True, timeout=20)
    except Exception:
        return False
    if out.returncode != 0:
        return False
    for line in out.stdout.splitlines()[1:]:
        cols = line.split()
        if cols and cols[0] == model:
            return True
    return model in out.stdout


def ensure_model(model: str) -> bool:
    if model_present(model):
        print(f"  {model}: present")
        return True
    print(f"  {model}: not found, pulling ...")
    try:
        r = subprocess.run(["ollama", "pull", model])  # inherit stdio: shows bar
    except FileNotFoundError:
        print("  ollama CLI not found on PATH")
        return False
    if r.returncode != 0:
        print(f"  {model}: pull failed")
        return False
    return True


def _parse_size_to_mb(size_str: str) -> float | None:
    parts = size_str.split()
    try:
        if len(parts) == 1:
            return round(float(parts[0]), 1)
        val = float(parts[0])
    except ValueError:
        return None
    factor = {"KB": 1 / 1024, "KIB": 1 / 1024, "MB": 1, "MIB": 1,
              "GB": 1024, "GIB": 1024, "TB": 1024 * 1024, "TIB": 1024 * 1024}
    f = factor.get(parts[1].upper())
    return round(val * f, 1) if f else None


def ollama_ps_size_mb(model: str) -> float | None:
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True,
                             text=True, timeout=15)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    import re
    for line in out.stdout.splitlines()[1:]:
        if not line.strip():
            continue
        fields = re.split(r"\s{2,}", line.strip())
        if len(fields) < 3:
            continue
        name = fields[0]
        if name == model or name.startswith(model) or model.startswith(name):
            return _parse_size_to_mb(fields[2])
    return None


def warmup(model: str, temp: float) -> None:
    body = json.dumps({
        "model": model, "prompt": "warmup", "stream": False,
        "options": {"num_ctx": NUM_CTX, "temperature": temp, "num_predict": 1},
    }).encode("utf-8")
    req = urllib.request.Request(GENERATE, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp.read()
    except Exception as exc:
        print(f"  warmup error: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# One benchmark run
# --------------------------------------------------------------------------- #

def run_one(model: str, tag: str, prompt: str, temp: float, machine: str,
            mem_mb: float | None) -> dict:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": True,
        "options": {"num_ctx": NUM_CTX, "temperature": temp,
                    "num_predict": NUM_PREDICT},
    }).encode("utf-8")
    req = urllib.request.Request(GENERATE, data=body,
                                 headers={"Content-Type": "application/json"})
    final: dict = {}
    ttft_ms: float | None = None
    error: str | None = None
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - t0) * 1000.0
                obj = json.loads(line)
                if obj.get("done"):
                    final = obj
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    def tps(ck: str, dk: str) -> float | None:
        c, d = final.get(ck), final.get(dk)
        return round(c / (d / 1e9), 2) if c and d else None

    status = "ok" if (error is None and final.get("eval_count")) else "fail"
    return {
        "machine": machine, "model": model, "prompt_tag": tag, "temp": temp,
        "decode_tps": tps("eval_count", "eval_duration"),
        "prefill_tps": tps("prompt_eval_count", "prompt_eval_duration"),
        "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
        "mem_mb": mem_mb, "mem_method": "ollama-ps", "ctx": NUM_CTX,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status, "error": error,
    }


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #

def safe_host(hostname: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "_", hostname)


def append_csv(path: Path, rows: list[dict]) -> None:
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def _fmt(v) -> str:
    return "n/a" if v is None else str(v)


def _mean(vals: list) -> float | None:
    nums = [v for v in vals if v is not None]
    return round(sum(nums) / len(nums), 2) if nums else None


def build_md(hostname: str, rows: list[dict], models: list[str]) -> str:
    out = []
    out.append(f"# bench results: {hostname}")
    out.append("")
    out.append(f"- host: `{hostname}`")
    out.append(f"- os/arch: `{os_arch()}`")
    out.append(f"- total ram: `{total_ram_gb()}`")
    out.append(f"- ctx: `{NUM_CTX}`")
    out.append("")
    cols = ["model", "prompt_tag", "temp", "decode_tps", "prefill_tps",
            "ttft_ms", "mem_mb", "ctx", "status"]
    out.append("| " + " | ".join(cols) + " |")
    out.append("|" + "|".join("---" for _ in cols) + "|")
    for r in rows:
        out.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
    out.append("")
    out.append("## stats per model (status=ok only)")
    out.append("")
    for m in models:
        ok = [r for r in rows if r["model"] == m and r["status"] == "ok"]
        if not ok:
            out.append(f"- `{m}`: no ok runs")
            continue
        dec = _mean([r["decode_tps"] for r in ok])
        pre = _mean([r["prefill_tps"] for r in ok])
        tt = _mean([r["ttft_ms"] for r in ok])
        mem = ok[0]["mem_mb"]
        out.append(f"- `{m}`: decode {_fmt(dec)} tps, prefill {_fmt(pre)} tps, "
                   f"ttft {_fmt(tt)} ms, mem {_fmt(mem)} mb")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Local Ollama benchmark (stdlib only).")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS))
    p.add_argument("--temp", type=float, default=0.0)
    args = p.parse_args(argv)

    if not ollama_up():
        print("Ollama is not reachable at http://localhost:11434.")
        print("Start it first (run `ollama serve`, or open the Ollama app), "
              "then re-run this script.")
        return 1

    machine = socket.gethostname()
    host = safe_host(machine)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    csv_path = BASE_DIR / f"comparison_{host}.csv"
    md_path = BASE_DIR / f"results_{host}.md"

    print(f"machine={machine}  os/arch={os_arch()}  ram={total_ram_gb()}")
    print(f"models={models}  temp={args.temp}  ctx={NUM_CTX}")

    rows: list[dict] = []
    for model in models:
        if not ensure_model(model):
            print(f"  {model}: skipped (not available)")
            continue
        print(f"  warming up {model} ...")
        warmup(model, args.temp)
        mem_mb = ollama_ps_size_mb(model)
        print(f"  {model}: mem_mb={mem_mb} (ollama-ps)")
        for tag, prompt in PROMPTS.items():
            print(f"  running {model} / {tag} ...")
            row = run_one(model, tag, prompt, args.temp, machine, mem_mb)
            rows.append(row)
            if row["status"] != "ok":
                print(f"    fail: {row['error'] or 'no eval_count'}")

    if not rows:
        print("No runs completed. Nothing written.")
        return 1

    append_csv(csv_path, rows)
    md = build_md(machine, rows, models)
    md_path.write_text(md, encoding="utf-8")

    print()
    print(md)
    print(f"appended rows -> {csv_path}")
    print(f"wrote summary -> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
