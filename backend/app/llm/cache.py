"""Disk cache for AI outputs (CLAUDE.md §8.4).

Key = sha256(task + canonical_json(inputs)), deliberately WITHOUT provider or model,
so a fallback provider's answer still counts as a hit. Free text is normalised first
so a stray space or a hamza variant doesn't miss. Provider, model and timestamp are
stored inside the entry as metadata. Only validated, grounded outputs are stored.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from ..config import CACHE_DIR

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def normalize_text(s: str) -> str:
    s = _TASHKEEL.sub("", s or "")
    s = s.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"}))
    return re.sub(r"\s+", " ", s).strip().lower()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def key(task: str, inputs: Any) -> str:
    return hashlib.sha256((task + canonical_json(inputs)).encode("utf-8")).hexdigest()


def _path(task: str, inputs: Any):
    return CACHE_DIR / task / f"{key(task, inputs)}.json"


def get(task: str, inputs: Any) -> Any | None:
    p = _path(task, inputs)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["output"]
    except (OSError, ValueError, KeyError):
        return None


def put(task: str, inputs: Any, output: Any, meta: dict | None = None) -> None:
    p = _path(task, inputs)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"task": task, "output": output, "meta": {**(meta or {}), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
             "inputs": inputs}
    p.write_text(json.dumps(entry, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
