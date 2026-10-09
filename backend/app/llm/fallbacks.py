"""Deterministic, non-AI text for every AI task (CLAUDE.md §8.6).

Built only from engine output and reason codes, in Arabic and English.
"""
from __future__ import annotations

from ..models import ParseResult
from ..sim import world
from ..sim.world import DAY_AR, DAY_EN

# First-person clauses for voices, in Modern Standard Arabic (فصحى).
REASON_VOICE = {
    "TOO_FAR": ("المكتب بعيد عني", "the office is too far for me"),
    "NO_TRANSPORT": ("لا توجد وسيلة توصلني", "I have no way to get there"),
    "HOURS_CONFLICT_WORK": ("ساعات الدوام تتعارض مع عملي", "the hours clash with my work"),
    "NO_SMARTPHONE": ("لا أملك هاتفاً ذكياً", "I don't have a smartphone"),
    "LOW_DIGITAL_LITERACY": ("لا أجيد استخدام المواقع والتطبيقات", "I can't manage websites and apps"),
    "NOT_WHEELCHAIR_ACCESSIBLE": ("المكتب غير مجهّز للكرسي المتحرك", "the office isn't wheelchair accessible"),
    "TOO_EXPENSIVE": ("أجرة سيارة الأجرة أكبر من قدرتي", "a taxi costs more than I can afford"),
    "OFFICE_CLOSED_ON_AVAILABLE_DAYS": ("المكتب مغلق في الأوقات التي أستطيع الذهاب فيها", "it's closed whenever I can go"),
}
# The population stores helper relations in Jordanian dialect; voices use the فصحى form.
HELPER_MSA = {"بنتي": "ابنتي", "أخوي": "أخي", "اخوي": "أخي", "أبوي": "أبي", "ابوي": "أبي", "صاحبي": "صديقي"}


def msa_helper(rel_ar: str | None) -> str | None:
    return HELPER_MSA.get(rel_ar, rel_ar) if rel_ar else None


GROUP_LABELS = {
    "elderly": ("كبار السن", "elderly"), "disabled": ("ذوو الإعاقة", "disabled"),
    "no_car": ("من لا يملكون سيارة", "no car"), "offline": ("غير المتصلين رقمياً", "offline"),
    "low_income": ("ذوو الدخل المحدود", "low income"), "worker": ("العاملون", "workers"),
    "student": ("الطلاب", "students"), "all": ("الجميع", "everyone"),
}


def _n(x: float) -> str:
    x = round(float(x), 1)
    return str(int(x)) if x == int(x) else str(x)


def _count_ar(x: float, singular: str, plural: str) -> str:
    """Arabic counted noun: 3-10 take the plural (8 دقائق), everything else the singular (15 دقيقة, 1.5 ساعة)."""
    v = round(float(x), 1)
    return f"{_n(v)} {plural if v == int(v) and 3 <= v <= 10 else singular}"


def _join_ar(parts: list[str]) -> str:
    return "، و".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _join_en(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else ""


def voice(citizen: dict, o: dict) -> tuple[str, str]:
    """(text_ar first-person in فصحى, one-line English summary)."""
    helper_ar = msa_helper(citizen.get("helper_relation_ar")) or "أحد أقاربي"
    helper_en = citizen.get("helper_relation_en") or "a relative"
    reasons = o.get("reasons") or []
    r_ar = [REASON_VOICE[r][0] for r in reasons if r in REASON_VOICE]
    r_en = [REASON_VOICE[r][1] for r in reasons if r in REASON_VOICE]

    if o["status"] == "left_out":
        return (f"لم أتمكن من إنجاز المعاملة: {_join_ar(r_ar)}.",
                f"Couldn't renew: {_join_en(r_en)}.")

    if o.get("mode") == "online":
        if o["status"] == "served":
            return (f"أنجزت المعاملة عبر الإنترنت من البيت، وكلّفتني {_n(o['cost_jd'])} دينار فقط.",
                    f"Renewed online from home for {_n(o['cost_jd'])} JD.")
        return (f"أنجز {helper_ar} المعاملة عني عبر الإنترنت؛ {_join_ar(r_ar)}.",
                f"{helper_en.capitalize()} did it online for them because {_join_en(r_en)}.")

    if o.get("mode") == "home":
        paid_ar = (f"وكلّفني ذلك {_count_ar(o['cost_jd'], 'دينار', 'دنانير')}" if o.get("cost_jd", 0) >= 0.05
                   else "دون أن أدفع أي رسوم")
        ar = f"جاء موظف الأحوال المدنية إلى بيتي وجدّد هويتي، {paid_ar}."
        en = (f"A clerk came to their home: {_n(o['hours_lost'])} h waiting at home, "
              + (f"{_n(o['cost_jd'])} JD." if o.get("cost_jd", 0) >= 0.05 else "free of charge."))
        return ar, en

    mode = o.get("mode")
    transfers = o.get("bus_transfers", 0)
    how_ar = {"car": "بسيارتي", "taxi": "بسيارة أجرة", "helper_car": f"وأوصلني {helper_ar} بالسيارة",
              "bus": ["بحافلة واحدة", "بحافلتين", "بثلاث حافلات"][min(transfers, 2)]}.get(mode, "")
    how_en = {"car": "by car", "taxi": "by taxi", "helper_car": f"driven by {helper_en}",
              "bus": ["by one bus", "by two buses", "by three buses"][min(transfers, 2)]}.get(mode, "")
    day = o.get("visit_day")
    # Mobile-unit channel names already include their day ("... يوم السبت"); don't repeat it.
    day_ar = f" يوم {DAY_AR[day]}" if day and DAY_AR[day] not in (o.get("channel_name_ar") or "") else ""
    day_en = f" on {DAY_EN[day]}" if day and DAY_EN[day] not in (o.get("channel_name_en") or "") else ""
    ar = (f"ذهبت إلى {o['channel_name_ar']}{day_ar} {how_ar}. استغرق الطريق {_count_ar(round(o['travel_minutes']), 'دقيقة', 'دقائق')}، "
          f"وخسرت {_count_ar(o['hours_lost'], 'ساعة', 'ساعات')} و{_count_ar(o['cost_jd'], 'دينار', 'دنانير')} في المجمل.")
    en = (f"Went to the {o['channel_name_en']}{day_en} {how_en}: {round(o['travel_minutes'])} min each way, "
          f"{_n(o['hours_lost'])} h and {_n(o['cost_jd'])} JD in total.")
    road = world.roads().get(o.get("detour_road") or "")
    if road and round(o.get("detour_minutes", 0)) >= 1:
        d = round(o["detour_minutes"])
        ar += f" وبسبب إغلاق {road['name_ar']} طال الطريق {_count_ar(d, 'دقيقة', 'دقائق')} في كل اتجاه."
        en += f" {road['name_en']} closed: +{d} min each way."
    if o.get("work_hours_missed"):
        ar += f" وتغيّبت عن عملي {_count_ar(o['work_hours_missed'], 'ساعة', 'ساعات')}."
        en += f" Missed {_n(o['work_hours_missed'])} h of work."
    if o["status"] == "hardship":
        extra = [x for x in reasons if x != "HOURS_CONFLICT_WORK"]
        if extra:
            ar += f" إضافة إلى ذلك: {_join_ar([REASON_VOICE[r][0] for r in extra])}."
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
