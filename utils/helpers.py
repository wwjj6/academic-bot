# -*- coding: utf-8 -*-
"""أدوات مساعدة عامة."""
import json
import os
import re
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

ADMIN_IDS = set(CONFIG.get("admin_ids", []))
ADMIN_USERNAMES = {u.lstrip("@").lower() for u in CONFIG.get("admin_usernames", [])}


def is_admin_user(tg_user):
    """مشرف عام: بالمعرف الرقمي أو باسم المستخدم في تيليجرام."""
    if tg_user.id in ADMIN_IDS:
        return True
    return bool(tg_user.username) and tg_user.username.lower() in ADMIN_USERNAMES

OPTION_LABELS = {"a": "أ", "b": "ب", "c": "ج", "d": "د"}
COMP_TYPE_LABELS = {
    "weekly": "🗓 أسبوعية",
    "monthly": "📅 شهرية",
    "challenge": "🔥 تحدي ما قبل الامتحان",
    "general": "🌐 عامة",
}
STATUS_LABELS = {
    "draft": "📝 مسودة",
    "pending_review": "⏳ بانتظار المراجعة",
    "approved": "✅ معتمدة (مجدولة)",
    "active": "🟢 نشطة الآن",
    "closed": "🔒 مغلقة",
    "rejected": "❌ مرفوضة",
}

DATETIME_FMT = "%Y-%m-%d %H:%M"


def parse_datetime(text):
    """تحويل نص مثل 2026-07-15 18:30 إلى datetime، أو None عند الفشل."""
    text = text.strip()
    for fmt in (DATETIME_FMT, "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def fmt_datetime(dt):
    if isinstance(dt, str):
        return dt
    return dt.strftime(DATETIME_FMT)


def is_valid_university_id(text):
    """رقم جامعي: أرقام فقط بطول 4-15."""
    return bool(re.fullmatch(r"\d{4,15}", text.strip()))


def medal(rank):
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")


def format_leaderboard(rows, title="🏆 الترتيب"):
    if not rows:
        return f"{title}\n\nلا توجد نتائج بعد."
    lines = [title, ""]
    for i, r in enumerate(rows, start=1):
        pts = r["points"] if "points" in r.keys() else r["score"]
        lines.append(f"{medal(i)} {r['full_name']} — {pts} نقطة")
    return "\n".join(lines)
