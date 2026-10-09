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

# Family/neighbour words a voice may NOT use unless it is the citizen's own helper. Matched after hamza
# variants are unified (أ/إ/آ -> ا), so "اخي" and "أخي" are the same word here.
KIN_WORDS = ["ابني", "بنتي", "ابنتي", "حفيدي", "حفيدتي", "أخوي", "أخي", "أختي", "زوجي", "زوجتي", "جاري", "جارتي",
             "أبوي", "أبي", "أمي", "ابن عمي", "بنت عمي", "صاحبي", "صديقي", "صديقتي",
             "عمي", "عمتي", "خالي", "خالتي", "والدي", "والدتي", "أولادي", "أبنائي", "جدي", "جدتي"]
# Attached prefixes: an optional و/ف, then an optional ب/ل/ك ("وأخي", "ولأمي", "بأختي", "كأبي", "فلأبي").
_KIN_PREFIX = "(?:[وف]?[بلك]?)"


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


def ungrounded(text: str, inputs: Any, also: Any = None) -> list[float]:
    """Numbers in `text` that don't match anything in `inputs` (empty list = grounded).
    `also` holds extra allowed numbers that are not part of the inputs (e.g. the 20 of "±20%"), so callers
    can allow them without touching what goes into a cache key."""
    ok = allowed_numbers(inputs) | (allowed_numbers(also) if also is not None else set())
    return [n for n in numbers_in(text) if not any(abs(n - a) <= TOL for a in ok)]


def _unify_hamza(s: str) -> str:
    return (s or "").translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا"}))


def _kin_pattern(word: str) -> str:
    return rf"(?<![ء-ي]){_KIN_PREFIX}{re.escape(_unify_hamza(word))}(?![ء-ي])"


def foreign_people(text: str, helper_relation_ar: str | None) -> list[str]:
    """Kin words in a voice other than the citizen's own helper, also with attached prefixes (وأخي، لأمي)."""
    t = _unify_hamza(to_western(text))
    helper = _unify_hamza(helper_relation_ar) if helper_relation_ar else None
    if helper:
        # Remove the helper's own word first, so e.g. "ابن عمي" does not also count as "عمي".
        t = re.sub(_kin_pattern(helper), " ", t)
    found, seen = [], set()
    for w in KIN_WORDS:
        u = _unify_hamza(w)
        if u == helper or u in seen:
            continue
        seen.add(u)
        if re.search(_kin_pattern(w), t):
            found.append(w)
    return found


def has_arabic(text: str) -> bool:
    return bool(re.search(r"[ء-ي]", text or ""))


WRONG_CURRENCY = re.compile(r"ليرة|ليره|ليرات")
# Misspellings the models produced in testing.
KNOWN_MISSPELLINGS = {"استقلبت": "استقللت", "وكلفشنا": "وكلّفنا"}


def voice_style_problems(text: str, helper_relation_ar: str | None) -> list[str]:
    """Dialect slips a native speaker flagged: the wrong currency, or the helper word without its
    possessive (e.g. "ابن" instead of "ابني")."""
    problems = []
    if WRONG_CURRENCY.search(text or ""):
        problems.append("say دينار/دنانير, not ليرة")
    for wrong, right in KNOWN_MISSPELLINGS.items():
        if wrong in (text or ""):
            problems.append(f"misspelling {wrong!r}: write {right!r}")
    # Stems of 2 letters or fewer are skipped: "أمي" -> "أم" is also the particle "أم" ("or").
    if helper_relation_ar and helper_relation_ar.endswith("ي") and len(helper_relation_ar) > 3:
        stem = helper_relation_ar[:-1]
        if re.search(rf"(?<![ء-ي]){stem}(?![ء-ي])", text or ""):
            problems.append(f"write the helper as {helper_relation_ar!r}, not {stem!r}")
    return problems
