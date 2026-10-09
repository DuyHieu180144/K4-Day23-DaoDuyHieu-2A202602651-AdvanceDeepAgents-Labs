"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent
from model import make_model
from sandbox import download, open_sandbox, upload

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    if not topic:
        return "topic"
    s = topic.strip().lower()
    s = re.sub(r"[^\w]+", "-", s).strip("-")
    s = s[:60].rstrip("-")
    return s if s else "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return (
        f"Please perform an in-depth literature research and produce a comprehensive survey report on the topic:\n"
        f"'{topic}'\n\n"
        f"Follow all instructions in your system prompt:\n"
        f"1. Plan with write_todos and split into >= 3 sub-questions.\n"
        f"2. Delegate to researcher subagents in parallel with full context.\n"
        f"3. Verify notes, merge into /tmp/work/research/sources.json (ensuring at least 3 source families: arxiv, hf-daily, hf-search, web).\n"
        f"4. Write the report body to /tmp/work/report/report.md without ## References (following REPORT_TEMPLATE.md).\n"
        f"5. Run /tmp/work/research/finalize_citations.py using execute to regenerate References and update sources.json.\n"
        f"6. Run /tmp/work/research/check_citations.py using execute and fix any issues until it outputs OK.\n"
        f"7. Have citation-checker spot-check sample claims."
    )


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}."""
    tool_counts = Counter()
    subagent_calls = 0
    input_tokens = 0
    output_tokens = 0

    for msg in messages:
        calls = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            calls = msg.tool_calls
        elif isinstance(msg, dict):
            calls = msg.get("tool_calls", [])

        for call in calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                tool_counts[name] += 1
                if name == "task":
                    subagent_calls += 1

        usage = None
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
        elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
            usage = msg.response_metadata.get("token_usage") or msg.response_metadata.get("usage")
        elif isinstance(msg, dict):
            usage = msg.get("usage_metadata") or msg.get("response_metadata", {}).get("token_usage")

        if usage:
            inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
            input_tokens += int(inp)
            output_tokens += int(out)

    return {
        "model": model_name,
        "elapsed_s": round(float(elapsed), 1),
        "subagent_calls": subagent_calls,
        "tool_calls": dict(tool_counts),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
        },
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes:
        raise RuntimeError(f"Report is missing or empty at {REPORT_PATH}")
    if not sources_bytes:
        raise RuntimeError(f"Sources file is missing at {SOURCES_PATH}")

    report_text = report_bytes.decode("utf-8", errors="replace")
    if not report_text.strip():
        raise RuntimeError("Report content is empty")

    try:
        sources = json.loads(sources_bytes.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON in sources file: {exc}")

    if not isinstance(sources, list) or not sources:
        raise RuntimeError("sources.json is empty or not a list")

    families = sorted(list({
        s.get("source") for s in sources if isinstance(s, dict) and s.get("source")
    }))

    slug = slugify(topic)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    meta_data = {
        "topic": topic,
        **summarize(messages, elapsed, model_name),
        "n_sources": len(sources),
        "source_families": families,
    }

    report_file = reports_path / f"{slug}.md"
    sources_file = reports_path / f"{slug}.sources.json"
    meta_file = reports_path / f"{slug}.meta.json"

    sources_file.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_file.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")
    report_file.write_text(report_text, encoding="utf-8")

    return report_file


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic or not topic.strip():
        print("Usage: python research.py \"<topic>\"", file=sys.stderr)
        return 2

    topic = topic.strip()
    model = make_model()
    model_name = getattr(model, "model_name", None) or os.getenv("LAB_MODEL", "gpt-4o-mini")
    start = time.monotonic()

    with open_sandbox() as backend:
        backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
        upload(backend, {
            VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
            FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
        })
        agent = build_lead_agent(backend, model)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": build_prompt(topic)}]},
            config={"recursion_limit": 1000},
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        elapsed = time.monotonic() - start
        try:
            report_path = save_outputs(backend, topic, messages, elapsed, model_name)
        except RuntimeError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    print(f"Report saved to: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
