"""Benchmark the current pipeline against ten locally checked-out bug cases.

Run with: python -m bench.run --cases bench/cases.json
Each case has a name, repo path, and either issue text or an issue_file path.
Use bench.make_manifest to create cases from your own fix history.
"""
import argparse
import json
import time
from pathlib import Path

from patcharena import config, metrics, pipeline

ROOT = Path(__file__).resolve().parent.parent


def load_cases(path):
    manifest_path = Path(path).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("The manifest must contain exactly ten cases.")

    loaded = []
    names = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be an object.")
        name, repo = case.get("name"), case.get("repo")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Case {index} must have a non-empty name.")
        if name in names:
            raise ValueError(f"Duplicate case name: {name}")
        names.add(name)
        if not isinstance(repo, str) or not repo.strip():
            raise ValueError(f"Case {name} must have a local repo path.")

        repo_path = Path(repo)
        if not repo_path.is_absolute():
            repo_path = manifest_path.parent / repo_path
        if not repo_path.is_dir():
            raise ValueError(f"Repo for case {name} is not a local directory: {repo_path}")

        issue, issue_file = case.get("issue"), case.get("issue_file")
        if bool(issue) == bool(issue_file):
            raise ValueError(f"Case {name} must have exactly one of 'issue' or 'issue_file'.")
        if issue_file:
            issue_path = Path(issue_file)
            if not issue_path.is_absolute():
                issue_path = manifest_path.parent / issue_path
            issue = issue_path.read_text(encoding="utf-8")
        if not isinstance(issue, str) or not issue.strip():
            raise ValueError(f"Case {name} has an empty issue description.")
        loaded.append({"name": name, "repo": repo_path, "issue": issue})
    return loaded


def run_cases(cases, output, candidates=None):
    rows = []
    for case in cases:
        started = time.perf_counter()
        result = pipeline.run(
            case["repo"],
            case["issue"],
            n=candidates,
            out_root=str(ROOT / "out"),
        )
        elapsed = round(time.perf_counter() - started, 1)
        snapshot = metrics.snapshot()
        row = {
            "name": case["name"],
            "outcome": result["outcome"],
            "seconds": elapsed,
            "verified_candidates": sum(v.passed for v in result["verdicts"]),
            "candidates": len(result["verdicts"]),
            "tokens_per_sec": snapshot["tokens_per_sec"],
        }
        rows.append(row)
        print(json.dumps(row))

    solved = sum(row["outcome"] == "verified_pr" for row in rows)
    report = {
        "pipeline_solve_rate": {"solved": solved, "total": len(rows)},
        "rows": rows,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Pipeline solve rate: {solved}/{len(rows)}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, help="JSON file containing exactly ten real bug cases")
    parser.add_argument("--output", default=str(ROOT / "bench" / "results.json"))
    parser.add_argument("--candidates", type=int, default=None, help="candidate count per bug")
    args = parser.parse_args()
    if config.LLM_MOCK:
        parser.error("Benchmarking requires a real model; unset LLM_MOCK.")
    try:
        cases = load_cases(args.cases)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    run_cases(cases, args.output, args.candidates)


if __name__ == "__main__":
    main()
