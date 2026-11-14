import json

import pytest

from bench.run import load_cases


def test_load_cases_resolves_repo_and_issue_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "issue.md").write_text("A real bug description.", encoding="utf-8")
    manifest = tmp_path / "cases.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "name": f"bug-{index}",
                        "repo": "repo",
                        "issue_file": "issue.md",
                    }
                    for index in range(10)
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_cases(manifest)

    assert len(cases) == 10
    assert cases[0] == {
        "name": "bug-0",
        "repo": repo,
        "issue": "A real bug description.",
    }


def test_load_cases_requires_exactly_ten_cases(tmp_path):
    manifest = tmp_path / "cases.json"
    manifest.write_text(json.dumps({"cases": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly ten"):
        load_cases(manifest)
