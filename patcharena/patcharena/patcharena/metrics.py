"""Tiny thread-safe counters so the dashboard can show model throughput."""
import threading
import time

_lock = threading.Lock()
_s = {"tokens": 0, "calls": 0, "inflight": 0, "first": None}


def reset():
    with _lock:
        _s.update(tokens=0, calls=0, inflight=0, first=None)


def start():
    with _lock:
        _s["inflight"] += 1
        if _s["first"] is None:
            _s["first"] = time.time()


def finish(tokens):
    with _lock:
        _s["inflight"] -= 1
        _s["calls"] += 1
        _s["tokens"] += tokens


def snapshot():
    with _lock:
        elapsed = (time.time() - _s["first"]) if _s["first"] else 0
        tps = _s["tokens"] / elapsed if elapsed > 0 else 0
        return {"tokens": _s["tokens"], "calls": _s["calls"], "inflight": _s["inflight"],
                "tokens_per_sec": round(tps, 1)}
