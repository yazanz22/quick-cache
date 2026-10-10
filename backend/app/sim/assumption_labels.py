"""Arabic/English display labels for the AssumptionsTable. Text only: no values live here,
so the frozen numbers in assumptions.py are untouched (CLAUDE.md §6.2)."""

# name: (label_ar, label_en, rationale_ar)
LABELS = {
    "SERVICE_MINUTES": ("مدة الخدمة في المكتب", "Service time at the office", "وقت الانتظار والمعاملة عند الشباك في زيارة واحدة"),
    "ONLINE_MINUTES": ("مدة الخدمة الإلكترونية", "Online service time", "وقت إنجاز المعاملة أو حجز الموعد عبر الإنترنت"),
    "HOME_VISIT_MINUTES": ("مدة الزيارة المنزلية", "Home visit time", "انتظار الموظف في البيت ضمن نافذة زيارة مدتها ساعتان"),
    "PICKUP_MINUTES": ("مدة استلام البطاقة", "Card pickup time", "زيارة قصيرة للشباك لاستلام بطاقة قُدّم طلبها إلكترونياً"),
    "TRAFFIC_FACTOR": ("معامل الازدحام", "Traffic factor", "زمن الرحلة نهاراً مقارنة بأزمنة OSRM دون ازدحام (الأزمنة نفسها من بيانات OpenStreetMap)"),
    "ROAD_FACTOR": ("معامل طول الطريق (احتياطي)", "Road factor (fallback)", "احتياطي فقط: نسبة طول الطريق إلى الخط المستقيم (الوسيط في OSRM نحو 1.4-1.5)"),
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
    "WEEKS_PER_MONTH": ("أسابيع الشهر", "Weeks per month", "لتحويل عدد الرحلات الأسبوعية إلى كلفة شهرية"),
    "INCOME_JD_MONTH": ("الدخل الشهري للفرد حسب الشريحة", "Per-capita monthly income by band", "قيمة تمثيلية لدخل الفرد الشهري في كل شريحة دخل، وليست إحصاءً"),
    "TRANSPORT_SHARE_SQUEEZED": ("حد الضغط على الميزانية", "Squeezed-budget threshold", "رحلة منتظمة تكلف هذه النسبة من الدخل أو أكثر تعني ميزانية مضغوطة"),
    "TRANSPORT_SHARE_PRICED_OUT": ("حد العجز عن التنقل", "Priced-out threshold", "عند هذه النسبة من الدخل أو أكثر تصبح الرحلة غير محتملة"),
    "FUEL_SHARE_OF_CAR_COST": ("حصة الوقود من كلفة السيارة", "Fuel share of car cost", "نسبة الوقود من كلفة تشغيل السيارة لكل كيلومتر"),
    "BUS_FARE_FUEL_PASS_THROUGH": ("انعكاس الوقود على أجرة الحافلة", "Fuel pass-through to bus fares", "النسبة التي تنقلها أجرة الحافلة المنظّمة من أي تغيير في سعر الوقود"),
    "TAXI_FARE_FUEL_PASS_THROUGH": ("انعكاس الوقود على تعرفة التاكسي", "Fuel pass-through to taxi fares", "النسبة التي تنقلها تعرفة التاكسي لكل كيلومتر من أي تغيير في سعر الوقود"),
    "EXEMPTION_VISIT_MINUTES": ("مدة زيارة الإعفاء الطبي", "Medical-exemption visit time", "الانتظار ومراجعة طبيب وزارة الصحة في زيارة واحدة لدائرة خدمة الجمهور في الديوان الملكي"),
    "UNINSURED_RATE_BY_BAND": ("نسبة غير المؤمَّنين صحياً حسب الدخل", "Uninsured share by income band", "نسبة البالغين بلا تأمين صحي في كل شريحة دخل، معايَرة لتعطي نحو 46% إجمالاً"),
}

# Arabic text of the `source` notes in assumptions.META (same constants, same meaning; the tag stays ASSUMPTION).
SOURCE_AR = {
    "TRAFFIC_FACTOR": "يُضرب في أزمنة OSRM دون ازدحام (بيانات OpenStreetMap)؛ لم نجد بيانات ازدحام لعمّان",
    "ROAD_FACTOR": "مصفوفة OSRM: وسيط نسبة طول الطريق إلى الخط المستقيم 1.44",
    "BUS_FIRST_WAIT_MIN": "دراسة من عام 2017 أوردها بحثنا قاست انتظاراً يقارب 25 دقيقة وقت الذروة (غير مُتحقَّق منها)؛ نفترض 10 دقائق، و15 دقيقة لكل تبديل، خارج الذروة",
    "BUS_WAIT_PLUS_TRANSFER_MIN": "دراسة انتظار الذروة نفسها من عام 2017 (غير مُتحقَّق منها)؛ تُختبر هذه القيمة عند ±20%",
    "BUS_FARE_JD": "الأجرة العامة بين 0.34 و0.55 دينار لكل ركوب، من بحثنا، غير مُتحقَّق منها",
    "TAXI_BASE_JD": "لم نجد تعرفة موثَّقة لسيارات الأجرة صادرة عن هيئة تنظيم النقل البري",
    "TAXI_PER_KM_JD": "لم نجد تعرفة موثَّقة لسيارات الأجرة صادرة عن هيئة تنظيم النقل البري",
    "INCOME_JD_MONTH": "وسيط دخل الفرد الافتراضي في كل شريحة كما أنتجه مولّد السكان (133 / 344 / 942 ديناراً)، مقرّباً؛ ليس إحصاءً",
    "TRANSPORT_SHARE_SQUEEZED": "معيار 10% المعتاد في دراسات القدرة على تحمّل كلفة النقل؛ بحثنا يورد أن انتظار الحافلات وحده قد يكلف حتى 12% من الدخل",
    "BUS_FARE_FUEL_PASS_THROUGH": "أجور الحافلات تحددها هيئة تنظيم النقل البري وتتحرك أقل من الوقود؛ لم نجد نسبة انعكاس منشورة",
    "EXEMPTION_VISIT_MINUTES": "تصف التقارير الصحفية التقديم حضورياً مع مراجعة طبيب من وزارة الصحة وزيارة ثانية لاستلام الكتاب؛ لا يوجد زمن انتظار منشور",
    "UNINSURED_RATE_BY_BAND": "معايَرة لتعطي نحو 46% إجمالاً: ورقة دائرة الإحصاءات العامة عن تعداد 2015، 44.8% من أردنيي عمّان بلا تأمين (كل الأعمار؛ الأطفال دون 6 سنوات مؤمَّنون جميعاً، فالبالغون أعلى)",
}


def label_rows(rows: list[dict]) -> list[dict]:
    for r in rows:
        ar, en, why_ar = LABELS.get(r["name"], (None, None, None))
        r.update(label_ar=ar, label_en=en, rationale_en=r["rationale"], rationale_ar=why_ar or r["rationale"],
                 source_en=r.get("source"), source_ar=SOURCE_AR.get(r["name"]) if r.get("source") else None)
    return rows
