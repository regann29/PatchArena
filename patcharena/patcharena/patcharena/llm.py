"""Chat client for an OpenAI-compatible server (vLLM on ROCm). Stdlib only."""
import json
import random
import time
import urllib.request

from . import config, metrics, mock_llm


def chat(messages, temperature=0.7, max_tokens=2048):
    metrics.start()
    tokens = 0
    try:
        if config.LLM_MOCK:
            time.sleep(config.MOCK_DELAY * random.uniform(0.5, 1.5))
            text = mock_llm.reply(messages)
            tokens = len(text.split())
            return text
        body = json.dumps({"model": config.LLM_MODEL, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens}).encode()
        req = urllib.request.Request(
            config.LLM_BASE_URL.rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + config.LLM_API_KEY})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
        tokens = data.get("usage", {}).get("completion_tokens", 0)
        return data["choices"][0]["message"]["content"]
    finally:
        metrics.finish(tokens)
