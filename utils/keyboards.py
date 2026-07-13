# -*- coding: utf-8 -*-
"""لوحات المفاتيح (Inline Keyboards) لجميع الأدوار."""
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup)

from utils.helpers import OPTION_LABELS, COMP_TYPE_LABELS

# أزرار لوحة التحكم الدائمة (تظهر عبر أيقونة الأزرار بجانب حقل الكتابة)
BTN_MAIN_MENU = "🏠 القائمة الرئيسية"
BTN_HELP = "📖 التعليمات"
BTN_LEADERBOARD = "🏆 الترتيب العام"


def persistent_keyboard():
    """لوحة أزرار دائمة أسفل الشاشة — يفتحها المستخدم من الأيقونة بجانب حقل الكتابة."""
    return ReplyKeyboardMarkup(
        [[BTN_MAIN_MENU], [BTN_HELP, BTN_LEADERBOARD]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="اختر من الأزرار أو اكتب هنا...")


# ------------------------------------------------------------ القوائم الرئيسية

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍🏫 إدارة المدرسين", callback_data="admin_professors")],
        [InlineKeyboardButton("🧑‍⚖️ إدارة لجنة المسابقات", callback_data="admin_committee")],
        [InlineKeyboardButton("📚 إدارة المقررات", callback_data="admin_subjects")],
        [InlineKeyboardButton("📊 التقارير الشاملة", callback_data="admin_reports")],
        [InlineKeyboardButton("🏆 الترتيب العام", callback_data="show_leaderboard_general")],
    ])


def professor_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إنشاء مسابقة جديدة", callback_data="prof_new_comp")],
        [InlineKeyboardButton("📋 مسابقاتي", callback_data="prof_my_comps")],
        [InlineKeyboardButton("📚 مقرراتي", callback_data="prof_my_subjects")],
        [InlineKeyboardButton("📊 نتائج الطلاب (حسب المقرر)", callback_data="prof_results")],
        [InlineKeyboardButton("📢 إرسال إشعار لطلاب مقرر", callback_data="prof_notify")],
    ])


def committee_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 مراجعة مسابقات المدرسين", callback_data="com_review")],
        [InlineKeyboardButton("🌐 إنشاء مسابقة عامة", callback_data="com_new_general")],
        [InlineKeyboardButton("🔗 تعيين مقررات المدرسين", callback_data="com_assign")],
        [InlineKeyboardButton("🏆 الترتيب العام", callback_data="show_leaderboard_general")],
    ])


def student_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 المسابقات المتاحة", callback_data="stu_comps")],
        [InlineKeyboardButton("📚 مقرراتي المسجلة", callback_data="stu_subjects")],
        [InlineKeyboardButton("📈 نتائجي", callback_data="stu_results")],
        [InlineKeyboardButton("🏆 الترتيب العام", callback_data="show_leaderboard_general")],
    ])


# ------------------------------------------------------------------ عامّة

def subjects_keyboard(subjects, prefix, done_button=None, selected_ids=()):
    """قائمة مقررات؛ prefix يحدد سياق الاختيار."""
    rows = []
    for s in subjects:
        mark = "✅ " if s["subject_id"] in selected_ids else ""
        rows.append([InlineKeyboardButton(f"{mark}{s['name']}",
                                          callback_data=f"{prefix}_{s['subject_id']}")])
    if done_button:
        rows.append([InlineKeyboardButton("✔️ تم الاختيار", callback_data=done_button)])
    return InlineKeyboardMarkup(rows)


def comp_type_keyboard(prefix="ctype"):
    rows = [[InlineKeyboardButton(label, callback_data=f"{prefix}_{key}")]
            for key, label in COMP_TYPE_LABELS.items() if key != "general"]
    return InlineKeyboardMarkup(rows)


def question_options_keyboard(question_id):
    """أزرار الإجابة: أ / ب / ج / د."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(OPTION_LABELS[o], callback_data=f"ans_{question_id}_{o}")
        for o in ("a", "b", "c", "d")
    ]])


def correct_option_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(OPTION_LABELS[o], callback_data=f"correct_{o}")
        for o in ("a", "b", "c", "d")
    ]])


def review_keyboard(competition_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اعتماد ونشر", callback_data=f"approve_{competition_id}"),
         InlineKeyboardButton("❌ رفض", callback_data=f"reject_{competition_id}")],
        [InlineKeyboardButton("👁 عرض الأسئلة", callback_data=f"viewq_{competition_id}")],
    ])


def join_competition_keyboard(competition_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ابدأ المسابقة الآن", callback_data=f"join_{competition_id}")]
    ])


def back_to_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ])
