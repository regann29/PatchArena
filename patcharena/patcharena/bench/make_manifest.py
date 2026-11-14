"""Build benchmark cases from small Python bug-fix commits in a local repository.

Run with: python -m bench.make_manifest C:\\work\\repo --out C:\\work\\bench --count 10
Rewrite generated issue files as user-reported symptoms before benchmarking.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

SKIP_MESSAGE = re.compile(
    r"\b(?:typo|spelling|lint|format\w*|docs?|ci|pre-commit|changelog|automated|python-modernize)\b",
    re.IGNORECASE,
)


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def is_test(path):
    path = Path(path)
    return (
        "tests" in {part.lower() for part in path.parts}
        or path.name.lower().startswith("test_")
        or path.name.lower() in {"test.py", "tests.py"}
        or path.name.lower().endswith("_test.py")
        or path.name.lower() == "conftest.py"
    )


def find_fix_commits(repo, limit):
    commits = git(
        repo,
        "log",
        "--no-merges",
        "--regexp-ignore-case",
        "--grep=fix",
        "--pretty=%H",
    ).split()
    found = []
    for commit in commits:
        message = git(repo, "show", "-s", "--format=%B", commit)
        if SKIP_MESSAGE.search(message):
            continue
        rows = [
            line.split("\t")
            for line in git(repo, "show", "--numstat", "--format=", commit).strip().splitlines()
        ]
        rows = [row for row in rows if len(row) == 3]
        source = [row for row in rows if row[2].endswith(".py") and not is_test(row[2])]
        tests = [row for row in rows if is_test(row[2])]
        if not source or not tests or len(rows) > 4:
            continue
        try:
            changed_lines = sum(int(row[0]) + int(row[1]) for row in source)
        except ValueError:
            continue
        if changed_lines > 60:
            continue
        try:
            git(repo, "rev-parse", "--verify", commit + "^")
        except RuntimeError:
            continue
        found.append(commit)
        if len(found) == limit:
            break
    return found


def create_manifest(repo, out, count=10):
    repo = Path(repo).resolve()
    out = Path(out).resolve()
    git(repo, "rev-parse", "--show-toplevel")
    try:
        out.relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError("The output folder must be outside the source repository.")
    if count < 5:
        raise ValueError("Count must be at least five.")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Output folder must be empty: {out}")

    commits = find_fix_commits(repo, count)
    if len(commits) < 5:
        raise ValueError(
            f"Found only {len(commits)} suitable fix commits; at least five are required."
        )

    out.mkdir(parents=True, exist_ok=True)
    cases, answers = [], {}
    for index, commit in enumerate(commits, start=1):
        name = f"bug-{index}"
        worktree = out / name
        git(repo, "worktree", "add", "--detach", str(worktree), commit + "^")
        issue_file = out / f"{name}.md"
        issue_file.write_text(
            git(repo, "log", "-1", "--pretty=%s%n%n%b", commit).strip() + "\n",
            encoding="utf-8",
        )
        cases.append(
            {"name": name, "repo": str(worktree), "issue_file": str(issue_file)}
        )
        answers[name] = commit

    (out / "manifest.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    (out / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="path to a local Python git repository")
    parser.add_argument("--out", required=True, help="empty folder for benchmark worktrees and files")
    parser.add_argument("--count", type=int, default=10, help="maximum cases to create (minimum 5)")
    args = parser.parse_args()
    try:
        cases = create_manifest(args.repo, args.out, args.count)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Wrote {len(cases)} cases to {Path(args.out).resolve() / 'manifest.json'}")
    print("Rewrite each issue file as a user-reported symptom before benchmarking.")


if __name__ == "__main__":
    main()
