"""
اتصال به یک مدلِ تصویریِ محلی از طریق Ollama.

عکس‌های جلسهٔ ریموت + فهرستِ «موارد»ِ سازمان را می‌فرستد و از مدل می‌خواهد
بگوید کدام موارد انجام شده‌اند و یک توضیح کوتاهِ فارسی بنویسد.

- کاملاً محلی/آفلاین: به Ollama روی همین سیستم (یا یک سرورِ داخلی) وصل می‌شود.
- اگر مدل/سرور در دسترس نبود، None برمی‌گرداند تا برنامه به قواعدِ کلیدواژه‌ای
  برگردد (هیچ‌وقت خطا پرت نمی‌کند).
- زبان‌مستقل: مدل پیکسلِ صفحه را می‌بیند، پس فارسی/انگلیسیِ صفحه فرقی ندارد.
"""
import os
import json
import base64
import urllib.request

from services.debug_log import log

_PROMPT = (
    "تو دستیارِ یک کارشناسِ پشتیبانیِ IT هستی. این تصویرها اسکرین‌شاتِ یک جلسهٔ "
    "اتصالِ ریموت (DameWare) به کامپیوترِ یک کاربر است. با نگاه به تصویرها تشخیص بده "
    "کدام‌یک از «کارهای مجاز» زیر انجام شده است. فقط از همین فهرست انتخاب کن و چیزی "
    "از خودت اضافه نکن.\n\n"
    "کارهای مجاز:\n{task_list}\n\n"
    "خروجی را فقط به‌صورت JSON بده با این ساختار:\n"
    '{{"tasks": ["عنوانِ دقیقِ کارِ انجام‌شده", ...], "summary": "یک جملهٔ کوتاهِ فارسی"}}\n'
    "اگر مطمئن نیستی، tasks را خالی بگذار."
)


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def analyze(image_paths, task_titles, cfg):
    """
    image_paths: مسیرِ چند PNG. task_titles: فهرستِ عنوانِ موارد.
    خروجی: {"titles": [...], "summary": "..."} یا None در صورتِ عدم‌دسترسی.
    """
    if not image_paths or not task_titles:
        return None
    url = (cfg.get("vision_url") or "http://localhost:11434").rstrip("/") + "/api/generate"
    model = cfg.get("vision_model") or "moondream"
    timeout = int(cfg.get("vision_timeout", 120))

    images = []
    for p in image_paths[:3]:  # حداکثر ۳ کی‌فریم تا سریع بماند
        try:
            images.append(_b64(p))
        except Exception:
            pass
    if not images:
        return None

    task_list = "\n".join(f"- {t}" for t in task_titles)
    prompt = _PROMPT.format(task_list=task_list)
    body = {
        "model": model,
        "prompt": prompt,
        "images": images,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("response") or "").strip()
        log(f"vision: model={model} raw={text[:200]!r}")
        parsed = json.loads(text)
        titles = parsed.get("tasks") or []
        if isinstance(titles, str):
            titles = [titles]
        return {"titles": [str(t) for t in titles], "summary": str(parsed.get("summary") or "")}
    except Exception as e:
        log(f"vision: در دسترس نیست/خطا ({model} @ {url}): {e!r}")
        return None


def is_configured(cfg):
    return bool(cfg.get("vision_enabled"))
