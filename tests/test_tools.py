import json
import pytest
from unittest.mock import MagicMock, patch
import httpx

from tools import (
    RetryableError,
    with_retry,
    arxiv_search,
    hf_daily_papers,
    hf_search_papers,
    web_search,
    web_fetch,
    SOURCE_TOOLS,
)


def test_with_retry_succeeds_first_try():
    calls = 0
    def op():
        nonlocal calls
        calls += 1
        return "success"
    res = with_retry(op, attempts=3, base=0.01)
    assert res == "success"
    assert calls == 1


def test_with_retry_retries_on_retryable_error():
    calls = 0
    def op():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RetryableError("transient", retry_after=0.01)
        return "ok"
    res = with_retry(op, attempts=4, base=0.01)
    assert res == "ok"
    assert calls == 3


def test_with_retry_fails_after_max_attempts():
    calls = 0
    def op():
        nonlocal calls
        calls += 1
        raise RetryableError("permanent failure", retry_after=0.01)
    with pytest.raises(RetryableError):
        with_retry(op, attempts=3, base=0.01)
    assert calls == 3


def test_with_retry_does_not_retry_non_retryable():
    calls = 0
    def op():
        nonlocal calls
        calls += 1
        raise ValueError("programming error")
    with pytest.raises(ValueError):
        with_retry(op, attempts=3, base=0.01)
    assert calls == 1


def test_arxiv_search_empty_query():
    res = arxiv_search.invoke({"query": "??!! @@", "max_results": 5})
    assert res == "NO RESULTS"


def test_source_tools_registered():
    names = [t.name for t in SOURCE_TOOLS]
    assert names == ["arxiv_search", "hf_daily_papers", "hf_search_papers", "web_search", "web_fetch"]

