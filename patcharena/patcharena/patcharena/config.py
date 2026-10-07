import os

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")
LLM_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")
LLM_MOCK = os.getenv("LLM_MOCK", "0") == "1"
MOCK_DELAY = float(os.getenv("MOCK_DELAY", "0"))  # seconds, simulates latency for the demo UI
N_CANDIDATES = int(os.getenv("N_CANDIDATES", "8"))
SANDBOX = os.getenv("SANDBOX", "local")  # local | docker
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "patcharena-sandbox")
TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "60"))
CONTEXT_CHARS = int(os.getenv("CONTEXT_CHARS", "30000"))
EXPLOIT_PATH = "tests/test_patcharena_exploit.py"
