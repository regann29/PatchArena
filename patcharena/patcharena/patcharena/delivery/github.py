"""Open a real PR. EXPERIMENTAL: needs GITHUB_TOKEN and push access; not exercised by the tests."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path


def open_pr(repo_dir, repo_slug, winner_files, title, body, base="main"):
    token = os.environ["GITHUB_TOKEN"]
    branch = "patcharena/fix-" + os.urandom(3).hex()
    run = lambda *a: subprocess.run(a, cwd=repo_dir, check=True, capture_output=True, text=True)
    run("git", "checkout", "-b", branch)
    for rel, content in winner_files.items():
        (Path(repo_dir) / rel).write_text(content)
    run("git", "add", *winner_files)
    run("git", "commit", "-m", title)
    run("git", "push", f"https://x-access-token:{token}@github.com/{repo_slug}.git", branch)
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo_slug}/pulls",
        data=json.dumps({"title": title, "head": branch, "base": base, "body": body}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["html_url"]
