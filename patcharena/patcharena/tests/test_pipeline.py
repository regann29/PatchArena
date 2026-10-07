from pathlib import Path

import pytest

from patcharena import config, pipeline
from patcharena.agents.parsing import parse_files
from patcharena.arena import scorer

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sqli_app"
ISSUE = (SAMPLE / "ISSUE.md").read_text()


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setattr(config, "LLM_MOCK", True)
    monkeypatch.setattr(config, "MOCK_DELAY", 0.0)


def test_parse_files():
    text = "FILE: a.py\n```python\nx = 1\n```\nFILE: pkg/b.py\n```python\ny = 2\n```"
    assert parse_files(text) == {"a.py": "x = 1\n", "pkg/b.py": "y = 2\n"}


def test_protected_paths():
    assert scorer.is_protected("tests/test_app.py")
    assert scorer.is_protected("conftest.py")
    assert not scorer.is_protected("app.py")
    assert not scorer.safe_path("../evil.py")


def test_tournament_rejects_bad_patches_and_picks_smallest_verified(tmp_path):
    events = []
    res = pipeline.run(SAMPLE, ISSUE, lambda t, **d: events.append((t, d)), n=6, out_root=tmp_path)
    assert res["outcome"] == "verified_pr"
    reasons = {v.index: v.reason for v in res["verdicts"]}
    assert res["winner"].index == 0                       # smallest verified diff
    assert [v.passed for v in res["verdicts"]] == [True, False, False, False, True, False]
    assert "Mary Jane" in reasons[1] or "test_name_with_space" in reasons[1]
    assert "protected" in reasons[2]                      # tried to edit tests
    assert "import or run" in reasons[3]                  # syntax error
    assert "exploit still works" in reasons[5]            # no real fix
    assert (Path(res["out"]) / "pr.md").exists()
    assert any(t == "winner" for t, _ in events)


def test_exploit_fails_on_unpatched_repo():
    from patcharena.arena import sandbox
    from patcharena.mock_llm import EXPLOIT
    work = sandbox.materialize(SAMPLE, {config.EXPLOIT_PATH: EXPLOIT})
    try:
        assert sandbox.pytest(work, [config.EXPLOIT_PATH]).returncode == 1
    finally:
        sandbox.cleanup(work)
