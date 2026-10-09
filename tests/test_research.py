import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from research import slugify, build_prompt, summarize, save_outputs


def test_slugify():
    assert slugify("Survey about World Model") == "survey-about-world-model"
    assert slugify("../../evil/path") == "evil-path"
    assert slugify("   ") == "topic"
    assert slugify("") == "topic"
    # long string truncation
    long_t = "a" * 100
    assert len(slugify(long_t)) <= 60


def test_build_prompt():
    prompt = build_prompt("survey about world model")
    assert "world model" in prompt
    assert "write_todos" in prompt


def test_summarize():
    msg1 = MagicMock()
    msg1.tool_calls = [{"name": "write_todos"}, {"name": "task"}]
    msg1.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    msg2 = MagicMock()
    msg2.tool_calls = [{"name": "task"}]
    msg2.usage_metadata = {"input_tokens": 80, "output_tokens": 30}

    messages = [msg1, msg2]
    res = summarize(messages, 12.34, "gpt-4o-mini")

    assert res["model"] == "gpt-4o-mini"
    assert res["elapsed_s"] == 12.3
    assert res["subagent_calls"] == 2
    assert res["tool_calls"]["task"] == 2
    assert res["tool_calls"]["write_todos"] == 1
    assert res["tokens"]["input"] == 180
    assert res["tokens"]["output"] == 80


def test_save_outputs_raises_on_missing_report(tmp_path):
    mock_backend = MagicMock()
    # download returns missing
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("research.download", lambda b, paths: {p: None for p in paths})
        with pytest.raises(RuntimeError):
            save_outputs(mock_backend, "topic", [], 1.0, "m", reports_dir=tmp_path)
    # verify nothing was written
    assert list(tmp_path.iterdir()) == []


def test_save_outputs_writes_files(tmp_path):
    mock_backend = MagicMock()
    report_bytes = b"# Survey\n\nBody [1].\n\n## References\n[1] Paper. url. (2025)"
    sources_bytes = json.dumps([{"n": 1, "url": "https://arxiv.org/abs/1", "source": "arxiv"}]).encode("utf-8")

    from agents import REPORT_PATH, SOURCES_PATH
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("research.download", lambda b, paths: {
            REPORT_PATH: report_bytes,
            SOURCES_PATH: sources_bytes,
        })
        out_path = save_outputs(mock_backend, "My Topic", [], 10.0, "model1", reports_dir=tmp_path)
        assert out_path.exists()
        assert (tmp_path / "my-topic.sources.json").exists()
        meta_file = tmp_path / "my-topic.meta.json"
        assert meta_file.exists()
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta["topic"] == "My Topic"
        assert meta["n_sources"] == 1
        assert meta["source_families"] == ["arxiv"]
