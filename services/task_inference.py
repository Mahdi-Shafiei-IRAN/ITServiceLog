"""
مغزِ تشخیصِ خودکار: از روی متنِ OCRِ جمع‌شده در طول جلسهٔ ریموت، حدس می‌زند
کدام «موارد» انجام شده و یک توضیح کوتاه می‌سازد.

این ماژول کاملاً بدونِ مدل و آفلاین است: ترکیبی از (۱) تطبیق مستقیمِ عنوانِ
مورد در متن و (۲) قوانینِ کلیدواژه‌ایِ قابل‌ویرایش (کلیدواژهٔ انگلیسیِ روی
صفحه → عنوانِ فارسیِ مورد). قوانین در فایل session_ai_config.json کنارِ
دیتابیس ذخیره می‌شوند و مدیر می‌تواند بدونِ build مجدد آن‌ها را تنظیم کند.
"""
import os
import json

# یکسان‌سازیِ حروفِ عربی/فارسی + حذفِ نیم‌فاصله برای تطبیقِ بهتر.
_NORM = str.maketrans({"ي": "ی", "ك": "ک", "‌": " ", "ي": "ی"})


def _norm(s):
    return (s or "").translate(_NORM).lower()


# قوانینِ پیش‌فرض: هر قانون یعنی «اگر یکی از keywords در متنِ صفحه دیده شد،
# هر موردی که عنوانش شاملِ یکی از match_title باشد تیک بخورد».
# این‌ها حدس‌های متعارفِ محیطِ IT ایران‌اند؛ مدیر می‌تواند ویرایش/تکمیل کند.
DEFAULT_RULES = [
    {"keywords": ["windows update", "update", "kb5", "kb4", "به‌روزرسانی", "اپدیت", "آپدیت"],
     "match_title": ["ویندوز", "به‌روز", "اپدیت", "آپدیت", "update"]},
    {"keywords": ["printer", "print spooler", "spooler", "print", "چاپگر", "پرینتر", "چاپ"],
     "match_title": ["چاپ", "پرینت", "چاپگر", "print"]},
    {"keywords": ["ipconfig", "ping", "ethernet", "network", "dns", "dhcp", "lan", "شبکه"],
     "match_title": ["شبکه", "اینترنت", "network", "lan", "اتصال"]},
    {"keywords": ["defender", "antivirus", "virus", "kaspersky", "eset", "nod32", "آنتی", "ویروس"],
     "match_title": ["آنتی", "ویروس", "antivirus"]},
    {"keywords": ["outlook", "smtp", "imap", "mailbox", "webmail", "ایمیل", "میل"],
     "match_title": ["ایمیل", "میل", "mail", "outlook", "نامه"]},
    {"keywords": ["word", "excel", "powerpoint", "office", "activation", "آفیس", "افیس"],
     "match_title": ["آفیس", "افیس", "office", "word", "excel", "افیس"]},
    {"keywords": ["driver", "device manager", "درایور"],
     "match_title": ["درایور", "driver", "سخت‌افزار", "سخت افزار"]},
    {"keywords": ["anydesk", "teamviewer", "remote desktop", "rdp", "ریموت"],
     "match_title": ["ریموت", "remote", "anydesk", "teamviewer"]},
    {"keywords": ["chkdsk", "format", "partition", "disk management", "هارد", "دیسک"],
     "match_title": ["هارد", "دیسک", "disk", "پارتیشن", "فرمت"]},
    {"keywords": ["password", "account", "domain", "login", "sign in", "رمز", "پسورد", "کاربری"],
     "match_title": ["رمز", "پسورد", "کاربر", "password", "اکانت", "دامین", "لاگین"]},
    {"keywords": ["backup", "restore", "بکاپ", "پشتیبان"],
     "match_title": ["بکاپ", "پشتیبان", "backup"]},
]

DEFAULT_CONFIG = {
    "enabled": True,
    "interval_seconds": 8,
    "dameware_ports": [6129, 6130, 6132, 6133],
    # --- مدلِ تصویریِ محلی (Ollama) ---
    "vision_enabled": True,
    "vision_url": "http://localhost:11434",
    "vision_model": "moondream",
    "vision_timeout": 120,
    "rules": DEFAULT_RULES,
}


def _config_path():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "ITServiceLog", "session_ai_config.json")


def load_config():
    """تنظیماتِ دستیارِ هوشمند را می‌خواند؛ اگر نبود، پیش‌فرض را می‌سازد."""
    path = _config_path()
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user.get("enabled"), bool):
                cfg["enabled"] = user["enabled"]
            if isinstance(user.get("interval_seconds"), (int, float)):
                cfg["interval_seconds"] = int(user["interval_seconds"])
            if isinstance(user.get("dameware_ports"), list) and user["dameware_ports"]:
                cfg["dameware_ports"] = [int(p) for p in user["dameware_ports"]
                                        if str(p).isdigit()] or cfg["dameware_ports"]
            for key in ("vision_enabled",):
                if isinstance(user.get(key), bool):
                    cfg[key] = user[key]
            for key in ("vision_url", "vision_model"):
                if isinstance(user.get(key), str) and user[key].strip():
                    cfg[key] = user[key].strip()
            if isinstance(user.get("vision_timeout"), (int, float)):
                cfg["vision_timeout"] = int(user["vision_timeout"])
            if isinstance(user.get("rules"), list) and user["rules"]:
                cfg["rules"] = user["rules"]
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return cfg


def infer(evidence_text, tasks, rules=None):
    """
    ورودی:
      evidence_text: کلِ متنِ OCRِ جمع‌شده در طولِ جلسه.
      tasks: لیستی از (task_id, title).
      rules: در صورت None از config خوانده می‌شود.
    خروجی: dict شاملِ task_ids (لیست), titles (لیست), description (str).
    """
    if rules is None:
        rules = load_config()["rules"]
    ev = _norm(evidence_text)
    matched = {}  # task_id -> title (حفظِ ترتیب با dict)

    # ۱) تطبیقِ مستقیم: اگر عنوانِ خودِ مورد در متنِ صفحه دیده شود.
    for tid, title in tasks:
        nt = _norm(title)
        if len(nt) >= 3 and nt in ev and tid not in matched:
            matched[tid] = title

    # ۲) قوانینِ کلیدواژه‌ای: کلیدواژهٔ صفحه → عنوانِ موردِ متناظر.
    for rule in rules:
        kws = rule.get("keywords", [])
        if not any(_norm(k) in ev for k in kws if k):
            continue
        targets = [_norm(m) for m in rule.get("match_title", []) if m]
        for tid, title in tasks:
            if tid in matched:
                continue
            nt = _norm(title)
            if any(t in nt for t in targets):
                matched[tid] = title

    titles = list(matched.values())
    return {
        "task_ids": list(matched.keys()),
        "titles": titles,
        "description": "، ".join(titles),
        "source": "rules",
    }


def map_titles_to_ids(model_titles, tasks):
    """عنوان‌هایی که مدل برگردانده را به شناسهٔ تسک‌های واقعی نگاشت می‌کند."""
    matched = {}
    norm_tasks = [(tid, title, _norm(title)) for tid, title in tasks]
    for mt in model_titles:
        nmt = _norm(mt)
        if not nmt:
            continue
        for tid, title, nt in norm_tasks:
            if tid in matched:
                continue
            # تطبیقِ کامل یا زیررشته‌ای (مدل ممکن است کمی متفاوت بنویسد)
            if nt == nmt or nt in nmt or nmt in nt:
                matched[tid] = title
    return matched


def infer_vision(image_paths, tasks, cfg=None):
    """
    تشخیص با مدلِ تصویریِ محلی. اگر مدل در دسترس نبود None برمی‌گرداند تا
    فراخواننده به infer() (قواعد) برگردد.
    """
    from services import vision_model
    if cfg is None:
        cfg = load_config()
    if not vision_model.is_configured(cfg):
        return None
    result = vision_model.analyze(image_paths, [t for _, t in tasks], cfg)
    if not result:
        return None
    matched = map_titles_to_ids(result.get("titles", []), tasks)
    titles = list(matched.values())
    description = (result.get("summary") or "").strip() or "، ".join(titles)
    return {
        "task_ids": list(matched.keys()),
        "titles": titles,
        "description": description,
        "source": "vision",
    }
