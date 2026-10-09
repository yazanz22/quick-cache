"""Grounding check (CLAUDE.md §8.3): every number in AI text must match a number in its inputs.

Handles Western and Arabic-Indic digits. A number matches if it equals an input
number, its rounding to 0 or 1 decimals, or (for HH:MM times) the 12-hour form.
"""
from __future__ import annotations

import re
from typing import Any

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
ALWAYS_OK = {0.0, 1.0}
TOL = 0.051

# Family/neighbour words a voice may NOT use unless it is the citizen's own helper.
KIN_WORDS = ["ابني", "بنتي", "حفيدي", "حفيدتي", "أخوي", "اخوي", "أختي", "اختي", "زوجي", "زوجتي", "جاري", "جارتي",
             "أبوي", "ابوي", "أمي", "امي", "ابن عمي", "بنت عمي", "صاحبي"]


def to_western(text: str) -> str:
    return (text or "").translate(_DIGITS)


def numbers_in(text: str) -> list[float]:
    return [float(x) for x in _NUM.findall(to_western(text))]


def allowed_numbers(obj: Any) -> set[float]:
    out: set[float] = set(ALWAYS_OK)

    def add(x: float):
        x = abs(float(x))
        out.update({x, round(x), round(x, 1), round(x, 2)})

    def walk(o: Any):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            add(o)
        elif isinstance(o, str):
            for h, _m in _TIME.findall(to_western(o)):
                add(int(h) % 12 or 12)
            for n in numbers_in(o):
                add(n)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v)

    walk(obj)
    return out


def ungrounded(text: str, inputs: Any) -> list[float]:
    """Numbers in `text` that don't match anything in `inputs` (empty list = grounded)."""
    ok = allowed_numbers(inputs)
    return [n for n in numbers_in(text) if not any(abs(n - a) <= TOL for a in ok)]


def foreign_people(text: str, helper_relation_ar: str | None) -> list[str]:
    """Kin words in a voice other than the citizen's own helper."""
    t = to_western(text)
    found = []
    for w in KIN_WORDS:
        if helper_relation_ar and (w == helper_relation_ar or w.replace("أ", "ا") == helper_relation_ar.replace("أ", "ا")):
            continue
        if re.search(rf"(?<![ء-ي]){w}(?![ء-ي])", t):
            found.append(w)
    return found


def has_arabic(text: str) -> bool:
    return bool(re.search(r"[ء-ي]", text or ""))
