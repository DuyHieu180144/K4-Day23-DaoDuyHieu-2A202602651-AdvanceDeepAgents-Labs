"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"

_GROUP = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")   # [3]  [1, 2]  [1-3]  [2-3]; not [3](link)
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")
_REF_LINE = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
_URL = re.compile(r"https?://\S+")


def _group_numbers(group):
    numbers = []
    for part in re.split(r"\s*,\s*", group):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            numbers.extend(range(a, b + 1) if 0 <= b - a <= 200 else [a, b])
        else:
            numbers.append(int(part))
    return numbers


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []
    if not sources or not isinstance(sources, list):
        return ["no sources in sources.json"]

    if not all(isinstance(e, dict) for e in sources):
        return ["sources.json must be a list of objects"]

    seen_urls = set()
    source_by_n = {}
    source_ns = set()

    for s in sources:
        n = s.get("n")
        if not isinstance(n, int) or isinstance(n, bool):
            problems.append(f"source n={n!r} is not an integer")
            continue

        url = s.get("url")
        if not url or not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source [{n}] url must start with http:// or https://: {url!r}")

        if url:
            if url in seen_urls:
                problems.append(f"duplicate url in sources: {url}")
            seen_urls.add(url)

        source_by_n[n] = s
        source_ns.add(n)

    # 3. Check ## References heading
    matches = list(_REF_HEADING.finditer(report_text))
    if not matches:
        problems.append("missing '## References' section")
        body = report_text
        ref_section = ""
    else:
        body = report_text[:matches[-1].start()]
        ref_section = report_text[matches[-1].end():]

    # 4. Citations in body
    segments = _CODE.split(body)
    cited_numbers = set()
    for i, segment in enumerate(segments):
        if i % 2:  # odd indexes are code blocks or inline code
            continue
        for match in _GROUP.finditer(segment):
            for n in _group_numbers(match.group(1)):
                cited_numbers.add(n)

    for n in sorted(cited_numbers):
        if n not in source_ns:
            problems.append(f"[{n}] cited in body but missing from sources.json")

    for n in sorted(source_ns):
        if n not in cited_numbers:
            problems.append(f"source [{n}] in sources.json is never cited in body")

    # 5. & 6. References section lines
    if matches:
        ref_lines_by_n = {}
        for line in ref_section.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            match = _REF_LINE.match(line_str)
            if match:
                n = int(match.group(1))
                urls = _URL.findall(line_str)
                ref_lines_by_n.setdefault(n, []).append((line_str, urls))

        for n in sorted(source_ns):
            if n not in ref_lines_by_n:
                problems.append(f"missing reference line for source [{n}] in ## References")
            elif len(ref_lines_by_n[n]) > 1:
                problems.append(f"duplicate reference line for source [{n}] in ## References")
            else:
                line_str, urls = ref_lines_by_n[n][0]
                if len(urls) != 1:
                    problems.append(f"reference line [{n}] must contain exactly one URL (found {len(urls)}): {line_str}")
                else:
                    expected_url = source_by_n[n].get("url")
                    found_url = urls[0].rstrip(").,;")
                    exp_clean = expected_url.rstrip(").,;") if expected_url else ""
                    if found_url != exp_clean:
                        problems.append(f"reference line [{n}] url {urls[0]!r} does not match source url {expected_url!r}")

        for n in sorted(ref_lines_by_n):
            if n not in source_ns:
                problems.append(f"reference line [{n}] in ## References is not in sources.json")

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
