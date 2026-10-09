"""Arabic/English display labels for the AssumptionsTable. Text only: no values live here,
so the frozen numbers in assumptions.py are untouched (CLAUDE.md §6.2)."""

# name: (label_ar, label_en, rationale_ar)
LABELS = {
    "SERVICE_MINUTES": ("مدة الخدمة في المكتب", "Service time at the office", "وقت الانتظار والمعاملة عند الشباك في زيارة واحدة"),
    "ONLINE_MINUTES": ("مدة الخدمة الإلكترونية", "Online service time", "وقت إنجاز المعاملة أو حجز الموعد عبر الإنترنت"),
    "TRAFFIC_FACTOR": ("معامل الازدحام", "Traffic factor", "زمن الرحلة نهاراً مقارنة بأزمنة OSRM دون ازدحام (الأزمنة نفسها من بيانات OpenStreetMap)"),
    "ROAD_FACTOR": ("معامل طول الطريق (احتياطي)", "Road factor (fallback)", "احتياطي فقط: نسبة طول الطريق إلى الخط المستقيم (الوسيط في OSRM هو 1.51)"),
    "CAR_SPEED_KMH": ("سرعة السيارة (احتياطي)", "Car speed (fallback)", "احتياطي فقط: سرعة السيارة في المدينة مع الازدحام"),
    "CAR_PARK_MIN": ("وقت الاصطفاف", "Parking time", "الاصطفاف والمشي حتى الشباك"),
    "CAR_COST_PER_KM_JD": ("كلفة السيارة لكل كم", "Car cost per km", "الوقود والاستهلاك لكل كيلومتر"),
    "BUS_SPEED_KMH": ("سرعة الحافلة", "Bus speed", "سرعة الحافلة مع التوقفات"),
    "BUS_WALK_MIN": ("المشي إلى الموقف", "Walk to the stop", "المشي من البيت إلى الموقف ومن الموقف إلى المكتب"),
    "LIMITED_MOBILITY_WALK_FACTOR": ("بطء المشي لذوي الحركة المحدودة", "Slower walking, limited mobility", "مضاعف وقت المشي لمن لديهم صعوبة في الحركة"),
    "BUS_FIRST_WAIT_MIN": ("انتظار الحافلة الأولى", "First bus wait", "انتظار أول حافلة"),
    "BUS_WAIT_PLUS_TRANSFER_MIN": ("وقت كل تبديل حافلة", "Time per bus transfer", "الانتظار والمشي الإضافي عند كل تبديل"),
    "BUS_FARE_JD": ("أجرة الحافلة", "Bus fare", "الأجرة لكل ركوب"),
    "TAXI_WAIT_MIN": ("انتظار سيارة الأجرة", "Taxi wait", "انتظار أو طلب سيارة أجرة"),
    "TAXI_BASE_JD": ("فتحة العداد", "Taxi flag fall", "الأجرة الأساسية لسيارة الأجرة"),
    "TAXI_PER_KM_JD": ("أجرة التاكسي لكل كم", "Taxi rate per km", "أجرة سيارة الأجرة لكل كيلومتر"),
    "TAXI_MAX_JD": ("أقصى ما تدفعه الأسرة للتاكسي", "Most a household pays for a taxi", "أقصى كلفة لرحلة ذهاب وإياب بالتاكسي حسب الدخل"),
    "MAX_TRAVEL_MINUTES": ("أطول رحلة معقولة", "Longest realistic trip", "أطول زمن رحلة باتجاه واحد لمعاملة"),
    "LONG_TRIP_MINUTES": ("حد الرحلة البعيدة", "Long-trip threshold", "زمن الرحلة الذي يُعدّ بعيداً في أسباب المشقة"),
    "MAX_WORK_HOURS_MISSED": ("أقصى ساعات عمل يمكن خسارتها", "Most work hours one can miss", "أقصى ساعات غياب عن العمل حسب الدخل"),
    "HELPER_FREE_FROM": ("متى يتفرغ المساعد", "When the helper is free", "متى يستطيع فرد العائلة العامل الإيصال في أيام الدوام"),
    "HARDSHIP_THRESHOLD": ("حد المشقة", "Hardship threshold", "العبء الذي يُعدّ مشقة: نصف يوم عمل"),
    "COST_WEIGHT": ("وزن الكلفة", "Cost weight", "ساعات العبء مقابل كل دينار يُدفع"),
    "WORK_WEIGHT": ("وزن ساعات العمل الضائعة", "Work-hours weight", "وزن إضافي لكل ساعة عمل ضائعة"),
}


def label_rows(rows: list[dict]) -> list[dict]:
    for r in rows:
        ar, en, why_ar = LABELS.get(r["name"], (None, None, None))
        r.update(label_ar=ar, label_en=en, rationale_en=r["rationale"], rationale_ar=why_ar or r["rationale"])
    return rows
