"""FastAPI app: starts runs, streams events (SSE) to the dashboard. Hosted demo = preloaded samples only."""
import json
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from . import metrics, pipeline

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
app = FastAPI(title="PatchArena")
RUNS = {}


@app.get("/")
def index():
    return FileResponse(ROOT / "dashboard" / "index.html")


@app.get("/api/samples")
def samples():
    return [{"name": p.name, "issue": (p / "ISSUE.md").read_text()}
            for p in sorted(SAMPLES.iterdir()) if (p / "ISSUE.md").exists()]


@app.get("/api/metrics")
def get_metrics():
    return metrics.snapshot()


@app.post("/api/runs")
def start_run(body: dict):
    name = Path(str(body.get("sample", ""))).name  # no path tricks: samples only
    repo = SAMPLES / name
    if not (repo / "ISSUE.md").exists():
        raise HTTPException(404, "unknown sample")
    issue = body.get("issue") or (repo / "ISSUE.md").read_text()
    run_id, events = uuid.uuid4().hex[:8], []
    RUNS[run_id] = events

    def emit(t, **d):
        events.append({"type": t, "t": time.time(), **d})

    def work():
        try:
            pipeline.run(repo, issue, emit, out_root=str(ROOT / "out"))
        except Exception as e:
            emit("done", outcome="error", reason=str(e))

    threading.Thread(target=work, daemon=True).start()
    return {"id": run_id}


@app.get("/api/runs/{run_id}/events")
def stream(run_id: str):
    events = RUNS.get(run_id)
    if events is None:
        raise HTTPException(404, "unknown run")

    def gen():
        i = 0
        while True:
            while i < len(events):
                ev = events[i]
                i += 1
                yield f"data: {json.dumps(ev)}\n\n"
                if ev["type"] == "done":
                    return
            time.sleep(0.15)

    return StreamingResponse(gen(), media_type="text/event-stream")
