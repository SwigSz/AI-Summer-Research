"""Summarise a red-team run into a model-by-model comparison.

Reads three logs and prints (and writes) a report:
  logs/attacker_runs.jsonl        outcomes per LLM attack (attacked/refused/error)
  logs/honeypot_classified.jsonl  each call's intent, with its source tag
  logs/honeytokens.json           fake credentials that were handed out

Output goes to stdout and to reports/summary.md so it can drop straight into
a writeup.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
OUT_DIR = BASE_DIR / "reports"

INTENTS = ["reconnaissance", "data_exfiltration", "privilege_escalation",
           "tool_poisoning_attempt", "benign"]


def load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def model_of(source: dict | None) -> str:
    """Map a honeypot event's source tag back to the attacking model."""
    if not source:
        return "unknown"
    name = source.get("client_name", "") or ""
    ver = source.get("client_version", "") or ""
    if name.startswith("redteam-llm/"):
        return ver or "llm(unknown-model)"
    if name.startswith("redteam/"):
        return "scripted"
    return name or "unknown"


def md_table(headers: list, rows: list) -> str:
    line = lambda cells: "| " + " | ".join(str(c) for c in cells) + " |"
    out = [line(headers), line(["---"] * len(headers))]
    out += [line(r) for r in rows]
    return "\n".join(out)


def build_report() -> str:
    runs = load_jsonl(LOG_DIR / "attacker_runs.jsonl")
    classified = load_jsonl(LOG_DIR / "honeypot_classified.jsonl")
    tokens = {}
    tf = LOG_DIR / "honeytokens.json"
    if tf.exists():
        try:
            tokens = json.loads(tf.read_text())
        except Exception:
            tokens = {}

    # ---- LLM attack outcomes (from attacker_runs) --------------------------
    by_model_runs = defaultdict(Counter)      # model -> outcome counts
    by_model_calls = Counter()                # model -> total tool calls
    for r in runs:
        m = r.get("model", "unknown")
        by_model_runs[m][r.get("outcome", "?")] += 1
        by_model_calls[m] += r.get("tool_calls", 0) or 0

    outcome_rows = []
    for m in sorted(by_model_runs):
        c = by_model_runs[m]
        total = sum(c.values())
        outcome_rows.append([
            m, total, c.get("attacked", 0), c.get("refused", 0),
            c.get("error", 0), by_model_calls[m],
        ])

    # ---- Intent breakdown (from classified events, joined by source) -------
    by_model_intent = defaultdict(Counter)
    for e in classified:
        m = model_of(e.get("source"))
        by_model_intent[m][e.get("intent", "unknown")] += 1

    intent_rows = []
    for m in sorted(by_model_intent):
        c = by_model_intent[m]
        exfil = "yes" if c.get("data_exfiltration", 0) else "no"
        intent_rows.append([m] + [c.get(i, 0) for i in INTENTS] + [exfil])

    # ---- Totals ------------------------------------------------------------
    total_events = len(classified)
    total_threats = sum(1 for e in classified
                        if e.get("intent") in INTENTS[:4])  # everything but benign

    lines = ["# Honeypot red-team summary", ""]
    lines.append(f"- classified events: **{total_events}**")
    lines.append(f"- threat events (non-benign): **{total_threats}**")
    lines.append(f"- honeytokens issued (tracked tripwires): **{len(tokens)}**")
    lines.append(f"- LLM attack runs recorded: **{len(runs)}**")
    lines.append("")

    lines.append("## LLM attack outcomes")
    lines.append("Did the model take the bait, given its attack prompt?")
    lines.append("")
    lines.append(md_table(
        ["model", "runs", "attacked", "refused", "error", "tool calls"],
        outcome_rows) if outcome_rows else "_no LLM runs logged yet_")
    lines.append("")

    lines.append("## Intent breakdown per attacker")
    lines.append("Classifier labels for the calls each source actually made.")
    lines.append("")
    lines.append(md_table(
        ["source", *INTENTS, "exfiltrated?"],
        intent_rows) if intent_rows else "_no classified events yet — run classify.py_")
    lines.append("")

    if tokens:
        lines.append("## Honeytokens (tripwires)")
        lines.append("If any of these strings appears outside this honeypot, "
                     "it was exfiltrated and used.")
        lines.append("")
        rows = [[v.get("service"), v.get("field"), k[:12] + "...", v.get("last_session", "")[:8]]
                for k, v in tokens.items()]
        lines.append(md_table(["service", "field", "token", "last session"], rows))
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    report = build_report()
    print(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "summary.md"
    out.write_text(report)
    print(f"\n(written to {out.relative_to(BASE_DIR)})")


if __name__ == "__main__":
    main()
