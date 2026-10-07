"""Run the tournament over every sample and write bench/results.json.
Add more vulnerable repos under samples/<name>/ (with ISSUE.md) to grow the benchmark."""
import json
import time
from pathlib import Path

from patcharena import metrics, pipeline

ROOT = Path(__file__).resolve().parent.parent


def main():
    rows = []
    for repo in sorted((ROOT / "samples").iterdir()):
        issue_file = repo / "ISSUE.md"
        if not issue_file.exists():
            continue
        t = time.time()
        res = pipeline.run(repo, issue_file.read_text(), out_root=str(ROOT / "out"))
        m = metrics.snapshot()
        rows.append({"sample": repo.name, "outcome": res["outcome"],
                     "seconds": round(time.time() - t, 1),
                     "verified": sum(v.passed for v in res["verdicts"]),
                     "candidates": len(res["verdicts"]),
                     "tokens_per_sec": m["tokens_per_sec"]})
        print(rows[-1])
    solved = sum(r["outcome"] == "verified_pr" for r in rows)
    out = {"resolve_rate": f"{solved}/{len(rows)}", "rows": rows}
    (ROOT / "bench" / "results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
