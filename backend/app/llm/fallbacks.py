"""Deterministic, non-AI text for every AI task (CLAUDE.md §8.6).

Built only from engine output and reason codes, in Arabic (فصحى) and English. None of this text
goes into a cache key, so it can be reworded freely.
"""
from __future__ import annotations

from ..models import ParseResult
from ..sim.world import DAY_AR, DAY_EN

# First-person clauses for voices, in Modern Standard Arabic (فصحى).
REASON_VOICE = {
    "TOO_FAR": ("المكتب بعيد عني", "the office is too far for me"),
    "NO_TRANSPORT": ("لا توجد وسيلة نقل توصلني", "I have no way to get there"),
    "HOURS_CONFLICT_WORK": ("ساعات الدوام تتعارض مع عملي", "the hours clash with my work"),
    "NO_SMARTPHONE": ("لا أملك هاتفاً ذكياً", "I don't have a smartphone"),
    "LOW_DIGITAL_LITERACY": ("لا أجيد استخدام المواقع والتطبيقات", "I can't manage websites and apps"),
    "NOT_WHEELCHAIR_ACCESSIBLE": ("المكتب غير مجهّز لمستخدمي الكراسي المتحركة", "the office isn't wheelchair accessible"),
    "TOO_EXPENSIVE": ("أجرة سيارة الأجرة تفوق قدرتي", "a taxi costs more than I can afford"),
    "OFFICE_CLOSED_ON_AVAILABLE_DAYS": ("المكتب مغلق في الأوقات التي أستطيع الذهاب فيها", "it's closed whenever I can go"),
}
# The population stores helper relations in Jordanian dialect; voices use the فصحى form.
HELPER_MSA = {"بنتي": "ابنتي", "أخوي": "أخي", "اخوي": "أخي", "أبوي": "أبي", "ابوي": "أبي", "صاحبي": "صديقي"}
# Helpers who take feminine verbs (أنجزت، أوصلتني).
FEMININE_HELPERS = {"أمي", "أختي", "ابنتي", "زوجتي", "جارتي", "صديقتي", "عمتي", "خالتي", "جدتي", "بنت عمي",
                    "حفيدتي", "والدتي"}


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


# Counted nouns: singular (after decimals and 100, 101, ...), accusative singular (11-99), "one" in the
# nominative/genitive and in the accusative, the dual in the nominative and in the accusative/genitive,
# and the plural (3-10).
NOUNS = {
    "dinar": ("دينار", "ديناراً", "دينار واحد", "ديناراً واحداً", "ديناران", "دينارين", "دنانير"),
    "hour": ("ساعة", "ساعة", "ساعة واحدة", "ساعة واحدة", "ساعتان", "ساعتين", "ساعات"),
    "minute": ("دقيقة", "دقيقة", "دقيقة واحدة", "دقيقة واحدة", "دقيقتان", "دقيقتين", "دقائق"),
    "point": ("نقطة", "نقطة", "نقطة واحدة", "نقطة واحدة", "نقطتان", "نقطتين", "نقاط"),
    "person": ("شخص", "شخصاً", "شخص واحد", "شخصاً واحداً", "شخصان", "شخصين", "أشخاص"),
    "run": ("تجربة", "تجربة", "تجربة واحدة", "تجربة واحدة", "تجربتان", "تجربتين", "تجارب"),
}


def count_ar(x: float, noun: str, case: str = "acc") -> str:
    """An Arabic number with its counted noun, in Western digits. case: "nom", "acc" or "gen".
    1 -> "دينار واحد" / "ديناراً واحداً", 2 -> "ديناران" / "دينارين", 3-10 -> "3 دنانير", 11-99 -> "15 ديناراً",
    100 -> "100 دينار", decimals -> "2.5 دينار"."""
    sing, sing_acc, one, one_acc, dual_nom, dual_acc, plural = NOUNS[noun]
    v = round(abs(float(x)), 1)
    if v != int(v):
        return f"{_n(v)} {sing}"
    n = int(v)
    if n == 1:
        return one_acc if case == "acc" else one
    if n == 2:
        return dual_nom if case == "nom" else dual_acc
    r = n % 100
    if 3 <= r <= 10:
        return f"{n} {plural}"
    if 11 <= r <= 99:
        return f"{n} {sing_acc}"
    return f"{n} {sing}"


def _pts_en(x: float) -> str:
    v = round(abs(float(x)), 1)
    return f"{_n(v)} {'pt' if v == 1 else 'pts'}"


def _join_ar(parts: list[str]) -> str:
    return "، و".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _join_en(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else ""


def _free(cost: float) -> bool:
    return round(float(cost or 0), 1) < 0.05


def voice(citizen: dict, o: dict) -> tuple[str, str]:
    """(text_ar first-person in فصحى, one-line first-person English summary)."""
    helper_ar = msa_helper(citizen.get("helper_relation_ar")) or "أحد أقاربي"
    helper_en = citizen.get("helper_relation_en") or "a relative"
    fem = helper_ar in FEMININE_HELPERS
    reasons = o.get("reasons") or []
    r_ar = [REASON_VOICE[r][0] for r in reasons if r in REASON_VOICE]
    r_en = [REASON_VOICE[r][1] for r in reasons if r in REASON_VOICE]
    cost = o.get("cost_jd", 0) or 0

    if o["status"] == "left_out":
        if not r_ar:
            return "لم أتمكن من إنجاز المعاملة.", "I couldn't renew."
        return (f"لم أتمكن من إنجاز المعاملة: {_join_ar(r_ar)}.",
                f"I couldn't renew: {_join_en(r_en)}.")

    if o.get("mode") == "online":
        if o["status"] == "served":
            if _free(cost):
                return ("أنجزت المعاملة عبر الإنترنت من البيت دون أي رسوم.",
                        "I renewed online from home, free of charge.")
            return (f"أنجزت المعاملة عبر الإنترنت من البيت، وكلّفتني {count_ar(cost, 'dinar')} فقط.",
                    f"I renewed online from home for {_n(cost)} JD.")
        verb = "أنجزت" if fem else "أنجز"
        ar = f"{verb} {helper_ar} المعاملة عني عبر الإنترنت"
        en = f"{helper_en[:1].upper() + helper_en[1:]} did it online for me"
        if r_ar:
            ar += f"، ف{_join_ar(r_ar)}"
            en += f" because {_join_en(r_en)}"
        return ar + ".", en + "."

    if o.get("mode") == "home":
        if _free(cost):
            return ("جاء موظف الأحوال المدنية إلى بيتي وجدّد هويتي دون أي رسوم.",
                    f"A clerk came to my home and renewed my ID: {_n(o.get('hours_lost', 0))} h at home, free of charge.")
        return (f"جاء موظف الأحوال المدنية إلى بيتي وجدّد هويتي، وكلّفني ذلك {count_ar(cost, 'dinar')}.",
                f"A clerk came to my home and renewed my ID: {_n(o.get('hours_lost', 0))} h at home, {_n(cost)} JD.")

    mode = o.get("mode")
    transfers = o.get("bus_transfers", 0) or 0
    drove = "وأوصلتني" if fem else "وأوصلني"
    how_ar = {"car": "بسيارتي", "taxi": "بسيارة أجرة", "helper_car": f"{drove} {helper_ar} بالسيارة",
              "bus": ["بحافلة واحدة", "بحافلتين", "بثلاث حافلات"][min(transfers, 2)]}.get(mode, "")
    how_en = {"car": "by car", "taxi": "by taxi", "helper_car": f"driven by {helper_en}",
              "bus": ["by one bus", "by two buses", "by three buses"][min(transfers, 2)]}.get(mode, "")
    day = o.get("visit_day")
    # Mobile-unit channel names already include their day ("... يوم السبت"); don't repeat it.
    day_ar = f" يوم {DAY_AR[day]}" if day and DAY_AR[day] not in (o.get("channel_name_ar") or "") else ""
    day_en = f" on {DAY_EN[day]}" if day and DAY_EN[day] not in (o.get("channel_name_en") or "") else ""
    minutes = round(o.get("travel_minutes", 0) or 0)
    hours = o.get("hours_lost", 0) or 0
    ar = f"ذهبت إلى {o.get('channel_name_ar') or 'المكتب'}{day_ar} {how_ar}".rstrip() + "."
    en = f"I went to the {o.get('channel_name_en') or 'office'}{day_en} {how_en}".rstrip()
    spent_ar = (f"وكلّفني ذلك {count_ar(hours, 'hour')} من وقتي، دون أي رسوم." if _free(cost)
                else f"وكلّفني ذلك {count_ar(hours, 'hour')} من وقتي و{count_ar(cost, 'dinar')} في المجمل.")
    spent_en = f"{_n(hours)} h in total, free of charge." if _free(cost) else f"{_n(hours)} h and {_n(cost)} JD in total."
    if minutes >= 1:
        ar += f" استغرق الطريق {count_ar(minutes, 'minute')} في كل اتجاه، {spent_ar}"
        en += f": {minutes} min each way, {spent_en}"
    else:
        ar += f" {spent_ar}"
        en += f": {spent_en}"
    if o.get("work_hours_missed"):
        ar += f" وتغيّبت عن عملي {count_ar(o['work_hours_missed'], 'hour')}."
        en += f" I missed {_n(o['work_hours_missed'])} h of work."
    if o["status"] == "hardship":
        extra = [x for x in reasons if x != "HOURS_CONFLICT_WORK" and x in REASON_VOICE]
        if extra:
            ar += f" إضافة إلى ذلك: {_join_ar([REASON_VOICE[r][0] for r in extra])}."
            en += f" Also, {_join_en([REASON_VOICE[r][1] for r in extra])}."
    return ar, en


def _change_ar(subject: str, drop: float) -> str:
    """"تنخفض نسبة X بمقدار 0.8 نقطة" for a positive drop, "ترتفع ..." for a negative one."""
    v = round(float(drop), 1)
    if v > 0:
        return f"تنخفض {subject} بمقدار {count_ar(v, 'point', 'gen')}"
    if v < 0:
        return f"ترتفع {subject} بمقدار {count_ar(v, 'point', 'gen')}"
    return f"لا تتغير {subject}"


def _change_en(subject: str, drop: float) -> str:
    v = round(float(drop), 1)
    if v > 0:
        return f"{subject} falls by {_pts_en(v)}"
    if v < 0:
        return f"{subject} rises by {_pts_en(v)}"
    return f"{subject} is unchanged"


def fix_explanation(fix: dict, improved_groups: list[str]) -> tuple[str, str]:
    g_ar = _join_ar([GROUP_LABELS[g][0] for g in improved_groups[:2]])
    g_en = _join_en([GROUP_LABELS[g][1] for g in improved_groups[:2]])
    ar = (f"{fix['title_ar']}: {_change_ar('نسبة المستبعدين', fix['left_out_drop'])}، "
          f"و{_change_ar('نسبة من يواجهون صعوبة', fix['hardship_drop'])}")
    en = (f"{fix['title_en']}: {_change_en('the share left out', fix['left_out_drop'])} and "
          f"{_change_en('the share in hardship', fix['hardship_drop'])}")
    if improved_groups:
        ar += f"، وأكثر المستفيدين {g_ar}."
        en += f", mostly {g_en}."
    else:
        ar += "."
        en += "."
    return ar, en


def report(summary: dict) -> tuple[str, str]:
    b, s = summary["baseline_kpis"], summary["scenario_kpis"]
    g = summary["group_deltas"]
    top = [x for x in summary["worst_groups"][:2] if g.get(x, 0) > 0]
    ar = (f"مقارنة بالوضع الحالي، تتغير نسبة من تمت خدمتهم من {_n(b['pct_served'])}% إلى {_n(s['pct_served'])}%، "
          f"ونسبة من يواجهون صعوبة من {_n(b['pct_hardship'])}% إلى {_n(s['pct_hardship'])}%، "
          f"ونسبة المستبعدين من {_n(b['pct_left_out'])}% إلى {_n(s['pct_left_out'])}%.")
    en = (f"Compared with today, the share served moves from {_n(b['pct_served'])}% to {_n(s['pct_served'])}%, "
          f"hardship from {_n(b['pct_hardship'])}% to {_n(s['pct_hardship'])}%, and left out from "
          f"{_n(b['pct_left_out'])}% to {_n(s['pct_left_out'])}%.")
    if not top:
        ar += " لا تسوء أوضاع أي فئة مقارنة بالوضع الحالي."
        en += " No group is worse off than today."
    elif len(top) == 1:
        x = top[0]
        ar += (f" أكثر الفئات تضرراً {GROUP_LABELS[x][0]}، إذ ترتفع بينهم نسبة من يواجهون صعوبة أو يُستبعدون "
               f"بمقدار {count_ar(g[x], 'point', 'gen')}.")
        en += f" Hardest hit: {GROUP_LABELS[x][1]} (hardship + left out up {_pts_en(g[x])})."
    else:
        x, y = top
        ar += (f" أكثر الفئات تضرراً {GROUP_LABELS[x][0]} ثم {GROUP_LABELS[y][0]}، إذ ترتفع بينهم نسبة من يواجهون "
               f"صعوبة أو يُستبعدون بمقدار {count_ar(g[x], 'point', 'gen')} و{count_ar(g[y], 'point', 'gen')} "
               f"على التوالي.")
        en += (f" Hardest hit: {GROUP_LABELS[x][1]} and {GROUP_LABELS[y][1]} (hardship + left out up "
               f"{_pts_en(g[x])} and {_pts_en(g[y])}).")
    sens = summary.get("sensitivity")
    if sens:
        ar += (f" اختبار المتانة: ثبت الترتيب في {sens['ranking_held']} من أصل {count_ar(sens['runs'], 'run', 'gen')} "
               f"عند تغيير الافتراضات ±20%.")
        en += f" Robustness: the ranking held in {sens['ranking_held']} of {sens['runs']} runs at ±20%."
        if "fix_still_helps" in sens:
            ar += f" وبقي الحل المختار مفيداً في {sens['fix_still_helps']} منها."
            en += f" The chosen fix still helped in {sens['fix_still_helps']} of them."
    fx = summary.get("applied_fix")
    if fx:
        k, n = fx["kpis"], fx["people_better_off"]
        better_ar = (f"ويتحسن وضع {count_ar(n, 'person', 'gen')} مقارنة بالسياسة المقترحة" if n
                     else "ولا يتحسن وضع أي شخص مقارنة بالسياسة المقترحة")
        ar += (f" بعد تطبيق الحل المختار تصبح نسبة من تمت خدمتهم {_n(k['pct_served'])}%، ونسبة من يواجهون صعوبة "
               f"{_n(k['pct_hardship'])}%، ونسبة المستبعدين {_n(k['pct_left_out'])}%، {better_ar}.")
        en += (f" With the chosen fix applied: {_n(k['pct_served'])}% served, {_n(k['pct_hardship'])}% in hardship, "
               f"{_n(k['pct_left_out'])}% left out, and {n} {'person' if n == 1 else 'people'} better off "
               f"than under the proposed policy.")
    return ar, en


def parse_failed() -> ParseResult:
    """The AI answered, but its output was rejected twice (or the text was empty)."""
    return ParseResult(
        status="unsupported", policy=None, changes_ar=[], changes_en=[], source="fallback",
        message_ar="تعذّر فهم الطلب. جرّب أدوات السياسة في اللوحة.",
        message_en="Couldn't understand that. Try the policy controls in the panel.")


def parse_unavailable() -> ParseResult:
    """No AI answer at all: offline mode, a cache miss offline, or every provider unavailable."""
    return ParseResult(
        status="unsupported", policy=None, changes_ar=[], changes_en=[], source="fallback",
        message_ar="خدمة الذكاء الاصطناعي غير متاحة الآن؛ استخدم أدوات السياسة في اللوحة.",
        message_en="The AI service is not available right now; use the policy controls in the panel.")
