import json
import subprocess

import pytest

from bench.make_manifest import create_manifest
from bench.run import load_cases


def test_load_cases_resolves_repo_and_issue_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "issue.md").write_text("A real bug description.", encoding="utf-8")
    manifest = tmp_path / "cases.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "name": f"bug-{index}",
                    "repo": "repo",
                    "issue_file": "issue.md",
                }
                for index in range(10)
            ]
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
    manifest.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly ten"):
        load_cases(manifest)


def test_create_manifest_uses_detached_pre_fix_worktrees(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Benchmark Test")
    git("config", "user.email", "benchmark@example.test")
    (repo / "app.py").write_text("def value():\n    return None\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "Add initial implementation")
    (repo / "app.py").write_text("def value():\n    return 42\n", encoding="utf-8")
    git("commit", "-am", "Fix returned value")

    output = tmp_path / "benchmark"
    cases = create_manifest(repo, output, count=1)

    assert len(cases) == 1
    assert "return None" in (output / "bug-1" / "app.py").read_text(encoding="utf-8")
    assert json.loads((output / "answers.json").read_text(encoding="utf-8")) == {
        "bug-1": git_output(repo, "rev-parse", "HEAD")
    }


def git_output(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
