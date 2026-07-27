# -*- coding: utf-8 -*-
"""
قراءة/كتابة إعدادات البوت (config.json) مع الحفاظ على القيم الحالية كافتراضية.
يُستخدم من لوحة تحكم Flask.
"""
import os
import json
import shutil
from datetime import datetime

# مجلد المشروع (الأصل) — config.json يوجد فيه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# القيم الافتراضية الكاملة لأي بوت (تُستخدم عند غياب الملف أو نقص مفتاح)
DEFAULT_CONFIG = {
    "bot_token": "",
    "bot_name": "المسابقات الأكاديمية - كلية الطب | جامعة حجة",
    "admin_ids": [],
    "admin_usernames": [],
    "database_path": "academic_bot.db",
    "timezone": "Asia/Aden",
    "min_questions": 5,
    "max_questions": 50,
    "default_question_seconds": 60,
    "top_n_leaderboard": 10,
}

# أنواع الحقول لضبط التحويل من نموذج الويب
INT_FIELDS = ("min_questions", "max_questions",
              "default_question_seconds", "top_n_leaderboard")
LIST_INT_FIELDS = ("admin_ids",)
LIST_STR_FIELDS = ("admin_usernames",)
STR_FIELDS = ("bot_token", "bot_name", "database_path", "timezone")


def load_config():
    """تحميل الإعدادات الحالية مدموجة فوق الافتراضية."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg):
    """
    حفظ الإعدادات بشكل ذرّي: كتابة إلى ملف مؤقت ثم استبدال الأصل،
    مع أخذ نسخة احتياطية. يمنع تلف الملف لو تعطّل البرنامج أثناء الحفظ.
    """
    if os.path.exists(CONFIG_PATH):
        try:
            shutil.copy2(CONFIG_PATH, CONFIG_PATH + ".bak")
        except OSError:
            pass
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
        f.flush()
        os.fsync(f.fileno())
    # os.replace ذرّي على نفس القرص (يدعمه ويندوز ولينكس)
    os.replace(tmp_path, CONFIG_PATH)


def _parse_int_list(text):
    """تحويل نص (أرقام مفصولة بفواصل/أسطر/مسافات) إلى قائمة أعداد صحيحة."""
    out = []
    for part in text.replace(",", "\n").replace(" ", "\n").split("\n"):
        part = part.strip()
        if part:
            try:
                out.append(int(part))
            except ValueError:
                pass
    return out


def _parse_str_list(text):
    """تحويل نص إلى قائمة نصوص (إزالة @ والمسافات)."""
    out = []
    for part in text.replace(",", "\n").split("\n"):
        part = part.strip().lstrip("@")
        if part:
            out.append(part)
    return out


def build_config_from_form(form, current):
    """
    بناء قاموس إعدادات جديد من بيانات نموذج الويب،
    مع الاحتفاظ بالقيم الحالية لأي حقل غير موجود في النموذج.
    """
    cfg = dict(current)

    for field in STR_FIELDS:
        if field in form:
            value = form.get(field, "").strip()
            # لا تمسح التوكن إذا تُرك فارغاً (حماية من الحذف بالخطأ)
            if field == "bot_token" and not value:
                continue
            cfg[field] = value

    for field in INT_FIELDS:
        if field in form:
            raw = form.get(field, "").strip()
            if raw:
                try:
                    cfg[field] = int(raw)
                except ValueError:
                    pass

    for field in LIST_INT_FIELDS:
        if field in form:
            cfg[field] = _parse_int_list(form.get(field, ""))

    for field in LIST_STR_FIELDS:
        if field in form:
            cfg[field] = _parse_str_list(form.get(field, ""))

    return cfg
