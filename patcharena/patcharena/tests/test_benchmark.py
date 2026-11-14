import json
import os
import subprocess

import pytest

from bench.make_manifest import create_manifest, find_fix_commits
from bench.run import load_cases
from patcharena.arena import sandbox


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


def test_load_cases_requires_at_least_five_cases(tmp_path):
    manifest = tmp_path / "cases.json"
    manifest.write_text(json.dumps([{}] * 4), encoding="utf-8")

    with pytest.raises(ValueError, match="at least five"):
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
    (repo / "tests").mkdir()
    for version in range(6):
        (repo / "app.py").write_text(f"def value():\n    return {version}\n", encoding="utf-8")
        (repo / "tests" / "test_app.py").write_text(
            f"from app import value\n\n\ndef test_value():\n    assert value() == {version}\n",
            encoding="utf-8",
        )
        if version == 0:
            git("add", "app.py", "tests/test_app.py")
            git("commit", "-m", "Add initial implementation")
        else:
            git("commit", "-am", f"Fix returned value {version}")

    output = tmp_path / "benchmark"
    cases = create_manifest(repo, output, count=10)

    assert len(cases) == 5
    assert "return 4" in (output / "bug-1" / "app.py").read_text(encoding="utf-8")
    assert json.loads((output / "answers.json").read_text(encoding="utf-8")) == {
        f"bug-{index}": commit
        for index, commit in enumerate(
        git_output(
            repo,
            "log",
            "--no-merges",
            "--regexp-ignore-case",
            "--grep=fix",
            "--format=%H",
        ).splitlines(),
            start=1,
        )
    }


def test_find_fix_commits_skips_chore_messages_and_fixes_without_tests(tmp_path):
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
    (repo / "tests").mkdir()
    (repo / "app.py").write_text("def value():\n    return 0\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text(
        "from app import value\n\n\ndef test_value():\n    assert value() == 0\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "Add initial implementation")

    (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text(
        "from app import value\n\n\ndef test_value():\n    assert value() == 1\n",
        encoding="utf-8",
    )
    git("commit", "-am", "Fix typo in return value")

    (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    git("commit", "-am", "Fix incorrect return")

    (repo / "app.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text(
        "from app import value\n\n\ndef test_value():\n    assert value() == 3\n",
        encoding="utf-8",
    )
    git("commit", "-am", "Fix incorrect result")

    assert find_fix_commits(repo, 10) == [git_output(repo, "rev-parse", "HEAD")]


def test_import_isolation_puts_case_source_before_inherited_pythonpath(tmp_path, monkeypatch):
    work = tmp_path / "case"
    source = work / "src" / "samplepkg"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("VALUE = 'case'\n", encoding="utf-8")
    installed = tmp_path / "installed" / "samplepkg"
    installed.mkdir(parents=True)
    (installed / "__init__.py").write_text("VALUE = 'installed'\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(installed.parent))

    paths = sandbox.verify_import_isolation(work)

    assert paths["samplepkg"] == str((source / "__init__.py").resolve())
    assert os.path.commonpath([paths["samplepkg"], str(work.resolve())]) == str(work.resolve())


def test_import_isolation_fails_if_import_resolves_outside_case(tmp_path, monkeypatch):
    work = tmp_path / "case"
    source = work / "src" / "samplepkg"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("VALUE = 'case'\n", encoding="utf-8")
    installed = tmp_path / "installed" / "samplepkg"
    installed.mkdir(parents=True)
    (installed / "__init__.py").write_text("VALUE = 'installed'\n", encoding="utf-8")
    monkeypatch.setattr(
        sandbox,
        "_python_env",
        lambda _: {**os.environ, "PYTHONPATH": str(installed.parent)},
    )

    with pytest.raises(sandbox.ImportIsolationError, match="resolved outside the case copy"):
        sandbox.verify_import_isolation(work)


def test_pytest_reports_import_isolation_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox.config, "SANDBOX", "local")

    def fail(_):
        raise sandbox.ImportIsolationError("wrong module path")

    monkeypatch.setattr(sandbox, "verify_import_isolation", fail)

    result = sandbox.pytest(tmp_path)

    assert result.returncode == 2
    assert result.output == "import isolation failed: wrong module path"


def git_output(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
