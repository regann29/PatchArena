import argparse
import json
import sys

from . import ingest, pipeline


def main():
    ap = argparse.ArgumentParser(prog="patcharena")
    ap.add_argument("--repo", required=True, help="local path or git URL")
    ap.add_argument("--issue", required=True, help="issue text, or @file to read from a file")
    ap.add_argument("-n", type=int, default=None, help="number of candidates")
    a = ap.parse_args()
    issue = open(a.issue[1:]).read() if a.issue.startswith("@") else a.issue
    repo = ingest.clone(a.repo) if a.repo.startswith(("http://", "https://", "git@")) else a.repo

    def emit(t, **d):
        if t == "verdict":
            print(f"  candidate {d['index']}: {'PASS' if d['passed'] else 'fail'}  {d['reason']}")
        elif t in ("ingested", "exploit_attempt", "exploit_ready", "done"):
            print(t, {k: v for k, v in d.items() if k in ("files", "attempt", "outcome", "out")})

    res = pipeline.run(repo, issue, emit, a.n)
    sys.exit(0 if res["outcome"] == "verified_pr" else 1)


if __name__ == "__main__":
    main()
