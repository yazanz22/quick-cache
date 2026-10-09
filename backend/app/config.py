"""Loads the repo-root .env once. Everything else reads settings from here."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "app" / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
CACHE_DIR = BACKEND_DIR / "cache"

load_dotenv(REPO_ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


LLM_PROVIDER = env("LLM_PROVIDER", "gemini")
LLM_FALLBACK_PROVIDER = env("LLM_FALLBACK_PROVIDER")
LLM_TIMEOUT_S = float(env("LLM_TIMEOUT_S", "15"))
DEMO_OFFLINE = env("DEMO_OFFLINE", "0") == "1"
