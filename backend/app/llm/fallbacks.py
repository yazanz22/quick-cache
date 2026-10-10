"""Deterministic, non-AI text for every AI task (CLAUDE.md §8.6).

Built only from engine output and reason codes, in Arabic (فصحى) and English. None of this text
goes into a cache key, so it can be reworded freely.
"""
from __future__ import annotations

from ..models import ParseResult
from ..sim import world
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
    # everyday_travel
    "TRANSPORT_OVER_BUDGET": ("رحلتي المنتظمة تكلّف أكثر مما تحتمله ميزانيتي", "my regular trip costs more than my budget can take"),
    "FUEL_COST": ("بسبب غلاء وقود سيارتي", "because of the fuel for my car"),
    "FARE_COST": ("بسبب أجور الحافلات أو سيارات الأجرة", "because of bus or taxi fares"),
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
    "day": ("يوم", "يوماً", "يوم واحد", "يوماً واحداً", "يومان", "يومين", "أيام"),
    "time": ("مرة", "مرة", "مرة واحدة", "مرة واحدة", "مرتان", "مرتين", "مرات"),
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


TRAVEL = "everyday_travel"
NO_TRIP = "no_regular_trip"


def is_travel_outcome(o: dict) -> bool:
    """An everyday_travel outcome: channel "trip:<hub>" or "no_regular_trip", or a trip purpose."""
    ch = o.get("channel") or ""
    return o.get("purpose") is not None or ch == NO_TRIP or ch.startswith("trip:")


def trip_hub(o: dict) -> dict | None:
    """The hub (hubs.json) of a travel outcome's channel "trip:<hub id>", or None."""
    ch = o.get("channel") or ""
    return world.hubs().get(ch[len("trip:"):]) if ch.startswith("trip:") else None


def _money(x: float) -> float:
    """Monthly amounts read better whole from 10 JD up (32 دينار, not 32.4); smaller ones keep one decimal."""
    v = round(abs(float(x or 0)), 1)   # the voice facts' rounding first, so the template stays grounded
    return float(round(v)) if v >= 10 else v


def _trip_reason_tail(reasons: list[str], mode: str | None) -> tuple[str, str]:
    """Why the trip got dearer, by mode: fuel for a car, bus fares or the taxi tariff."""
    if "FUEL_COST" in reasons:
        if mode == "helper_car":  # not their own car
            return " بسبب غلاء الوقود", " because of the fuel price"
        return f" {REASON_VOICE['FUEL_COST'][0]}", f" {REASON_VOICE['FUEL_COST'][1]}"
    if "FARE_COST" in reasons:
        if mode == "bus":
            return " بسبب ارتفاع أجور الحافلات", " because of higher bus fares"
        if mode == "taxi":
            return " بسبب ارتفاع أجرة سيارة الأجرة", " because of higher taxi fares"
        return f" {REASON_VOICE['FARE_COST'][0]}", f" {REASON_VOICE['FARE_COST'][1]}"
    return "", ""


def travel_voice(citizen: dict, o: dict) -> tuple[str, str]:
    """everyday_travel: the citizen's regular trip, its monthly cost before and after, the share of income and any
    cash support. "left_out" here means priced out: the trip itself has become unaffordable."""
    cash = o.get("cash_support_jd_month") or 0
    cash_ar = f" وأتلقى دعماً نقدياً قدره {count_ar(_money(cash), 'dinar', 'nom')} في الشهر." if cash >= 0.05 else ""
    cash_en = f" I get {_n(_money(cash))} JD a month in cash support." if cash >= 0.05 else ""
    if (o.get("channel") or "") == NO_TRIP or (o.get("purpose") is None and not o.get("mode")):
        return ("ليست لي رحلة منتظمة، فلا يغيّر سعر الوقود شيئاً في يومي." + cash_ar,
                "I have no regular trip, so the fuel price changes nothing in my day." + cash_en)

    helper_ar = msa_helper(citizen.get("helper_relation_ar")) or "أحد أقاربي"
    helper_en = citizen.get("helper_relation_en") or "a relative"
    fem = helper_ar in FEMININE_HELPERS
    purpose = o.get("purpose") or "work"
    hub = trip_hub(o)
    dest_ar = hub["name_ar"] if hub else o.get("channel_name_ar")
    dest_en = hub["name_en"] if hub else o.get("channel_name_en")
    go_ar = {"work": f"أذهب إلى عملي في {dest_ar}" if dest_ar else "أذهب إلى عملي",
             "university": f"أذهب إلى {dest_ar}" if dest_ar else "أذهب إلى جامعتي",
             "hospital": f"أراجع {dest_ar}" if dest_ar else "أراجع المستشفى"}[purpose]
    go_en = {"work": f"I go to work in {dest_en}" if dest_en else "I go to work",
             "university": f"I go to {dest_en}" if dest_en else "I go to university",
             "hospital": f"I go to {dest_en}" if dest_en else "I go to hospital"}[purpose]
    days = int(o.get("days_per_week") or 0)
    if purpose == "hospital":
        freq_ar = f"{count_ar(days, 'time')} في الأسبوع" if days else ""
        freq_en = "once a week" if days == 1 else (f"{days} times a week" if days else "")
    else:
        freq_ar = f"{count_ar(days, 'day')} في الأسبوع" if days else ""
        freq_en = f"{days} {'day' if days == 1 else 'days'} a week" if days else ""

    mode = o.get("mode")
    reasons = o.get("reasons") or []
    if not mode:  # no way to make the trip at all
        r_ar = [REASON_VOICE[r][0] for r in reasons if r in REASON_VOICE]
        r_en = [REASON_VOICE[r][1] for r in reasons if r in REASON_VOICE]
        ar = f"لا أستطيع القيام برحلتي المنتظمة: {_join_ar(r_ar)}." if r_ar else "لا أستطيع القيام برحلتي المنتظمة."
        en = f"I can't make my regular trip: {_join_en(r_en)}." if r_en else "I can't make my regular trip."
        return ar + cash_ar, en + cash_en
    transfers = min(int(o.get("bus_transfers") or 0), 2)
    if mode == "helper_car":
        drive_ar = "وتوصلني" if fem else "ويوصلني"
        first_ar = f"{go_ar} {freq_ar}، {drive_ar} {helper_ar} بالسيارة."
        first_en = f"{go_en} {freq_en}, and {helper_en} drives me."
    else:
        how_ar = {"car": "بسيارتي", "taxi": "بسيارة أجرة",
                  "bus": ["بالحافلة", "بحافلتين", "بثلاث حافلات"][transfers]}.get(mode, "")
        how_en = {"car": "by car", "taxi": "by taxi", "bus": ["by bus", "on two buses", "on three buses"][transfers]}.get(mode, "")
        first_ar = " ".join(x for x in (go_ar, how_ar, freq_ar) if x) + "."
        first_en = " ".join(x for x in (go_en, how_en, freq_en) if x) + "."

    now = float(o.get("cost_jd") or 0)
    before = o.get("monthly_cost_before_jd")
    before = now if before is None else float(before)
    share = round(float(o.get("income_share_pct") or 0))
    share_ar = f"، أي {share}% من دخلي" if share else ""
    share_en = f", {share}% of my income" if share else ""
    mb, mn = _money(before), _money(now)
    if mb == mn and abs(now - before) >= 0.05:  # a small change whole dinars would hide (20 -> 20): one decimal
        mb, mn = round(before, 1), round(now, 1)
    b_ar, n_ar = count_ar(mb, "dinar"), count_ar(mn, "dinar")
    with_ar = f" ومع دعم نقدي شهري قدره {count_ar(_money(cash), 'dinar', 'nom')}" if cash >= 0.05 else ""
    with_en = f" with {_n(_money(cash))} JD a month in cash support" if cash >= 0.05 else ""
    if abs(now - before) < 0.05 and not with_ar:
        cost_ar = f" تكلّفني رحلتي {n_ar} في الشهر{share_ar}."
        cost_en = f" It costs {_n(mn)} JD a month{share_en}."
    elif abs(now - before) < 0.05:
        cost_ar = f" كانت رحلتي تكلّفني {b_ar} في الشهر، وبعد القرار الجديد{with_ar} بقيت تكلّفني {n_ar}{share_ar}."
        cost_en = f" It cost {_n(mb)} JD a month;{with_en} it still costs {_n(mn)} JD{share_en}."
    elif _free(now):
        cost_ar = f" كانت رحلتي تكلّفني {b_ar} في الشهر، وبعد القرار الجديد{with_ar} لم تعد تكلّفني شيئاً."
        cost_en = f" It cost {_n(mb)} JD a month; now,{with_en or ' after the change'}, it costs me nothing."
    else:
        cost_ar = f" كانت رحلتي تكلّفني {b_ar} في الشهر، وبعد القرار الجديد{with_ar} أصبحت تكلّفني {n_ar}{share_ar}."
        cost_en = f" It cost {_n(mb)} JD a month; now{with_en} it costs {_n(mn)} JD{share_en}."
    # Only blame fuel or fares when the trip actually got dearer.
    tail_ar, tail_en = _trip_reason_tail(reasons, mode) if now - before >= 0.05 else ("", "")
    status_ar, status_en = {
        "served": (" ما زالت كلفتها في حدود قدرتي.", " I can still manage it."),
        "hardship": (f" هذا يضغط على ميزانيتي{tail_ar}.", f" It squeezes my budget{tail_en}."),
        "left_out": (f" لم أعد أستطيع تحمّل كلفتها{tail_ar}.", f" I can no longer afford it{tail_en}."),
    }[o["status"]]
    if o["status"] == "left_out" and now - before < 0.05:  # nothing got dearer: it was already unaffordable
        status_ar, status_en = f" لا أستطيع تحمّل كلفتها{tail_ar}.", f" I can't afford it{tail_en}."
    if _free(now) and o["status"] == "served":
        status_ar, status_en = "", ""
    return first_ar + cost_ar + status_ar, first_en + cost_en + status_en


def voice(citizen: dict, o: dict) -> tuple[str, str]:
    """(text_ar first-person in فصحى, one-line first-person English summary)."""
    if is_travel_outcome(o):
        return travel_voice(citizen, o)
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


# Status wording per service: the statuses keep the keys served / hardship / left_out, but for everyday_travel they
# mean fine / squeezed / priced out. (subject after "نسبة", English label, the "hardship or left out" phrase.)
WORDS = {
    "id_renewal": {
        "served": ("من تمت خدمتهم", "served", "served"), "hardship": ("من يواجهون صعوبة", "hardship", "in hardship"),
        "left_out": ("المستبعدين", "left out", "left out"), "both_ar": "من يواجهون صعوبة أو يُستبعدون",
        "both_en": "hardship + left out", "today_ar": "بالوضع الحالي", "fx_lo_ar": "نسبة المستبعدين",
        "fx_h_ar": "نسبة من يواجهون صعوبة", "fx_lo_en": "the share left out", "fx_h_en": "the share in hardship"},
    "everyday_travel": {
        "served": ("من هم بخير", "fine", "fine"), "hardship": ("من تُضغط ميزانيتهم", "squeezed", "squeezed"),
        "left_out": ("من يعجزون عن تحمّل كلفة التنقل", "priced out", "priced out"),
        "both_ar": "من تُضغط ميزانيتهم أو يعجزون عن التنقل", "both_en": "squeezed + priced out",
        "today_ar": "بالأسعار الحالية", "fx_lo_ar": "نسبة من يعجزون عن تحمّل كلفة التنقل",
        "fx_h_ar": "نسبة من تُضغط ميزانيتهم", "fx_lo_en": "the share priced out", "fx_h_en": "the share squeezed"},
}


def fix_explanation(fix: dict, improved_groups: list[str], service: str = "id_renewal") -> tuple[str, str]:
    w = WORDS.get(service, WORDS["id_renewal"])
    g_ar = _join_ar([GROUP_LABELS[g][0] for g in improved_groups[:2]])
    g_en = _join_en([GROUP_LABELS[g][1] for g in improved_groups[:2]])
    ar = (f"{fix['title_ar']}: {_change_ar(w['fx_lo_ar'], fix['left_out_drop'])}، "
          f"و{_change_ar(w['fx_h_ar'], fix['hardship_drop'])}")
    en = (f"{fix['title_en']}: {_change_en(w['fx_lo_en'], fix['left_out_drop'])} and "
          f"{_change_en(w['fx_h_en'], fix['hardship_drop'])}")
    if improved_groups:
        ar += f"، وأكثر المستفيدين {g_ar}."
        en += f", mostly {g_en}."
    else:
        ar += "."
        en += "."
    return ar, en


def report(summary: dict) -> tuple[str, str]:
    """summary = tasks.report_summary(...); it carries "service" only for everyday_travel."""
    service = summary.get("service", "id_renewal")
    w = WORDS.get(service, WORDS["id_renewal"])
    (sv_ar, sv_en, _), (hd_ar, hd_en, hd_en2), (lo_ar, lo_en, _) = w["served"], w["hardship"], w["left_out"]
    b, s = summary["baseline_kpis"], summary["scenario_kpis"]
    g = summary["group_deltas"]
    top = [x for x in summary["worst_groups"][:2] if g.get(x, 0) > 0]
    if service == TRAVEL:
        en_head = (f"Compared with today's prices, the share who are fine moves from {_n(b['pct_served'])}% to "
                   f"{_n(s['pct_served'])}%, squeezed from {_n(b['pct_hardship'])}% to {_n(s['pct_hardship'])}%, and "
                   f"priced out from {_n(b['pct_left_out'])}% to {_n(s['pct_left_out'])}%.")
    else:
        en_head = (f"Compared with today, the share served moves from {_n(b['pct_served'])}% to {_n(s['pct_served'])}%, "
                   f"hardship from {_n(b['pct_hardship'])}% to {_n(s['pct_hardship'])}%, and left out from "
                   f"{_n(b['pct_left_out'])}% to {_n(s['pct_left_out'])}%.")
    ar = (f"مقارنة {w['today_ar']}، تتغير نسبة {sv_ar} من {_n(b['pct_served'])}% إلى {_n(s['pct_served'])}%، "
          f"ونسبة {hd_ar} من {_n(b['pct_hardship'])}% إلى {_n(s['pct_hardship'])}%، "
          f"ونسبة {lo_ar} من {_n(b['pct_left_out'])}% إلى {_n(s['pct_left_out'])}%.")
    en = en_head
    if service == TRAVEL:
        ar += (f" أي إن الرحلة المنتظمة بموجب هذا القرار تضغط ميزانية {_n(s['pct_hardship'])}% من السكان، "
               f"وتفوق قدرة {_n(s['pct_left_out'])}% منهم.")
        extra = ((summary.get("travel") or {}).get("scenario") or {}).get("avg_extra_jd_month")
        if isinstance(extra, (int, float)) and abs(extra) >= 0.05:
            ar += (f" و{'يرتفع' if extra > 0 else 'ينخفض'} متوسط الكلفة الشهرية للرحلة بمقدار "
                   f"{count_ar(extra, 'dinar', 'gen')}.")
            en += f" The average trip costs {_n(abs(extra))} JD a month {'more' if extra > 0 else 'less'}."
    if not top:
        ar += f" لا تسوء أوضاع أي فئة مقارنة {w['today_ar']}."
        en += " No group is worse off than today."
    elif len(top) == 1:
        x = top[0]
        ar += (f" أكثر الفئات تضرراً {GROUP_LABELS[x][0]}، إذ ترتفع بينهم نسبة {w['both_ar']} "
               f"بمقدار {count_ar(g[x], 'point', 'gen')}.")
        en += f" Hardest hit: {GROUP_LABELS[x][1]} ({w['both_en']} up {_pts_en(g[x])})."
    else:
        x, y = top
        ar += (f" أكثر الفئات تضرراً {GROUP_LABELS[x][0]} ثم {GROUP_LABELS[y][0]}، إذ ترتفع بينهم نسبة {w['both_ar']} "
               f"بمقدار {count_ar(g[x], 'point', 'gen')} و{count_ar(g[y], 'point', 'gen')} "
               f"على التوالي.")
        en += (f" Hardest hit: {GROUP_LABELS[x][1]} and {GROUP_LABELS[y][1]} ({w['both_en']} up "
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
        ar += (f" بعد تطبيق الحل المختار تصبح نسبة {sv_ar} {_n(k['pct_served'])}%، ونسبة {hd_ar} "
               f"{_n(k['pct_hardship'])}%، ونسبة {lo_ar} {_n(k['pct_left_out'])}%، {better_ar}.")
        en += (f" With the chosen fix applied: {_n(k['pct_served'])}% {sv_en}, {_n(k['pct_hardship'])}% {hd_en2}, "
               f"{_n(k['pct_left_out'])}% {lo_en}, and {n} {'person' if n == 1 else 'people'} better off "
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
