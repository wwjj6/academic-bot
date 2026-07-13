# -*- coding: utf-8 -*-
"""
معالج الطالب + محرك المسابقات:
- عرض المسابقات النشطة لمقررات الطالب
- المشاركة: سؤال واحد في كل مرة، عداد تنازلي، بلا رجوع، إغلاق تلقائي
- نتيجة فورية + ترتيب Top 10
- إدارة المقررات المسجلة
"""
import logging
import time

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from database import db
from utils.helpers import (CONFIG, COMP_TYPE_LABELS, OPTION_LABELS, medal)
from utils.keyboards import (back_to_menu_keyboard, join_competition_keyboard,
                             question_options_keyboard, student_menu,
                             subjects_keyboard)

logger = logging.getLogger(__name__)

TOP_N = CONFIG.get("top_n_leaderboard", 10)


# ===================================================== المسابقات المتاحة ==

async def list_competitions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comps = db.get_active_competitions_for_student(query.from_user.id)
    if not comps:
        await query.edit_message_text(
            "لا توجد مسابقات نشطة لمقرراتك حالياً. 🕐\n"
            "ستصلك الإشعارات تلقائياً عند بدء مسابقة جديدة.",
            reply_markup=back_to_menu_keyboard())
        return
    await query.edit_message_text("🎯 المسابقات المتاحة لك الآن:")
    for c in comps:
        text = (f"🏷 {c['title']}\n"
                f"📚 المقرر: {c['subject_name'] or 'عامة (جميع الطلاب)'}\n"
                f"📌 النوع: {COMP_TYPE_LABELS.get(c['comp_type'])}\n"
                f"❓ الأسئلة: {c['num_questions']} | "
                f"⏱ {c['question_seconds']} ثانية للسؤال\n"
                f"🔚 تُغلق: {c['end_time']}")
        await query.message.reply_text(
            text, reply_markup=join_competition_keyboard(c["competition_id"]))


# ========================================================= محرك المسابقة ==

async def join_competition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    comp = db.get_competition(int(query.data.split("_")[1]))

    if not comp or comp["status"] != "active":
        await query.answer("⚠️ هذه المسابقة غير نشطة حالياً.", show_alert=True)
        return
    # منع المشاركة المتكررة
    if any(r["user_id"] == user_id for r in db.get_competition_results(comp["competition_id"])):
        await query.answer("لقد شاركت في هذه المسابقة من قبل! ✋", show_alert=True)
        return
    if context.user_data.get("quiz"):
        await query.answer("لديك مسابقة جارية بالفعل! أكملها أولاً.", show_alert=True)
        return

    questions = db.get_competition_questions(comp["competition_id"], approved_only=True)
    if not questions:
        await query.answer("⚠️ لا توجد أسئلة معتمدة في هذه المسابقة.", show_alert=True)
        return
    questions = questions[: comp["num_questions"]]

    await query.answer()
    context.user_data["quiz"] = {
        "comp_id": comp["competition_id"],
        "subject_id": comp["subject_id"],
        "questions": [dict(q) for q in questions],
        "index": 0,
        "score": 0,
        "started_at": time.time(),
        "seconds": comp["question_seconds"],
    }
    await query.edit_message_text(
        f"🚀 بدأت مسابقة: {comp['title']}\n\n"
        f"📜 القواعد:\n"
        f"• {len(questions)} سؤال، لكل سؤال {comp['question_seconds']} ثانية ⏳\n"
        f"• سؤال واحد في كل مرة — لا يمكن الرجوع للخلف\n"
        f"• عدم الإجابة قبل انتهاء الوقت = إجابة خاطئة\n\n"
        f"بالتوفيق! 🍀")
    await _send_question(context, query.message.chat_id, user_id)


async def _send_question(context: ContextTypes.DEFAULT_TYPE, chat_id, user_id):
    """إرسال السؤال الحالي وجدولة مؤقت انتهاء الوقت."""
    quiz = context.application.user_data[user_id].get("quiz")
    if not quiz:
        return
    idx = quiz["index"]
    q = quiz["questions"][idx]
    total = len(quiz["questions"])
    quiz["q_started_at"] = time.time()

    msg = await context.bot.send_message(
        chat_id,
        f"❓ السؤال {idx + 1}/{total}  |  ⏳ {quiz['seconds']} ثانية\n"
        f"{'─' * 20}\n\n"
        f"{q['text']}\n\n"
        f"أ) {q['option_a']}\n"
        f"ب) {q['option_b']}\n"
        f"ج) {q['option_c']}\n"
        f"د) {q['option_d']}",
        reply_markup=question_options_keyboard(q["question_id"]))
    quiz["q_message_id"] = msg.message_id

    context.job_queue.run_once(
        _question_timeout, when=quiz["seconds"],
        data={"user_id": user_id, "chat_id": chat_id,
              "question_id": q["question_id"], "index": idx},
        name=_timeout_job_name(user_id, quiz["comp_id"], idx))


def _timeout_job_name(user_id, comp_id, index):
    return f"qtimeout_{user_id}_{comp_id}_{index}"


def _cancel_timeout(context, user_id, comp_id, index):
    for job in context.job_queue.get_jobs_by_name(_timeout_job_name(user_id, comp_id, index)):
        job.schedule_removal()


async def _question_timeout(context: ContextTypes.DEFAULT_TYPE):
    """انتهى وقت السؤال دون إجابة."""
    data = context.job.data
    user_id, chat_id = data["user_id"], data["chat_id"]
    quiz = context.application.user_data.get(user_id, {}).get("quiz")
    # تجاهل إن كان الطالب قد أجاب وانتقل
    if not quiz or quiz["index"] != data["index"]:
        return

    q = quiz["questions"][quiz["index"]]
    db.save_answer(q["question_id"], user_id, None, False)
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=quiz.get("q_message_id"), reply_markup=None)
    except Exception:
        pass
    await context.bot.send_message(
        chat_id,
        f"⏰ انتهى الوقت! الإجابة الصحيحة: {OPTION_LABELS[q['correct_option']]}")
    await _advance(context, chat_id, user_id)


async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال إجابة الطالب: ans_{question_id}_{option}"""
    query = update.callback_query
    user_id = query.from_user.id
    _, qid, option = query.data.split("_")
    qid = int(qid)

    quiz = context.user_data.get("quiz")
    if not quiz:
        await query.answer("لا توجد مسابقة جارية.", show_alert=True)
        return
    current_q = quiz["questions"][quiz["index"]]
    if current_q["question_id"] != qid:
        # ضغط على سؤال قديم — لا رجوع للخلف
        await query.answer("انتهى هذا السؤال بالفعل! ⛔", show_alert=True)
        return

    _cancel_timeout(context, user_id, quiz["comp_id"], quiz["index"])
    is_correct = option == current_q["correct_option"]
    if is_correct:
        quiz["score"] += 1
    db.save_answer(qid, user_id, option, is_correct)

    feedback = "✅ إجابة صحيحة!" if is_correct else \
        f"❌ إجابة خاطئة. الصحيحة: {OPTION_LABELS[current_q['correct_option']]}"
    await query.answer(feedback)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.reply_text(feedback)
    await _advance(context, query.message.chat_id, user_id)


async def _advance(context: ContextTypes.DEFAULT_TYPE, chat_id, user_id):
    """الانتقال للسؤال التالي أو إنهاء المسابقة."""
    quiz = context.application.user_data[user_id].get("quiz")
    if not quiz:
        return
    quiz["index"] += 1
    if quiz["index"] < len(quiz["questions"]):
        await _send_question(context, chat_id, user_id)
        return

    # ============================== انتهت المسابقة — النتيجة الفورية
    comp_id = quiz["comp_id"]
    score, total = quiz["score"], len(quiz["questions"])
    time_taken = int(time.time() - quiz["started_at"])
    db.save_result(comp_id, user_id, score, total, time_taken)
    db.add_leaderboard_points(user_id, quiz["subject_id"], score)
    del context.application.user_data[user_id]["quiz"]

    pct = round(score / total * 100)
    grade = "🌟 ممتاز!" if pct >= 90 else "👏 جيد جداً!" if pct >= 75 else \
            "🙂 جيد" if pct >= 50 else "📖 تحتاج مزيداً من المراجعة"

    top = db.get_competition_results(comp_id, limit=TOP_N)
    lines = [
        "🏁 انتهت مشاركتك!",
        "",
        f"📊 نتيجتك: {score}/{total} ({pct}%)",
        f"⏱ الوقت: {time_taken // 60} د {time_taken % 60} ث",
        grade,
        "",
        f"🏆 الترتيب الحالي (Top {TOP_N}):",
    ]
    for i, r in enumerate(top, start=1):
        marker = " ⬅️ أنت" if r["user_id"] == user_id else ""
        lines.append(f"{medal(i)} {r['full_name']} — {r['score']}/{r['total']} "
                     f"({r['time_taken']} ث){marker}")
    await context.bot.send_message(chat_id, "\n".join(lines),
                                   reply_markup=student_menu())


# ===================================================== مقررات الطالب ==

async def my_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_all_subjects()
    if not subjects:
        await query.edit_message_text("لا توجد مقررات معرفة بعد.",
                                      reply_markup=back_to_menu_keyboard())
        return
    enrolled = {s["subject_id"] for s in db.get_student_subjects(query.from_user.id)}
    await query.edit_message_text(
        "📚 مقرراتك — اضغط على مقرر للتسجيل/إلغاء التسجيل:\n(✅ = مسجل)",
        reply_markup=subjects_keyboard(subjects, "stusub",
                                       done_button="stusub_done",
                                       selected_ids=enrolled))


async def toggle_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data == "stusub_done":
        await query.answer("تم الحفظ ✅")
        from handlers.common import show_main_menu
        await show_main_menu(update, context)
        return
    await query.answer()
    sid = int(query.data.split("_")[1])
    enrolled = {s["subject_id"] for s in db.get_student_subjects(user_id)}
    if sid in enrolled:
        db.unenroll_student(user_id, sid)
        enrolled.discard(sid)
    else:
        db.enroll_student(user_id, sid)
        enrolled.add(sid)
    await query.edit_message_reply_markup(
        reply_markup=subjects_keyboard(db.get_all_subjects(), "stusub",
                                       done_button="stusub_done",
                                       selected_ids=enrolled))


# ========================================================= نتائج الطالب ==

async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    results = db.get_student_results(query.from_user.id)
    if not results:
        await query.edit_message_text("لم تشارك في أي مسابقة بعد. 🎯",
                                      reply_markup=back_to_menu_keyboard())
        return
    lines = ["📈 نتائجك:\n"]
    for r in results[:20]:
        pct = round(r["score"] / r["total"] * 100) if r["total"] else 0
        lines.append(f"• {r['title']} ({r['subject_name'] or 'عامة'})\n"
                     f"  {r['score']}/{r['total']} — {pct}%")
    await query.edit_message_text("\n".join(lines), reply_markup=back_to_menu_keyboard())


# ============================================================== Handlers ==

def get_callback_handlers():
    return [
        CallbackQueryHandler(list_competitions, pattern=r"^stu_comps$"),
        CallbackQueryHandler(join_competition, pattern=r"^join_\d+$"),
        CallbackQueryHandler(answer_question, pattern=r"^ans_\d+_[abcd]$"),
        CallbackQueryHandler(my_subjects, pattern=r"^stu_subjects$"),
        CallbackQueryHandler(toggle_subject, pattern=r"^stusub_"),
        CallbackQueryHandler(my_results, pattern=r"^stu_results$"),
    ]
