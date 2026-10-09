import json
import pytest
from check_citations import check


def test_empty_sources():
    problems = check("# Title\n\nBody [1]\n\n## References\n[1] Title. url. https://arxiv.org/abs/1234.5678", [])
    assert any("no sources" in p.lower() for p in problems)


def test_invalid_source_entry():
    sources = [{"n": "one", "url": "https://arxiv.org/abs/1234.5678"}]
    problems = check("# Title\n\nBody [1]\n\n## References\n[1] Title. url. https://arxiv.org/abs/1234.5678", sources)
    assert any("not an int" in p.lower() or "integer" in p.lower() for p in problems)


def test_invalid_source_url():
    sources = [{"n": 1, "url": "ftp://example.com"}]
    problems = check("# Title\n\nBody [1]\n\n## References\n[1] Title. url. ftp://example.com", sources)
    assert any("url" in p.lower() for p in problems)


def test_duplicate_source_url():
    sources = [
        {"n": 1, "url": "https://arxiv.org/abs/1234.5678"},
        {"n": 2, "url": "https://arxiv.org/abs/1234.5678"},
    ]
    report = "# Title\n\nBody [1][2]\n\n## References\n[1] A. https://arxiv.org/abs/1234.5678\n[2] B. https://arxiv.org/abs/1234.5678"
    problems = check(report, sources)
    assert any("duplicate" in p.lower() for p in problems)


def test_missing_references_heading():
    sources = [{"n": 1, "url": "https://arxiv.org/abs/1234.5678"}]
    problems = check("# Title\n\nBody [1]\n\n[1] Title. url. https://arxiv.org/abs/1234.5678", sources)
    assert any("references" in p.lower() for p in problems)


def test_valid_report():
    sources = [
        {"n": 1, "url": "https://arxiv.org/abs/1234.5678", "title": "Paper 1", "source": "arxiv"},
        {"n": 2, "url": "https://huggingface.co/papers/2345.6789", "title": "Paper 2", "source": "hf-search"},
    ]
    report = (
        "# Survey\n\n"
        "## TL;DR\n"
        "We discuss world models [1] and reasoning [2].\n\n"
        "## References\n"
        "[1] Paper 1. arxiv. https://arxiv.org/abs/1234.5678 (2025-01-01)\n"
        "[2] Paper 2. hf-search. https://huggingface.co/papers/2345.6789 (2025-01-02)\n"
    )
    problems = check(report, sources)
    assert problems == []


def test_grouped_citations_expansion():
    sources = [
        {"n": 1, "url": "https://arxiv.org/abs/1234.5678"},
        {"n": 2, "url": "https://arxiv.org/abs/2345.6789"},
        {"n": 3, "url": "https://arxiv.org/abs/3456.7890"},
    ]
    report = (
        "# Survey\n\n"
        "## TL;DR\n"
        "Recent progress is noted in [1, 2] and [1-3].\n\n"
        "## References\n"
        "[1] A. https://arxiv.org/abs/1234.5678\n"
        "[2] B. https://arxiv.org/abs/2345.6789\n"
        "[3] C. https://arxiv.org/abs/3456.7890\n"
    )
    problems = check(report, sources)
    assert problems == []


def test_code_block_and_link_citations_ignored():
    sources = [{"n": 1, "url": "https://arxiv.org/abs/1234.5678"}]
    # Body has code block with [99] and markdown link [98](http://foo)
    report = (
        "# Survey\n\n"
        "Here is real citation [1].\n"
        "```python\nx = [99]\n```\n"
        "And a link [98](https://example.com)\n\n"
        "## References\n"
        "[1] Title. https://arxiv.org/abs/1234.5678\n"
    )
    problems = check(report, sources)
    assert problems == []


def test_uncited_source_and_missing_source():
    sources = [
        {"n": 1, "url": "https://arxiv.org/abs/1234.5678"},
        {"n": 2, "url": "https://arxiv.org/abs/2345.6789"},
    ]
    # Body cites [1] and [3], but not [2]
    report = (
        "# Survey\n\n"
        "Citation [1] and [3].\n\n"
        "## References\n"
        "[1] A. https://arxiv.org/abs/1234.5678\n"
        "[2] B. https://arxiv.org/abs/2345.6789\n"
    )
    problems = check(report, sources)
    assert any("[3]" in p for p in problems)
    assert any("[2]" in p for p in problems)

