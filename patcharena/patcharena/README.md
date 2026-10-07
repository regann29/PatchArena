# PatchArena

A security-patching agent that runs a tournament. Given a vulnerability report, it writes a failing exploit test, generates many candidate patches in parallel on an AMD GPU, runs each in a sandbox, and opens a pull request only for a verified winner, with the evidence attached.

Built for the AMD Developer Hackathon: ACT III (lablab.ai).

## How it works

1. **Ingest** the repo (source files first, tests after, within a context cap).
2. **Red agent** writes a pytest exploit test. It must fail on the unpatched code (a real assertion failure, not an import error), or the run stops as "cannot reproduce".
3. **Generator** produces N candidates in parallel, each with a different strategy hint. The model returns complete changed files; the diff is computed locally.
4. **Arena** applies each candidate to a throwaway copy and checks four hard gates: it runs, the exploit test passes, the full existing suite passes, and it does not touch tests or CI files.
5. **Judge** picks the smallest verified diff and writes the PR text with the evidence table. If nothing survives, it writes a "needs human" report instead.

## Quick start (no GPU, scripted model replies)

```bash
pip install -r requirements.txt
python -m pytest -q tests
LLM_MOCK=1 MOCK_DELAY=0.6 uvicorn patcharena.api:app --port 8080   # open http://localhost:8080
LLM_MOCK=1 python -m patcharena.cli --repo samples/sqli_app --issue @samples/sqli_app/ISSUE.md -n 6
```

Mock mode only understands `samples/sqli_app`. It exists so the pipeline, gates, and dashboard can be developed and tested anywhere.

## Running on AMD (ROCm)

1. On the AMD cloud instance, serve an open-weight coder model with vLLM (ROCm build). See `docker-compose.yml`; confirm the image tag and that the model fits GPU memory.
2. Point the app at it: `LLM_BASE_URL=http://<host>:8000/v1 LLM_MODEL=<model name>`.
3. Run `docker compose up --build`, then open port 8080.

All agent reasoning (exploit test, patches, PR summary) goes through that endpoint.

## Sandbox

- `SANDBOX=local` runs pytest in a temp directory. Use it only with the preloaded samples; it is not isolated.
- `SANDBOX=docker` runs each candidate in a container with no network and memory/CPU limits. Build the image first: `docker build -t patcharena-sandbox sandbox/`.
- The hosted demo only accepts preloaded samples. Arbitrary repos should use the Docker sandbox.

## Layout

```
patcharena/
  agents/   red.py, generator.py, judge.py, parsing.py
  arena/    sandbox.py, scorer.py
  delivery/ github.py (experimental PR opener)
  pipeline.py, api.py, cli.py, llm.py, mock_llm.py, metrics.py
dashboard/  live arena UI
samples/    preloaded vulnerable repos (+ ISSUE.md)
bench/      run.py -> results.json
tests/
```

## Status and limits

- Python repos with pytest only.
- One sample repo so far; the benchmark needs more.
- Not yet tested on real AMD hardware or with a real model; prompts will need tuning.
- GitHub PR opening is untested.
- A human must review every PR.
