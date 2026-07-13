# -*- coding: utf-8 -*-
"""المعالجات المشتركة: /start، تسجيل الطلاب، القوائم الرئيسية، الترتيب العام."""
import logging

from telegram import Update
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from database import db
from utils.helpers import (ADMIN_IDS, CONFIG, format_leaderboard,
                           is_admin_user, is_valid_university_id)
from utils.keyboards import (admin_menu, committee_menu, persistent_keyboard,
                             professor_menu, student_menu, subjects_keyboard)

logger = logging.getLogger(__name__)

# حالات محادثة تسجيل الطالب
REG_UNI_ID, REG_NAME, REG_SUBJECTS = range(3)

BOT_NAME = CONFIG.get("bot_name", "المسابقات الأكاديمية")

WELCOME_TEXT = (
    "🏆 مرحبًا بك في بوت المسابقات الأكاديمية\n\n"
    "يسر اللجنة العلمية أن ترحب بك في المنصة المخصصة لتنظيم المسابقات "
    "العلمية بين طلاب الدفعة.\n\n"
    "من خلال هذا البوت يمكنك:\n"
    "• المشاركة في المسابقات الأكاديمية.\n"
    "• اختبار معلوماتك في مختلف المواد.\n"
    "• متابعة نتائجك وترتيبك.\n"
    "• المنافسة بروح علمية مع زملائك.\n"
    "• تنمية مستواك العلمي من خلال تحديات متنوعة.\n\n"
    "🌟 نسعى لأن يكون هذا البوت مساحة تجمع بين التعلم، والمتعة، "
    "والتنافس الشريف.\n\n"
    "نتمنى لك تجربة ممتعة، ومنافسة مليئة بالنجاح والتميز.\n\n"
    "العلم يرتقي بالمنافسة، والتميز يبدأ بخطوة. 🤍"
)

# تعليمات الاستخدام حسب دور المستخدم — تظهر عند /start وعند /help
ROLE_INSTRUCTIONS = {
    "student": (
        "📖 تعليمات الاستخدام — الطالب:\n\n"
        "1️⃣ التسجيل: أرسل رقمك الجامعي ثم اسمك الكامل، واختر المقررات المسجل بها.\n\n"
        "2️⃣ المسابقات: عند بدء مسابقة لأحد مقرراتك يصلك إشعار تلقائي، "
        "أو تصفحها من زر (🎯 المسابقات المتاحة).\n\n"
        "3️⃣ آلية الإجابة:\n"
        "   • لكل سؤال عداد تنازلي ⏳ — انتهاء الوقت بدون إجابة = إجابة خاطئة\n"
        "   • سؤال واحد في كل مرة، ولا يمكن الرجوع للسؤال السابق ⛔\n"
        "   • اضغط على أحد الأزرار (أ، ب، ج، د) للإجابة\n\n"
        "4️⃣ النتائج: تظهر نتيجتك فور انتهائك مع ترتيب أفضل 10 مشاركين 🏆\n"
        "   وتتراكم نقاطك في الترتيب العام مع كل مسابقة.\n\n"
        "⚙️ الأوامر: /menu القائمة الرئيسية | /help التعليمات | /cancel إلغاء العملية الحالية"
    ),
    "professor": (
        "📖 تعليمات الاستخدام — المدرس:\n\n"
        "1️⃣ مقرراتك: تعينها لجنة المسابقات، وتظهر في زر (📚 مقرراتي).\n\n"
        "2️⃣ إنشاء مسابقة (➕):\n"
        "   اختر المقرر ← اسم المسابقة ← النوع (أسبوعية/شهرية/تحدي) ← "
        "عدد الأسئلة (5-50) ← مدة كل سؤال ← وقت البدء والانتهاء ← أدخل الأسئلة "
        "(نص السؤال ثم الخيارات أ، ب، ج، د ثم الإجابة الصحيحة).\n\n"
        "3️⃣ المراجعة: تُرسل مسابقتك تلقائياً للجنة، وعند اعتمادها تُجدول "
        "وتنطلق في موعدها ويُشعَر طلاب المقرر تلقائياً.\n\n"
        "4️⃣ النتائج: من زر (📊 نتائج الطلاب) — مفصولة حسب كل مقرر على حدة.\n\n"
        "5️⃣ الإشعارات: من زر (📢) ترسل رسالة تصل فقط لطلاب المقرر الذي تحدده.\n\n"
        "⚙️ الأوامر: /menu القائمة الرئيسية | /cancel إلغاء العملية الحالية"
    ),
    "committee": (
        "📖 تعليمات الاستخدام — لجنة المسابقات:\n\n"
        "1️⃣ تعيين المقررات (🔗): اختر المدرس ثم فعّل/ألغِ مقرراته — "
        "المدرس ينشئ مسابقات لمقرراته المعتمدة فقط.\n\n"
        "2️⃣ المراجعة (🔍): تصلك مسابقات المدرسين قبل النشر — "
        "اعرض الأسئلة ثم اعتمد ✅ أو ارفض ❌. عند الاعتماد تُجدول تلقائياً.\n\n"
        "3️⃣ المسابقات العامة (🌐): تنشئها اللجنة لجميع الطلاب وتُنشر "
        "مباشرة بدون مراجعة.\n\n"
        "4️⃣ الترتيب العام (🏆): نقاط تراكمية من جميع المسابقات.\n\n"
        "⚙️ الأوامر: /menu القائمة الرئيسية | /cancel إلغاء العملية الحالية"
    ),
    "admin": (
        "📖 تعليمات الاستخدام — المشرف العام:\n\n"
        "1️⃣ ابدأ بإضافة المقررات من (📚 إدارة المقررات) — "
        "أرسل اسم المقرر أو بالصيغة: الاسم | الرمز | المستوى.\n\n"
        "2️⃣ أضف المدرسين من (👨‍🏫 إدارة المدرسين) بمعرف تيليجرام الخاص بكل مدرس "
        "(يحصل عليه من @userinfobot).\n\n"
        "3️⃣ أضف أعضاء لجنة المسابقات من (🧑‍⚖️ إدارة لجنة المسابقات) — "
        "اللجنة تعين مقررات المدرسين وتراجع مسابقاتهم.\n\n"
        "4️⃣ تابع الإحصائيات الكاملة من (📊 التقارير الشاملة).\n\n"
        "⚙️ الأوامر: /menu القائمة الرئيسية | /cancel إلغاء العملية الحالية"
    ),
}

# سطر الدعم الفني — يُلحق بجميع التعليمات
SUPPORT_LINE = "\n\n📮 إذا واجهت مشكلة تواصل بنا عبر بوت التواصل الخاص بالدفعة."
ROLE_INSTRUCTIONS = {role: text + SUPPORT_LINE
                     for role, text in ROLE_INSTRUCTIONS.items()}

ROLE_MENUS = {
    "admin": ("👑 لوحة المشرف العام", admin_menu),
    "professor": ("👨‍🏫 لوحة المدرس", professor_menu),
    "committee": ("🧑‍⚖️ لوحة لجنة المسابقات", committee_menu),
    "student": ("🎓 لوحة الطالب", student_menu),
}


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القائمة المناسبة لدور المستخدم."""
    user_id = update.effective_user.id
    role = db.get_role(user_id, ADMIN_IDS)
    title, menu = ROLE_MENUS.get(role, ROLE_MENUS["student"])
    text = f"🏥 {BOT_NAME}\n\n{title}\nاختر من القائمة:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=menu())
    else:
        await update.effective_message.reply_text(text, reply_markup=menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — تسجيل تلقائي للمشرفين، وبدء محادثة التسجيل للطلاب الجدد."""
    user = update.effective_user
    existing = db.get_user(user.id)

    # رسالة الترحيب الرسمية تظهر دائماً عند /start
    # مع تفعيل لوحة الأزرار الدائمة (أيقونة بجانب حقل الكتابة)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=persistent_keyboard())

    if is_admin_user(user):
        db.upsert_user(user.id, user.full_name, user.username, role="admin")
        await update.message.reply_text(ROLE_INSTRUCTIONS["admin"])
        await show_main_menu(update, context)
        return ConversationHandler.END

    if existing and (existing["role"] != "student" or existing["university_id"]):
        # تعليمات مطابقة لدور المستخدم المسجل
        await update.message.reply_text(
            ROLE_INSTRUCTIONS.get(existing["role"], ROLE_INSTRUCTIONS["student"]))
        await show_main_menu(update, context)
        return ConversationHandler.END

    # طالب جديد → التعليمات ثم التسجيل
    await update.message.reply_text(ROLE_INSTRUCTIONS["student"])
    await update.message.reply_text(
        "📝 للتسجيل كطالب، أرسل رقمك الجامعي (أرقام فقط):")
    return REG_UNI_ID


async def reg_university_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not is_valid_university_id(text):
        await update.message.reply_text("⚠️ رقم جامعي غير صالح. أرسل أرقاماً فقط (4-15 خانة):")
        return REG_UNI_ID
    context.user_data["reg_university_id"] = text
    await update.message.reply_text("✍️ ممتاز! الآن أرسل اسمك الكامل (رباعي):")
    return REG_NAME


async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 6:
        await update.message.reply_text("⚠️ الاسم قصير جداً. أرسل اسمك الكامل:")
        return REG_NAME
    context.user_data["reg_name"] = name
    context.user_data["reg_subject_ids"] = set()

    subjects = db.get_all_subjects()
    if not subjects:
        # لا توجد مقررات بعد — إكمال التسجيل بدون مقررات
        _finish_registration(update.effective_user, context)
        await update.message.reply_text(
            "✅ تم تسجيلك بنجاح!\nلا توجد مقررات معرفة حالياً، يمكنك اختيارها لاحقاً من قائمة (مقرراتي).")
        await show_main_menu(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "📚 اختر المقررات المسجل بها (اضغط على كل مقرر، ثم اضغط ✔️ تم الاختيار):",
        reply_markup=subjects_keyboard(subjects, "regsub", done_button="regsub_done"))
    return REG_SUBJECTS


async def reg_toggle_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = context.user_data.setdefault("reg_subject_ids", set())

    if query.data == "regsub_done":
        if not selected:
            await query.answer("اختر مقرراً واحداً على الأقل!", show_alert=True)
            return REG_SUBJECTS
        _finish_registration(update.effective_user, context)
        names = [db.get_subject(sid)["name"] for sid in selected]
        await query.edit_message_text(
            "✅ تم تسجيلك بنجاح!\n\n"
            f"👤 الاسم: {context.user_data['reg_name']}\n"
            f"🎫 الرقم الجامعي: {context.user_data['reg_university_id']}\n"
            f"📚 المقررات: {'، '.join(names)}")
        await query.message.reply_text("اختر من القائمة:", reply_markup=student_menu())
        context.user_data.clear()
        return ConversationHandler.END

    sid = int(query.data.split("_")[1])
    if sid in selected:
        selected.discard(sid)
    else:
        selected.add(sid)
    await query.edit_message_reply_markup(
        reply_markup=subjects_keyboard(db.get_all_subjects(), "regsub",
                                       done_button="regsub_done", selected_ids=selected))
    return REG_SUBJECTS


def _finish_registration(user, context):
    db.upsert_user(user.id, context.user_data["reg_name"], user.username, role="student")
    db.set_student_info(user.id, context.user_data["reg_university_id"])
    for sid in context.user_data.get("reg_subject_ids", set()):
        db.enroll_student(user.id, sid)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text("تم الإلغاء. أرسل /start للبدء من جديد.")
    return ConversationHandler.END


async def show_general_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترتيب العام — يعمل من الزر المدمج ومن لوحة الأزرار الدائمة."""
    rows = db.get_leaderboard(subject_id=None, limit=CONFIG.get("top_n_leaderboard", 10))
    text = format_leaderboard(rows, "🏆 الترتيب العام — أفضل 10")
    from utils.keyboards import back_to_menu_keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=back_to_menu_keyboard())
    else:
        await update.effective_message.reply_text(
            text, reply_markup=back_to_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = db.get_role(update.effective_user.id, ADMIN_IDS) or "student"
    await update.message.reply_text(
        f"🏥 {BOT_NAME}\n\n"
        + ROLE_INSTRUCTIONS.get(role, ROLE_INSTRUCTIONS["student"]))


def get_registration_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_UNI_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_university_id)],
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_SUBJECTS: [CallbackQueryHandler(reg_toggle_subject, pattern=r"^regsub_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
