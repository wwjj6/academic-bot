# -*- coding: utf-8 -*-
"""
معالج المدرس:
- إنشاء مسابقات وأسئلة لأي مقرر من مقرراته المعتمدة
- مشاهدة نتائج طلاب كل مقرر على حدة
- إرسال إشعارات مستهدفة لطلاب مقرر محدد
"""
import logging

from telegram import Update
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from database import db
from utils.helpers import (ADMIN_IDS, CONFIG, COMP_TYPE_LABELS, OPTION_LABELS,
                           STATUS_LABELS, parse_datetime)
from utils.keyboards import (back_to_menu_keyboard, comp_type_keyboard,
                             correct_option_keyboard, professor_menu,
                             subjects_keyboard)
from utils.scheduler import notify_subject_students

logger = logging.getLogger(__name__)

MIN_Q = CONFIG.get("min_questions", 5)
MAX_Q = CONFIG.get("max_questions", 50)

# حالات محادثة إنشاء المسابقة
(C_SUBJECT, C_TITLE, C_TYPE, C_NUM, C_QSECONDS, C_START, C_END,
 Q_TEXT, Q_A, Q_B, Q_C, Q_D, Q_CORRECT) = range(13)

# حالات محادثة الإشعارات
N_SUBJECT, N_TEXT = range(2)


def _is_professor(user_id):
    return db.get_role(user_id, ADMIN_IDS) in ("professor", "admin") \
        and db.get_professor_by_user(user_id) is not None or user_id in ADMIN_IDS


# ============================================================ إنشاء مسابقة ==

async def new_comp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_professor_subjects(query.from_user.id)
    if not subjects:
        await query.edit_message_text(
            "⚠️ لا توجد مقررات معينة لك بعد.\n"
            "تواصل مع لجنة المسابقات لتعيين مقرراتك.",
            reply_markup=back_to_menu_keyboard())
        return ConversationHandler.END
    context.user_data["comp"] = {}
    await query.edit_message_text(
        "📚 الخطوة 1/7 — اختر المقرر من مقرراتك المعتمدة:",
        reply_markup=subjects_keyboard(subjects, "csub"))
    return C_SUBJECT


async def comp_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    context.user_data["comp"]["subject_id"] = sid
    subject = db.get_subject(sid)
    await query.edit_message_text(
        f"📚 المقرر: {subject['name']}\n\n"
        "🏷 الخطوة 2/7 — أرسل اسم المسابقة:")
    return C_TITLE


async def comp_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comp"]["title"] = update.message.text.strip()
    await update.message.reply_text(
        "📌 الخطوة 3/7 — اختر نوع المسابقة:",
        reply_markup=comp_type_keyboard())
    return C_TYPE


async def comp_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctype = query.data.split("_", 1)[1]
    context.user_data["comp"]["comp_type"] = ctype
    await query.edit_message_text(
        f"📌 النوع: {COMP_TYPE_LABELS[ctype]}\n\n"
        f"❓ الخطوة 4/7 — أرسل عدد الأسئلة ({MIN_Q}-{MAX_Q}):")
    return C_NUM


async def comp_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
        assert MIN_Q <= n <= MAX_Q
    except (ValueError, AssertionError):
        await update.message.reply_text(f"⚠️ أرسل رقماً بين {MIN_Q} و {MAX_Q}:")
        return C_NUM
    context.user_data["comp"]["num_questions"] = n
    await update.message.reply_text(
        "⏱ الخطوة 5/7 — أرسل مدة كل سؤال بالثواني (مثال: 60):")
    return C_QSECONDS


async def comp_qseconds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sec = int(update.message.text.strip())
        assert 10 <= sec <= 600
    except (ValueError, AssertionError):
        await update.message.reply_text("⚠️ أرسل رقماً بين 10 و 600 ثانية:")
        return C_QSECONDS
    context.user_data["comp"]["question_seconds"] = sec
    await update.message.reply_text(
        "🕐 الخطوة 6/7 — أرسل وقت بدء المسابقة بالصيغة:\n"
        "YYYY-MM-DD HH:MM\n"
        "مثال: 2026-07-20 18:00")
    return C_START


async def comp_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = parse_datetime(update.message.text)
    if not dt:
        await update.message.reply_text("⚠️ صيغة غير صحيحة. مثال: 2026-07-20 18:00")
        return C_START
    context.user_data["comp"]["start_time"] = dt.strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text(
        "🕐 الخطوة 7/7 — أرسل وقت انتهاء المسابقة بنفس الصيغة:")
    return C_END


async def comp_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt = parse_datetime(update.message.text)
    comp = context.user_data["comp"]
    if not dt or dt.strftime("%Y-%m-%d %H:%M") <= comp["start_time"]:
        await update.message.reply_text("⚠️ وقت الانتهاء يجب أن يكون بعد وقت البدء. أعد الإرسال:")
        return C_END
    comp["end_time"] = dt.strftime("%Y-%m-%d %H:%M")

    comp_id = db.create_competition(
        title=comp["title"], subject_id=comp["subject_id"],
        creator_id=update.effective_user.id, comp_type=comp["comp_type"],
        num_questions=comp["num_questions"], question_seconds=comp["question_seconds"],
        start_time=comp["start_time"], end_time=comp["end_time"], status="draft")
    context.user_data["comp_id"] = comp_id
    context.user_data["q_index"] = 1

    subject = db.get_subject(comp["subject_id"])
    await update.message.reply_text(
        f"✅ تم إنشاء المسابقة (مسودة):\n"
        f"🏷 {comp['title']}\n📚 {subject['name']}\n"
        f"❓ {comp['num_questions']} سؤال × {comp['question_seconds']} ثانية\n"
        f"🕐 {comp['start_time']} ← {comp['end_time']}\n\n"
        f"الآن نضيف الأسئلة (اختيار من متعدد: أ، ب، ج، د)\n\n"
        f"📝 أرسل نص السؤال رقم 1:")
    return Q_TEXT


# ------------------------------------------------------------ إضافة الأسئلة

async def q_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = {"text": update.message.text.strip()}
    await update.message.reply_text("🅰 أرسل الخيار (أ):")
    return Q_A


async def q_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"]["a"] = update.message.text.strip()
    await update.message.reply_text("🅱 أرسل الخيار (ب):")
    return Q_B


async def q_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"]["b"] = update.message.text.strip()
    await update.message.reply_text("©️ أرسل الخيار (ج):")
    return Q_C


async def q_c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"]["c"] = update.message.text.strip()
    await update.message.reply_text("🅳 أرسل الخيار (د):")
    return Q_D


async def q_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"]["d"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ اختر الإجابة الصحيحة:", reply_markup=correct_option_keyboard())
    return Q_CORRECT


async def q_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    correct = query.data.split("_")[1]
    q = context.user_data["q"]
    comp_id = context.user_data["comp_id"]
    db.add_question(comp_id, q["text"], q["a"], q["b"], q["c"], q["d"], correct)

    idx = context.user_data["q_index"]
    total = context.user_data["comp"]["num_questions"]
    if idx < total:
        context.user_data["q_index"] = idx + 1
        await query.edit_message_text(
            f"✅ تم حفظ السؤال {idx}/{total} (الإجابة: {OPTION_LABELS[correct]})\n\n"
            f"📝 أرسل نص السؤال رقم {idx + 1}:")
        return Q_TEXT

    # اكتملت الأسئلة
    if context.user_data.get("auto_approve"):
        # مسار اللجنة: اعتماد وجدولة فورية بدون مراجعة
        db.set_questions_status(comp_id, "approved")
        db.set_competition_status(comp_id, "approved")
        from utils.scheduler import schedule_competition
        schedule_competition(context.job_queue, db.get_competition(comp_id))
        await query.edit_message_text(
            f"🎉 اكتملت جميع الأسئلة ({total}/{total})!\n\n"
            "✅ اعتُمدت المسابقة وجُدولت. سيُشعَر الطلاب تلقائياً عند وقت البدء.")
        context.user_data.clear()
        return ConversationHandler.END

    # مسار المدرس: إرسال للمراجعة
    db.set_competition_status(comp_id, "pending_review")
    await query.edit_message_text(
        f"🎉 اكتملت جميع الأسئلة ({total}/{total})!\n\n"
        "📨 أُرسلت المسابقة إلى لجنة المسابقات للمراجعة والاعتماد.\n"
        "سيصلك إشعار عند اعتمادها أو رفضها.")

    # إشعار أعضاء اللجنة
    comp = db.get_competition(comp_id)
    for member in db.get_users_by_role("committee"):
        try:
            await context.bot.send_message(
                member["user_id"],
                f"🔔 مسابقة جديدة بانتظار المراجعة:\n"
                f"🏷 {comp['title']}\n"
                f"👨‍🏫 المدرس: {db.get_user(comp['creator_id'])['full_name']}\n"
                f"استخدم قائمة (مراجعة مسابقات المدرسين).")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_comp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comp_id = context.user_data.get("comp_id")
    if comp_id:
        db.set_competition_status(comp_id, "draft")
    context.user_data.clear()
    await update.effective_message.reply_text(
        "تم إلغاء العملية.", reply_markup=professor_menu())
    return ConversationHandler.END


# ========================================================== عرض المسابقات ==

async def my_competitions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comps = db.get_competitions_by_creator(query.from_user.id)
    if not comps:
        await query.edit_message_text("لا توجد مسابقات بعد.",
                                      reply_markup=back_to_menu_keyboard())
        return
    lines = ["📋 مسابقاتك:\n"]
    for c in comps[:20]:
        lines.append(f"• {c['title']} — {c['subject_name'] or 'عامة'}\n"
                     f"  {STATUS_LABELS[c['status']]} | {c['start_time']} ← {c['end_time']}")
    await query.edit_message_text("\n".join(lines), reply_markup=back_to_menu_keyboard())


async def my_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_professor_subjects(query.from_user.id)
    if not subjects:
        text = "⚠️ لا توجد مقررات معينة لك. تواصل مع لجنة المسابقات."
    else:
        text = "📚 مقرراتك المعتمدة:\n\n" + "\n".join(
            f"• {s['name']}" + (f" ({s['code']})" if s["code"] else "")
            for s in subjects)
    await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())


# ====================================================== النتائج حسب المقرر ==

async def results_choose_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_professor_subjects(query.from_user.id)
    if not subjects:
        await query.edit_message_text("⚠️ لا توجد مقررات معينة لك.",
                                      reply_markup=back_to_menu_keyboard())
        return
    await query.edit_message_text(
        "📊 اختر المقرر لعرض نتائج طلابه:",
        reply_markup=subjects_keyboard(subjects, "profres"))


async def show_subject_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    subject = db.get_subject(sid)
    rows = db.get_results_by_subject(sid)
    if not rows:
        await query.edit_message_text(
            f"📊 {subject['name']}: لا توجد نتائج بعد.",
            reply_markup=back_to_menu_keyboard())
        return
    lines = [f"📊 نتائج مقرر: {subject['name']}\n"]
    current_comp = None
    for r in rows[:40]:
        if r["competition_title"] != current_comp:
            current_comp = r["competition_title"]
            lines.append(f"\n🏷 {current_comp}:")
        lines.append(f"  • {r['full_name']} ({r['university_id']}) — "
                     f"{r['score']}/{r['total']}")
    await query.edit_message_text("\n".join(lines), reply_markup=back_to_menu_keyboard())


# ==================================================== إشعار مستهدف لمقرر ==

async def notify_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_professor_subjects(query.from_user.id)
    if not subjects:
        await query.edit_message_text("⚠️ لا توجد مقررات معينة لك.",
                                      reply_markup=back_to_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text(
        "📢 اختر المقرر المراد إرسال إشعار لطلابه:",
        reply_markup=subjects_keyboard(subjects, "nsub"))
    return N_SUBJECT


async def notify_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    context.user_data["notify_subject_id"] = sid
    subject = db.get_subject(sid)
    await query.edit_message_text(
        f"📢 إشعار لطلاب مقرر: {subject['name']}\n\nأرسل نص الإشعار:")
    return N_TEXT


async def notify_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = context.user_data.pop("notify_subject_id")
    subject = db.get_subject(sid)
    prof = db.get_user(update.effective_user.id)
    text = (f"📢 إشعار من د. {prof['full_name']}\n"
            f"📚 مقرر: {subject['name']}\n\n{update.message.text}")
    sent = await notify_subject_students(context.bot, sid, text)
    await update.message.reply_text(
        f"✅ أُرسل الإشعار إلى {sent} طالباً في مقرر {subject['name']}.",
        reply_markup=professor_menu())
    return ConversationHandler.END


# ============================================================== Handlers ==

def get_competition_creation_handler():
    text_only = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(new_comp_start, pattern=r"^prof_new_comp$"),
                      CallbackQueryHandler(new_comp_start, pattern=r"^com_new_from_prof$")],
        states={
            C_SUBJECT: [CallbackQueryHandler(comp_subject, pattern=r"^csub_\d+$")],
            C_TITLE: [MessageHandler(text_only, comp_title)],
            C_TYPE: [CallbackQueryHandler(comp_type, pattern=r"^ctype_")],
            C_NUM: [MessageHandler(text_only, comp_num)],
            C_QSECONDS: [MessageHandler(text_only, comp_qseconds)],
            C_START: [MessageHandler(text_only, comp_start_time)],
            C_END: [MessageHandler(text_only, comp_end_time)],
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


def get_notify_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(notify_start, pattern=r"^prof_notify$")],
        states={
            N_SUBJECT: [CallbackQueryHandler(notify_subject, pattern=r"^nsub_\d+$")],
            N_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, notify_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_comp)],
        allow_reentry=True,
    )


def get_callback_handlers():
    return [
        CallbackQueryHandler(my_competitions, pattern=r"^prof_my_comps$"),
        CallbackQueryHandler(my_subjects, pattern=r"^prof_my_subjects$"),
        CallbackQueryHandler(results_choose_subject, pattern=r"^prof_results$"),
        CallbackQueryHandler(show_subject_results, pattern=r"^profres_\d+$"),
    ]
