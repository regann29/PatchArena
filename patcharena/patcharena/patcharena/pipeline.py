"""Orchestrates the tournament: ingest -> exploit -> N candidates in parallel -> judge -> report."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, ingest, metrics
from .agents import generator, judge, red
from .arena import scorer


def run(repo, issue, emit=None, n=None, out_root="out"):
    emit = emit or (lambda *a, **k: None)
    n = n or config.N_CANDIDATES
    repo = Path(repo)
    out = Path(out_root) / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    metrics.reset()

    ctx = ingest.collect(repo)
    emit("ingested", files=len(ctx.files))

    exploit = red.write_exploit(repo, issue, ctx, emit)
    if exploit is None:
        report = judge.write_needs_human(issue, [], "Could not produce a failing reproduction test.")
        (out / "pr.md").write_text(report)
        emit("done", outcome="needs_human", reason="could not reproduce", out=str(out))
        return {"outcome": "needs_human", "out": str(out), "verdicts": []}
    emit("exploit_ready", source=exploit.source, before_tail=exploit.before_output[-600:])

    def one(i):
        emit("candidate_start", index=i, strategy=generator.STRATEGIES[i % len(generator.STRATEGIES)])
        try:
            cand = generator.generate_one(i, issue, ctx, exploit.source)
            v = scorer.evaluate(repo, cand, exploit.source)
        except Exception as e:  # one broken candidate must not sink the tournament
            from .models import Verdict
            v = Verdict(index=i, strategy="error", reason=f"error: {e}")
        emit("verdict", **v.to_dict())
        return v

    with ThreadPoolExecutor(max_workers=n) as pool:
        verdicts = list(pool.map(one, range(n)))

    winner = judge.pick(verdicts)
    (out / "verdicts.json").write_text(json.dumps([v.to_dict(True) for v in verdicts], indent=2))
    if winner is None:
        report = judge.write_needs_human(issue, verdicts, "No candidate cleared every gate.")
        (out / "pr.md").write_text(report)
        emit("done", outcome="needs_human", reason="no verified candidate", out=str(out),
             metrics=metrics.snapshot())
        return {"outcome": "needs_human", "out": str(out), "verdicts": verdicts}

    pr = judge.write_pr(issue, winner, verdicts, exploit.before_output)
    (out / "pr.md").write_text(pr)
    (out / "winner.patch").write_text(winner.diff)
    emit("winner", index=winner.index, diff=winner.diff, pr=pr)
    emit("done", outcome="verified_pr", out=str(out), metrics=metrics.snapshot())
    return {"outcome": "verified_pr", "winner": winner, "out": str(out), "verdicts": verdicts}
