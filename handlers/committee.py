# -*- coding: utf-8 -*-
"""
معالج لجنة المسابقات:
- مراجعة أسئلة المدرسين قبل النشر (اعتماد / رفض)
- تعيين/تغيير المقررات المخصصة لكل مدرس
- إنشاء مسابقات عامة (لجميع الطلاب) بدون مراجعة
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from database import db
from handlers.professor import (Q_A, Q_B, Q_C, Q_CORRECT, Q_D, Q_TEXT,
                                cancel_comp, q_a, q_b, q_c, q_correct, q_d,
                                q_text)
from utils.helpers import (CONFIG, COMP_TYPE_LABELS, OPTION_LABELS,
                           parse_datetime)
from utils.keyboards import (back_to_menu_keyboard, review_keyboard,
                             subjects_keyboard)
from utils.scheduler import schedule_competition

logger = logging.getLogger(__name__)

MIN_Q = CONFIG.get("min_questions", 5)
MAX_Q = CONFIG.get("max_questions", 50)

# حالات إنشاء المسابقة العامة (تكمل بعدها بحالات الأسئلة من professor)
G_TITLE, G_NUM, G_SECONDS, G_START, G_END = range(100, 105)

# حالات تعيين المقررات
A_PROF, A_SUBJECTS = range(2)


# ========================================================== مراجعة المسابقات

async def review_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending = db.get_competitions_pending_review()
    if not pending:
        await query.edit_message_text("✅ لا توجد مسابقات بانتظار المراجعة.",
                                      reply_markup=back_to_menu_keyboard())
        return
    await query.edit_message_text(f"🔍 مسابقات بانتظار المراجعة: {len(pending)}")
    for c in pending:
        text = (f"🏷 {c['title']}\n"
                f"👨‍🏫 المدرس: {c['creator_name']}\n"
                f"📚 المقرر: {c['subject_name'] or 'عامة'}\n"
                f"📌 النوع: {COMP_TYPE_LABELS.get(c['comp_type'])}\n"
                f"❓ الأسئلة: {db.count_questions(c['competition_id'])}/{c['num_questions']}\n"
                f"🕐 {c['start_time']} ← {c['end_time']}")
        await query.message.reply_text(text, reply_markup=review_keyboard(c["competition_id"]))


async def view_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comp_id = int(query.data.split("_")[1])
    questions = db.get_competition_questions(comp_id)
    if not questions:
        await query.message.reply_text("لا توجد أسئلة.")
        return
    chunks, current = [], []
    for i, q in enumerate(questions, start=1):
        current.append(
            f"❓ س{i}: {q['text']}\n"
            f"  أ) {q['option_a']}\n  ب) {q['option_b']}\n"
            f"  ج) {q['option_c']}\n  د) {q['option_d']}\n"
            f"  ✅ الصحيحة: {OPTION_LABELS[q['correct_option']]}")
        if len("\n\n".join(current)) > 3000:
            chunks.append("\n\n".join(current[:-1]))
            current = current[-1:]
    chunks.append("\n\n".join(current))
    for ch in chunks:
        await query.message.reply_text(ch)


async def approve_competition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comp_id = int(query.data.split("_")[1])
    comp = db.get_competition(comp_id)
    if not comp or comp["status"] != "pending_review":
        await query.edit_message_text("⚠️ هذه المسابقة لم تعد بانتظار المراجعة.")
        return
    db.set_questions_status(comp_id, "approved")
    db.set_competition_status(comp_id, "approved")
    schedule_competition(context.job_queue, db.get_competition(comp_id))
    await query.edit_message_text(
        f"✅ اعتُمدت مسابقة: {comp['title']}\n"
        f"ستُفعَّل تلقائياً في: {comp['start_time']}")
    try:
        await context.bot.send_message(
            comp["creator_id"],
            f"🎉 اعتمدت لجنة المسابقات مسابقتك: {comp['title']}\n"
            f"ستبدأ تلقائياً في: {comp['start_time']}")
    except Exception:
        pass


async def reject_competition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comp_id = int(query.data.split("_")[1])
    comp = db.get_competition(comp_id)
    if not comp:
        return
    db.set_competition_status(comp_id, "rejected")
    await query.edit_message_text(f"❌ رُفضت مسابقة: {comp['title']}")
    try:
        await context.bot.send_message(
            comp["creator_id"],
            f"⚠️ رفضت لجنة المسابقات مسابقتك: {comp['title']}\n"
            "يمكنك إنشاء مسابقة جديدة بعد التعديل.")
    except Exception:
        pass


# ======================================================= تعيين مقررات المدرس

async def assign_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profs = db.get_all_professors()
    if not profs:
        await query.edit_message_text("⚠️ لا يوجد مدرسون مسجلون بعد. "
                                      "يضيفهم المشرف العام أولاً.",
                                      reply_markup=back_to_menu_keyboard())
        return ConversationHandler.END
    rows = [[InlineKeyboardButton(p["full_name"],
                                  callback_data=f"aprof_{p['professor_id']}")]
            for p in profs]
    await query.edit_message_text(
        "🔗 اختر المدرس لتعيين/تغيير مقرراته:",
        reply_markup=InlineKeyboardMarkup(rows))
    return A_PROF


async def assign_choose_prof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    professor_id = int(query.data.split("_")[1])
    context.user_data["assign_prof_id"] = professor_id

    subjects = db.get_all_subjects()
    if not subjects:
        await query.edit_message_text("⚠️ لا توجد مقررات. يضيفها المشرف العام أولاً.",
                                      reply_markup=back_to_menu_keyboard())
        return ConversationHandler.END

    # المقررات المعينة حالياً
    with db.get_conn() as conn:
        current = {r["subject_id"] for r in conn.execute(
            "SELECT subject_id FROM Professor_Subjects WHERE professor_id=?",
            (professor_id,)).fetchall()}
    context.user_data["assign_selected"] = current

    await query.edit_message_text(
        "📚 اضغط على المقررات لتفعيلها/إلغائها ثم اضغط ✔️:",
        reply_markup=subjects_keyboard(subjects, "asub",
                                       done_button="asub_done",
                                       selected_ids=current))
    return A_SUBJECTS


async def assign_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    professor_id = context.user_data["assign_prof_id"]
    selected = context.user_data["assign_selected"]

    if query.data == "asub_done":
        # مزامنة الاختيارات مع قاعدة البيانات
        all_ids = {s["subject_id"] for s in db.get_all_subjects()}
        for sid in all_ids:
            if sid in selected:
                db.assign_subject_to_professor(professor_id, sid)
            else:
                db.unassign_subject_from_professor(professor_id, sid)
        names = [db.get_subject(sid)["name"] for sid in selected]
        await query.edit_message_text(
            "✅ حُدثت مقررات المدرس:\n" +
            ("، ".join(names) if names else "لا مقررات"),
            reply_markup=back_to_menu_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    sid = int(query.data.split("_")[1])
    selected.symmetric_difference_update({sid})
    await query.edit_message_reply_markup(
        reply_markup=subjects_keyboard(db.get_all_subjects(), "asub",
                                       done_button="asub_done",
                                       selected_ids=selected))
    return A_SUBJECTS


# ========================================================= مسابقة عامة ==

async def general_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["comp"] = {"subject_id": None, "comp_type": "general"}
    context.user_data["auto_approve"] = True
    await query.edit_message_text(
        "🌐 مسابقة عامة (لجميع الطلاب)\n\n"
        "🏷 الخطوة 1/5 — أرسل اسم المسابقة:")
    return G_TITLE


async def general_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comp"]["title"] = update.message.text.strip()
    await update.message.reply_text(f"❓ الخطوة 2/5 — عدد الأسئلة ({MIN_Q}-{MAX_Q}):")
    return G_NUM


async def general_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
        assert MIN_Q <= n <= MAX_Q
    except (ValueError, AssertionError):
        await update.message.reply_text(f"⚠️ أرسل رقماً بين {MIN_Q} و {MAX_Q}:")
        return G_NUM
    context.user_data["comp"]["num_questions"] = n
    await update.message.reply_text("⏱ الخطوة 3/5 — مدة كل سؤال بالثواني:")
    return G_SECONDS


async def general_seconds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sec = int(update.message.text.strip())
        assert 10 <= sec <= 600
    except (ValueError, AssertionError):
        await update.message.reply_text("⚠️ أرسل رقماً بين 10 و 600:")
        return G_SECONDS
    context.user_data["comp"]["question_seconds"] = sec
    await update.message.reply_text(
        "🕐 الخطوة 4/5 — وقت البدء (YYYY-MM-DD HH:MM):")
    return G_START


async def general_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = parse_datetime(update.message.text)
    if not dt:
        await update.message.reply_text("⚠️ صيغة غير صحيحة. مثال: 2026-07-20 18:00")
        return G_START
    context.user_data["comp"]["start_time"] = dt.strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text("🕐 الخطوة 5/5 — وقت الانتهاء بنفس الصيغة:")
    return G_END


async def general_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = parse_datetime(update.message.text)
    comp = context.user_data["comp"]
    if not dt or dt.strftime("%Y-%m-%d %H:%M") <= comp["start_time"]:
        await update.message.reply_text("⚠️ وقت الانتهاء يجب أن يكون بعد وقت البدء:")
        return G_END
    comp["end_time"] = dt.strftime("%Y-%m-%d %H:%M")

    comp_id = db.create_competition(
        title=comp["title"], subject_id=None,
        creator_id=update.effective_user.id, comp_type="general",
        num_questions=comp["num_questions"], question_seconds=comp["question_seconds"],
        start_time=comp["start_time"], end_time=comp["end_time"], status="draft")
    context.user_data["comp_id"] = comp_id
    context.user_data["q_index"] = 1
    await update.message.reply_text(
        f"✅ أُنشئت المسابقة العامة: {comp['title']}\n\n"
        "📝 أرسل نص السؤال رقم 1:")
    return Q_TEXT


# ============================================================== Handlers ==

def get_general_comp_handler():
    text_only = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(general_start, pattern=r"^com_new_general$")],
        states={
            G_TITLE: [MessageHandler(text_only, general_title)],
            G_NUM: [MessageHandler(text_only, general_num)],
            G_SECONDS: [MessageHandler(text_only, general_seconds)],
            G_START: [MessageHandler(text_only, general_start_time)],
            G_END: [MessageHandler(text_only, general_end_time)],
            Q_TEXT: [MessageHandler(text_only, q_text)],
            Q_A: [MessageHandler(text_only, q_a)],
            Q_B: [MessageHandler(text_only, q_b)],
            Q_C: [MessageHandler(text_only, q_c)],
            Q_D: [MessageHandler(text_only, q_d)],
            Q_CORRECT: [CallbackQueryHandler(q_correct, pattern=r"^correct_[abcd]$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_comp)],
        allow_reentry=True,
    )


def get_assign_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(assign_start, pattern=r"^com_assign$")],
        states={
            A_PROF: [CallbackQueryHandler(assign_choose_prof, pattern=r"^aprof_\d+$")],
            A_SUBJECTS: [CallbackQueryHandler(assign_toggle, pattern=r"^asub_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_comp)],
        allow_reentry=True,
    )


def get_callback_handlers():
    return [
        CallbackQueryHandler(review_list, pattern=r"^com_review$"),
        CallbackQueryHandler(view_questions, pattern=r"^viewq_\d+$"),
        CallbackQueryHandler(approve_competition, pattern=r"^approve_\d+$"),
        CallbackQueryHandler(reject_competition, pattern=r"^reject_\d+$"),
    ]
