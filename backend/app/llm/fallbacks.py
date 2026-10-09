"""Deterministic, non-AI text for every AI task (CLAUDE.md §8.6).

Built only from engine output and reason codes, in Arabic and English.
"""
from __future__ import annotations

from ..models import ParseResult
from ..sim.world import DAY_AR, DAY_EN

# Neutral labels (chips, lists).
REASON_LABELS = {
    "TOO_FAR": ("بعيد جداً", "Too far"),
    "NO_TRANSPORT": ("لا توجد وسيلة نقل", "No transport"),
    "HOURS_CONFLICT_WORK": ("الدوام يتعارض مع العمل", "Hours clash with work"),
    "NO_SMARTPHONE": ("لا يملك هاتفاً ذكياً", "No smartphone"),
    "LOW_DIGITAL_LITERACY": ("مهارات رقمية ضعيفة", "Low digital literacy"),
    "NOT_WHEELCHAIR_ACCESSIBLE": ("المكان غير مهيأ للكرسي المتحرك", "Not wheelchair accessible"),
    "TOO_EXPENSIVE": ("التكلفة مرتفعة", "Too expensive"),
    "OFFICE_CLOSED_ON_AVAILABLE_DAYS": ("مغلق في الأوقات المتاحة", "Closed when they can go"),
}
# First-person clauses for voices (Jordanian colloquial).
REASON_VOICE = {
    "TOO_FAR": ("المكتب بعيد عليّ", "the office is too far for me"),
    "NO_TRANSPORT": ("ما في إشي يوصّلني", "I have no way to get there"),
    "HOURS_CONFLICT_WORK": ("الدوام بيتعارض مع شغلي", "the hours clash with my work"),
    "NO_SMARTPHONE": ("ما عندي تلفون ذكي", "I don't have a smartphone"),
    "LOW_DIGITAL_LITERACY": ("ما بعرف أتعامل مع المواقع والتطبيقات", "I can't manage websites and apps"),
    "NOT_WHEELCHAIR_ACCESSIBLE": ("المكتب مش مجهّز للكرسي المتحرك", "the office isn't wheelchair accessible"),
    "TOO_EXPENSIVE": ("التكسي غالي عليّ", "a taxi costs more than I can afford"),
    "OFFICE_CLOSED_ON_AVAILABLE_DAYS": ("المكتب مسكّر بالأوقات اللي بقدر أروح فيها", "it's closed whenever I can go"),
}
GROUP_LABELS = {
    "elderly": ("كبار السن", "elderly"), "disabled": ("ذوو الإعاقة", "disabled"),
    "no_car": ("من لا يملكون سيارة", "no car"), "offline": ("غير المتصلين رقمياً", "offline"),
    "low_income": ("ذوو الدخل المحدود", "low income"), "worker": ("العاملون", "workers"),
    "student": ("الطلاب", "students"), "all": ("الجميع", "everyone"),
}
MODE_LABELS = {
    "car": ("سيارة", "car"), "helper_car": ("مع أحد الأقارب بالسيارة", "driven by family"),
    "bus": ("باص", "bus"), "taxi": ("تكسي", "taxi"), "online": ("أونلاين", "online"),
}
STATUS_LABELS = {"served": ("تمت الخدمة", "Served"), "hardship": ("بصعوبة", "Hardship"), "left_out": ("مستبعد", "Left out")}


def _n(x: float) -> str:
    x = round(float(x), 1)
    return str(int(x)) if x == int(x) else str(x)


def _join_ar(parts: list[str]) -> str:
    return "، و".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _join_en(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else ""


def voice(citizen: dict, o: dict) -> tuple[str, str]:
    """(text_ar first-person, one-line English summary)."""
    helper_ar = citizen.get("helper_relation_ar") or "واحد من أهلي"
    helper_en = citizen.get("helper_relation_en") or "a relative"
    reasons = o.get("reasons") or []
    r_ar = [REASON_VOICE[r][0] for r in reasons if r in REASON_VOICE]
    r_en = [REASON_VOICE[r][1] for r in reasons if r in REASON_VOICE]

    if o["status"] == "left_out":
        return (f"ما قدرت أخلّص المعاملة: {_join_ar(r_ar)}.",
                f"Couldn't renew: {_join_en(r_en)}.")

    if o.get("mode") == "online":
        if o["status"] == "served":
            return (f"خلّصتها أونلاين من البيت، وكلّفتني {_n(o['cost_jd'])} دينار بس.",
                    f"Renewed online from home for {_n(o['cost_jd'])} JD.")
        return (f"{helper_ar} خلّصلي ياها أونلاين، لأنه {_join_ar(r_ar)}.",
                f"{helper_en.capitalize()} did it online for them because {_join_en(r_en)}.")

    mode = o.get("mode")
    transfers = o.get("bus_transfers", 0)
    how_ar = {"car": "بسيارتي", "taxi": "بالتكسي", "helper_car": f"و{helper_ar} وصّلني بالسيارة",
              "bus": ["بباص واحد", "بباصين", "بتلات باصات"][min(transfers, 2)]}.get(mode, "")
    how_en = {"car": "by car", "taxi": "by taxi", "helper_car": f"driven by {helper_en}",
              "bus": ["by one bus", "by two buses", "by three buses"][min(transfers, 2)]}.get(mode, "")
    day_ar = f" يوم {DAY_AR[o['visit_day']]}" if o.get("visit_day") else ""
    day_en = f" on {DAY_EN[o['visit_day']]}" if o.get("visit_day") else ""
    ar = (f"رحت على {o['channel_name_ar']}{day_ar} {how_ar}، الطريق {_n(o['travel_minutes'])} دقيقة، "
          f"وراح عليّ {_n(o['hours_lost'])} ساعات و{_n(o['cost_jd'])} دينار.")
    en = (f"Went to the {o['channel_name_en']}{day_en} {how_en}: {_n(o['travel_minutes'])} min each way, "
          f"{_n(o['hours_lost'])} h and {_n(o['cost_jd'])} JD in total.")
    if o.get("work_hours_missed"):
        ar += f" وغبت عن شغلي {_n(o['work_hours_missed'])} ساعات."
        en += f" Missed {_n(o['work_hours_missed'])} h of work."
    if o["status"] == "hardship":
        extra = [x for x in reasons if x != "HOURS_CONFLICT_WORK"]
        if extra:
            ar += f" وكمان {_join_ar([REASON_VOICE[r][0] for r in extra])}."
            en += f" Also, {_join_en([REASON_VOICE[r][1] for r in extra])}."
    return ar, en


def fix_explanation(fix: dict, improved_groups: list[str]) -> tuple[str, str]:
    g_ar = _join_ar([GROUP_LABELS[g][0] for g in improved_groups[:2]])
    g_en = _join_en([GROUP_LABELS[g][1] for g in improved_groups[:2]])
    ar = (f"{fix['title_ar']}: نسبة المستبعدين تنخفض {_n(fix['left_out_drop'])} نقطة "
          f"ونسبة من يواجهون صعوبة تنخفض {_n(fix['hardship_drop'])} نقطة")
    en = (f"{fix['title_en']}: {_n(fix['left_out_drop'])} pts fewer people left out and "
          f"{_n(fix['hardship_drop'])} pts fewer in hardship")
    if improved_groups:
        ar += f"، وأكثر المستفيدين {g_ar}."
        en += f", mostly {g_en}."
    else:
        ar += "."
        en += "."
    return ar, en


def report(summary: dict) -> tuple[str, str]:
    b, s = summary["baseline_kpis"], summary["scenario_kpis"]
    top = summary["worst_groups"][:2]
    g = summary["group_deltas"]
    ar = (f"مقارنة بالوضع الحالي، تتغير نسبة من تمت خدمتهم من {_n(b['pct_served'])}% إلى {_n(s['pct_served'])}%، "
          f"ومن يواجهون صعوبة من {_n(b['pct_hardship'])}% إلى {_n(s['pct_hardship'])}%، "
          f"والمستبعدين من {_n(b['pct_left_out'])}% إلى {_n(s['pct_left_out'])}%. "
          f"أكثر الفئات تضرراً: {_join_ar([GROUP_LABELS[x][0] for x in top])} "
          f"(ارتفاع الصعوبة والاستبعاد {_join_ar([_n(g[x]) + ' نقطة' for x in top])}).")
    en = (f"Compared with today, the share served moves from {_n(b['pct_served'])}% to {_n(s['pct_served'])}%, "
          f"hardship from {_n(b['pct_hardship'])}% to {_n(s['pct_hardship'])}%, and left out from "
          f"{_n(b['pct_left_out'])}% to {_n(s['pct_left_out'])}%. Hardest hit: "
          f"{_join_en([GROUP_LABELS[x][1] for x in top])} (hardship + left out up "
          f"{_join_en([_n(g[x]) + ' pts' for x in top])}).")
    sens = summary.get("sensitivity")
    if sens:
        ar += f" اختبار المتانة: ثبت الترتيب في {sens['ranking_held']} من {sens['runs']} تجارب عند تغيير الافتراضات ±20%."
        en += f" Robustness: the ranking held in {sens['ranking_held']} of {sens['runs']} runs at ±20%."
    return ar, en


def parse_failed() -> ParseResult:
    return ParseResult(
        status="unsupported", policy=None, changes_ar=[], changes_en=[], source="fallback",
        message_ar="ما قدرنا نفهم الطلب. جرّب أدوات السياسة في اللوحة.",
        message_en="Couldn't understand that. Try the policy controls in the panel.")
