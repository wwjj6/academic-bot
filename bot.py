# -*- coding: utf-8 -*-
"""
بوت المسابقات الأكاديمية — كلية الطب | جامعة حجة
================================================
نقطة التشغيل الرئيسية.

التشغيل:
    python bot.py
"""
import logging
import sys
import asyncio  # <--- تمت الإضافة

from telegram import BotCommand
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

from database import db
from handlers import admin, committee, common, professor, student
from utils.helpers import CONFIG
from utils.keyboards import BTN_HELP, BTN_LEADERBOARD, BTN_MAIN_MENU
from utils.scheduler import reschedule_all

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# تقليل ضجيج مكتبة httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """بعد الإقلاع: إعادة جدولة المسابقات + تفعيل زر القائمة ☰ بجانب حقل الكتابة."""
    reschedule_all(application.job_queue)
    logger.info("✅ أُعيدت جدولة المسابقات المعلقة.")
    await application.bot.set_my_commands([
        BotCommand("start", "بدء البوت / التسجيل"),
        BotCommand("menu", "القائمة الرئيسية"),
        BotCommand("help", "التعليمات"),
        BotCommand("cancel", "إلغاء العملية الحالية"),
    ])
    logger.info("✅ فُعّل زر القائمة (☰) بجانب حقل الكتابة.")


def main():
    token = CONFIG.get("bot_token", "")
    if not token or token.startswith("PUT_"):
        print("⚠️  ضع توكن البوت في config.json أولاً (bot_token).")
        print("    احصل على التوكن من @BotFather في تيليجرام.")
        sys.exit(1)

    # إنشاء قاعدة البيانات
    db.init_db()
    logger.info("✅ قاعدة البيانات جاهزة.")

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # ---------- المحادثات ----------
    application.add_handler(common.get_registration_handler())
    application.add_handler(professor.get_competition_creation_handler())
    application.add_handler(professor.get_notify_handler())
    application.add_handler(committee.get_general_comp_handler())
    application.add_handler(committee.get_assign_handler())
    for h in admin.get_conversation_handlers():
        application.add_handler(h)

    # ---------- الأزرار المفردة ----------
    for h in professor.get_callback_handlers():
        application.add_handler(h)
    for h in committee.get_callback_handlers():
        application.add_handler(h)
    for h in admin.get_callback_handlers():
        application.add_handler(h)
    for h in student.get_callback_handlers():
        application.add_handler(h)

    # ---------- المشتركة ----------
    application.add_handler(CallbackQueryHandler(common.show_main_menu,
                                                 pattern=r"^main_menu$"))
    application.add_handler(CallbackQueryHandler(common.show_general_leaderboard,
                                                 pattern=r"^show_leaderboard_general$"))
    application.add_handler(CommandHandler("menu", common.show_main_menu))
    application.add_handler(CommandHandler("help", common.help_command))
    application.add_handler(CommandHandler("cancel", common.cancel))

    # أزرار لوحة التحكم الدائمة
    application.add_handler(MessageHandler(filters.Text([BTN_MAIN_MENU]),
                                           common.show_main_menu))
    application.add_handler(MessageHandler(filters.Text([BTN_HELP]),
                                           common.help_command))
    application.add_handler(MessageHandler(filters.Text([BTN_LEADERBOARD]),
                                           common.show_general_leaderboard))

    logger.info("🚀 بوت المسابقات الأكاديمية يعمل الآن...")

    # ===== الحل النهائي لتشغيل البوت على Render (داخل def main) =====
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(application.run_polling(drop_pending_updates=True))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()