# -*- coding: utf-8 -*-
"""
جدولة المسابقات: تفعيل تلقائي عند وقت البدء، إغلاق تلقائي عند وقت الانتهاء،
وإرسال إشعارات مستهدفة لطلاب المقرر المعني فقط.
"""
import logging
from datetime import datetime

from telegram.ext import ContextTypes

from database import db
from utils.helpers import COMP_TYPE_LABELS, DATETIME_FMT, format_leaderboard
from utils.keyboards import join_competition_keyboard

logger = logging.getLogger(__name__)


async def notify_subject_students(bot, subject_id, text, reply_markup=None):
    """إرسال إشعار لطلاب مقرر محدد فقط، أو لجميع الطلاب إذا كانت المسابقة عامة."""
    if subject_id is None:
        students = db.get_users_by_role("student")
    else:
        students = db.get_subject_students(subject_id)
    sent = 0
    for s in students:
        try:
            await bot.send_message(s["user_id"], text, reply_markup=reply_markup)
            sent += 1
        except Exception as e:  # المستخدم حظر البوت مثلاً
            logger.warning("تعذر الإرسال إلى %s: %s", s["user_id"], e)
    return sent


async def _open_competition_job(context: ContextTypes.DEFAULT_TYPE):
    comp_id = context.job.data["competition_id"]
    comp = db.get_competition(comp_id)
    if not comp or comp["status"] != "approved":
        return
    db.set_competition_status(comp_id, "active")
    subject = db.get_subject(comp["subject_id"]) if comp["subject_id"] else None
    subject_name = subject["name"] if subject else "جميع المقررات (عامة)"
    text = (
        f"🚨 بدأت الآن مسابقة جديدة!\n\n"
        f"🏷 {comp['title']}\n"
        f"📚 المقرر: {subject_name}\n"
        f"📌 النوع: {COMP_TYPE_LABELS.get(comp['comp_type'], comp['comp_type'])}\n"
        f"❓ عدد الأسئلة: {comp['num_questions']}\n"
        f"⏱ زمن كل سؤال: {comp['question_seconds']} ثانية\n"
        f"🔚 تُغلق: {comp['end_time']}\n\n"
        f"بالتوفيق! 🍀"
    )
    await notify_subject_students(context.bot, comp["subject_id"], text,
                                  reply_markup=join_competition_keyboard(comp_id))


async def _close_competition_job(context: ContextTypes.DEFAULT_TYPE):
    comp_id = context.job.data["competition_id"]
    comp = db.get_competition(comp_id)
    if not comp or comp["status"] != "active":
        return
    db.set_competition_status(comp_id, "closed")

    # إعلان النتائج + Top 10
    top = db.get_competition_results(comp_id, limit=10)
    lines = [f"🔒 انتهت مسابقة: {comp['title']}", "", "🏆 أفضل 10 مشاركين:"]
    if top:
        from utils.helpers import medal
        for i, r in enumerate(top, start=1):
            lines.append(f"{medal(i)} {r['full_name']} — {r['score']}/{r['total']} "
                         f"({r['time_taken']} ث)")
    else:
        lines.append("لم يشارك أحد في هذه المسابقة.")
    text = "\n".join(lines)

    await notify_subject_students(context.bot, comp["subject_id"], text)
    # إشعار منشئ المسابقة
    try:
        await context.bot.send_message(comp["creator_id"], text)
    except Exception:
        pass


def schedule_competition(job_queue, comp):
    """جدولة فتح وإغلاق مسابقة معتمدة. تُستدعى عند الاعتماد وعند إقلاع البوت."""
    comp_id = comp["competition_id"]
    now = datetime.now()

    start = datetime.strptime(comp["start_time"], DATETIME_FMT)
    end = datetime.strptime(comp["end_time"], DATETIME_FMT)

    if comp["status"] == "approved":
        delay = max(0, (start - now).total_seconds())
        job_queue.run_once(_open_competition_job, when=delay,
                           data={"competition_id": comp_id},
                           name=f"open_{comp_id}")
    if end > now:
        job_queue.run_once(_close_competition_job,
                           when=(end - now).total_seconds(),
                           data={"competition_id": comp_id},
                           name=f"close_{comp_id}")
    else:
        # موعد الإغلاق مضى أثناء توقف البوت
        db.set_competition_status(comp_id, "closed")


def reschedule_all(job_queue):
    """إعادة جدولة كل المسابقات المعلقة عند إقلاع البوت."""
    for comp in db.get_scheduled_competitions():
        try:
            schedule_competition(job_queue, comp)
        except Exception as e:
            logger.error("فشل جدولة المسابقة %s: %s", comp["competition_id"], e)
