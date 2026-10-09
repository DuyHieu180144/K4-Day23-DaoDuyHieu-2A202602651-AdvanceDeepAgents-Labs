import pytest
from unittest.mock import MagicMock

from agents import (
    LEAD_PROMPT,
    RESEARCHER_PROMPT,
    CHECKER_PROMPT,
    build_subagents,
    build_lead_agent,
    LEAD_LIMITS,
    SUB_LIMITS,
    WORKDIR,
    SOURCES_PATH,
    REPORT_PATH,
    VALIDATOR_PATH,
    FINALIZER_PATH,
)


def test_prompts_contain_required_rules():
    assert "write_todos" in LEAD_PROMPT
    assert SOURCES_PATH in LEAD_PROMPT
    assert REPORT_PATH in LEAD_PROMPT
    assert FINALIZER_PATH in LEAD_PROMPT
    assert VALIDATOR_PATH in LEAD_PROMPT
    assert "source families" in LEAD_PROMPT.lower() or "arxiv" in LEAD_PROMPT

    assert "untrusted" in RESEARCHER_PROMPT.lower()
    assert "notes" in RESEARCHER_PROMPT.lower()
    assert "web_fetch" in CHECKER_PROMPT or "supported" in CHECKER_PROMPT.lower()


def test_subagents_structure():
    subagents = build_subagents()
    assert len(subagents) == 2
    names = {s["name"] for s in subagents}
    assert names == {"researcher", "citation-checker"}

    researcher = next(s for s in subagents if s["name"] == "researcher")
    assert len(researcher["tools"]) == 5
    assert "middleware" in researcher
    assert researcher["middleware"] == SUB_LIMITS

    checker = next(s for s in subagents if s["name"] == "citation-checker")
    assert len(checker["tools"]) == 1
    assert "middleware" in checker
    assert checker["middleware"] == SUB_LIMITS


def test_build_lead_agent():
    mock_backend = MagicMock()
    mock_model = MagicMock()
    # verify build_lead_agent can be called or mocked
    with pytest.MonkeyPatch.context() as mp:
        mock_create = MagicMock(return_value="agent_instance")
        mp.setattr("agents.create_deep_agent", mock_create)
        agent = build_lead_agent(mock_backend, mock_model)
        assert agent == "agent_instance"
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["model"] == mock_model
        assert kwargs["backend"] == mock_backend
        assert len(kwargs["middleware"]) >= 3  # TodoListMiddleware + 2 limits

