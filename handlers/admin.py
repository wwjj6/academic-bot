# -*- coding: utf-8 -*-
"""
معالج المشرف العام:
- إدارة المدرسين (إضافة/إزالة/عرض)
- إدارة أعضاء لجنة المسابقات
- إدارة المقررات
- التقارير الشاملة
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from database import db
from utils.helpers import ADMIN_IDS
from utils.keyboards import back_to_menu_keyboard

logger = logging.getLogger(__name__)

# حالات المحادثات
ADD_PROF_ID, ADD_PROF_NAME = range(2)
ADD_COM_ID, ADD_COM_NAME = range(2, 4)
ADD_SUBJECT = 4


def _admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # مشرف بالمعرف الرقمي أو بدور admin في قاعدة البيانات (المعرفون باسم المستخدم)
        if db.get_role(update.effective_user.id, ADMIN_IDS) != "admin":
            if update.callback_query:
                await update.callback_query.answer("⛔ صلاحية المشرف العام فقط.", show_alert=True)
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


# ========================================================== إدارة المدرسين

@_admin_only
async def professors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👨‍🏫 إدارة المدرسين:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة مدرس", callback_data="admin_add_prof")],
            [InlineKeyboardButton("📋 عرض المدرسين", callback_data="admin_list_profs")],
            [InlineKeyboardButton("🗑 إزالة مدرس", callback_data="admin_del_prof")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
        ]))


@_admin_only
async def add_prof_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ إضافة مدرس\n\n"
        "أرسل معرف تيليجرام (Telegram ID) الخاص بالمدرس:\n"
        "(يحصل عليه المدرس من بوت مثل @userinfobot)")
    return ADD_PROF_ID


async def add_prof_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["new_prof_id"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ أرسل رقم المعرف فقط:")
        return ADD_PROF_ID
    await update.message.reply_text("✍️ أرسل اسم المدرس الكامل:")
    return ADD_PROF_NAME


async def add_prof_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prof_id = context.user_data.pop("new_prof_id")
    name = update.message.text.strip()
    db.upsert_user(prof_id, name, role="professor")
    db.add_professor(prof_id)
    await update.message.reply_text(
        f"✅ أُضيف المدرس: {name} (ID: {prof_id})\n"
        "تعين اللجنة مقرراته من قائمة (تعيين مقررات المدرسين).",
        reply_markup=back_to_menu_keyboard())
    try:
        await context.bot.send_message(
            prof_id, f"🎉 تم تعيينك مدرساً في بوت المسابقات الأكاديمية.\nأرسل /start للبدء.")
    except Exception:
        pass
    return ConversationHandler.END


@_admin_only
async def list_profs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profs = db.get_all_professors()
    if not profs:
        text = "لا يوجد مدرسون بعد."
    else:
        lines = ["👨‍🏫 المدرسون المسجلون:\n"]
        for p in profs:
            subjects = db.get_professor_subjects(p["user_id"])
            subj_names = "، ".join(s["name"] for s in subjects) or "بلا مقررات"
            lines.append(f"• {p['full_name']} (ID: {p['user_id']})\n  📚 {subj_names}")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())


@_admin_only
async def del_prof_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    profs = db.get_all_professors()
    if not profs:
        await query.edit_message_text("لا يوجد مدرسون.", reply_markup=back_to_menu_keyboard())
        return
    rows = [[InlineKeyboardButton(f"🗑 {p['full_name']}",
                                  callback_data=f"delprof_{p['user_id']}")]
            for p in profs]
    rows.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    await query.edit_message_text("اختر المدرس لإزالته:",
                                  reply_markup=InlineKeyboardMarkup(rows))


@_admin_only
async def del_prof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    user = db.get_user(user_id)
    db.remove_professor(user_id)
    await query.edit_message_text(
        f"✅ أُزيل المدرس: {user['full_name'] if user else user_id}",
        reply_markup=back_to_menu_keyboard())


# ===================================================== إدارة لجنة المسابقات

@_admin_only
async def committee_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    members = db.get_users_by_role("committee")
    lines = ["🧑‍⚖️ أعضاء لجنة المسابقات:\n"]
    lines += [f"• {m['full_name']} (ID: {m['user_id']})" for m in members] or ["لا يوجد أعضاء."]
    rows = [[InlineKeyboardButton("➕ إضافة عضو لجنة", callback_data="admin_add_com")]]
    rows += [[InlineKeyboardButton(f"🗑 إزالة {m['full_name']}",
                                   callback_data=f"delcom_{m['user_id']}")]
             for m in members]
    rows.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


@_admin_only
async def add_com_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ أرسل معرف تيليجرام لعضو اللجنة الجديد:")
    return ADD_COM_ID


async def add_com_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["new_com_id"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ أرسل رقم المعرف فقط:")
        return ADD_COM_ID
    await update.message.reply_text("✍️ أرسل اسم العضو الكامل:")
    return ADD_COM_NAME


async def add_com_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    com_id = context.user_data.pop("new_com_id")
    name = update.message.text.strip()
    db.upsert_user(com_id, name, role="committee")
    await update.message.reply_text(
        f"✅ أُضيف عضو اللجنة: {name} (ID: {com_id})",
        reply_markup=back_to_menu_keyboard())
    try:
        await context.bot.send_message(
            com_id, "🎉 تم تعيينك عضواً في لجنة المسابقات.\nأرسل /start للبدء.")
    except Exception:
        pass
    return ConversationHandler.END


@_admin_only
async def del_com(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    db.set_role(user_id, "student")
    await query.edit_message_text("✅ أُزيل العضو من اللجنة.",
                                  reply_markup=back_to_menu_keyboard())


# ========================================================== إدارة المقررات

@_admin_only
async def subjects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subjects = db.get_all_subjects()
    lines = ["📚 المقررات الحالية:\n"]
    lines += [f"• {s['name']}" + (f" ({s['code']})" if s["code"] else "")
              for s in subjects] or ["لا توجد مقررات."]
    lines.append("\n➕ لإضافة مقرر أرسل اسمه الآن، أو بالصيغة:\nالاسم | الرمز | المستوى")
    await query.edit_message_text("\n".join(lines))
    return ADD_SUBJECT


async def add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [p.strip() for p in update.message.text.split("|")]
    name = parts[0]
    code = parts[1] if len(parts) > 1 else None
    level = parts[2] if len(parts) > 2 else None
    db.add_subject(name, code, level)
    await update.message.reply_text(
        f"✅ أُضيف المقرر: {name}\n"
        "أرسل مقرراً آخر أو /cancel للإنهاء.")
    return ADD_SUBJECT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text("تم الإنهاء.",
                                              reply_markup=back_to_menu_keyboard())
    return ConversationHandler.END


# ================================================================ التقارير

@_admin_only
async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s = db.get_stats()
    await query.edit_message_text(
        "📊 التقرير الشامل:\n\n"
        f"🎓 الطلاب: {s['students']}\n"
        f"👨‍🏫 المدرسون: {s['professors']}\n"
        f"🧑‍⚖️ أعضاء اللجنة: {s['committee']}\n"
        f"📚 المقررات: {s['subjects']}\n"
        f"🏆 إجمالي المسابقات: {s['competitions']}\n"
        f"🟢 المسابقات النشطة: {s['active_competitions']}\n"
        f"📝 المشاركات المكتملة: {s['results']}",
        reply_markup=back_to_menu_keyboard())


# ============================================================== Handlers ==

def get_conversation_handlers():
    text_only = filters.TEXT & ~filters.COMMAND
    return [
        ConversationHandler(
            entry_points=[CallbackQueryHandler(add_prof_start, pattern=r"^admin_add_prof$")],
            states={
                ADD_PROF_ID: [MessageHandler(text_only, add_prof_id)],
                ADD_PROF_NAME: [MessageHandler(text_only, add_prof_name)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True),
        ConversationHandler(
            entry_points=[CallbackQueryHandler(add_com_start, pattern=r"^admin_add_com$")],
            states={
                ADD_COM_ID: [MessageHandler(text_only, add_com_id)],
                ADD_COM_NAME: [MessageHandler(text_only, add_com_name)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True),
        ConversationHandler(
            entry_points=[CallbackQueryHandler(subjects_menu, pattern=r"^admin_subjects$")],
            states={ADD_SUBJECT: [MessageHandler(text_only, add_subject)]},
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True),
    ]


def get_callback_handlers():
    return [
        CallbackQueryHandler(professors_menu, pattern=r"^admin_professors$"),
        CallbackQueryHandler(list_profs, pattern=r"^admin_list_profs$"),
        CallbackQueryHandler(del_prof_menu, pattern=r"^admin_del_prof$"),
        CallbackQueryHandler(del_prof, pattern=r"^delprof_\d+$"),
        CallbackQueryHandler(committee_menu, pattern=r"^admin_committee$"),
        CallbackQueryHandler(del_com, pattern=r"^delcom_\d+$"),
        CallbackQueryHandler(reports, pattern=r"^admin_reports$"),
    ]
