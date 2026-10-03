import asyncio
import logging
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config.settings import settings
from database.db import db

# Import routers
from handlers.admin_events import admin_events_router
from handlers.auth import auth_router
from handlers.channel_select import channel_router
from handlers.settings_menu import settings_router
from handlers.smart_batch import batch_router
from handlers.start import start_router
from handlers.media_uploader import uploader_router, start_queue_workers, stop_queue_workers
from utils.web_server import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ChannelMediaBot")

async def setup_bot_commands(bot: Bot):
    """Register standard commands in Telegram Bot Menu."""
    commands = [
        BotCommand(command="start", description="🚀 Open Main Dashboard"),
        BotCommand(command="channels", description="📢 Select / Switch Target Channel"),
        BotCommand(command="batch", description="📦 Start Smart Batch Upload Session"),
        BotCommand(command="endbatch", description="🏁 Finish & Sort Batch for Upload"),
        BotCommand(command="cancelbatch", description="🗑️ Discard Current Batch Session"),
        BotCommand(command="batchstatus", description="📋 View Active Batch Files & Order"),
        BotCommand(command="settings", description="⚙️ Upload & Preview Preferences"),
        BotCommand(command="stats", description="📊 Bot & Upload Statistics"),
        BotCommand(command="help", description="📖 Help & Setup Guide"),
        BotCommand(command="logout", description="🔒 Log Out of Bot")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    logger.info("Starting Telegram Channel Media Uploader Bot...")
    
    # 1. Validate Token
    if not settings.BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in settings.BOT_TOKEN or ":" not in settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is missing or not configured in .env file!")
        print("\n" + "="*60)
        print("⚠️  CONFIG ERROR: Valid BOT_TOKEN not found!")
        print("Please edit the .env file in the project folder and set your BOT_TOKEN:")
        print("Example: BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        print("="*60 + "\n")
        return

    # 2. Initialize Database
    await db.init_db()

    # 3. Create Bot and Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Include Routers in logical order
    dp.include_router(admin_events_router)
    dp.include_router(auth_router)
    dp.include_router(channel_router)
    dp.include_router(settings_router)
    dp.include_router(batch_router)
    dp.include_router(start_router)
    dp.include_router(uploader_router)

    # 5. Set Bot Commands Menu
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Could not register bot commands menu: {e}")

    # 6. Start Background Queue Workers (Strict Sequential FIFO Engine)
    start_queue_workers(bot, num_workers=settings.WORKER_COUNT)

    # 7. Fetch Bot Info
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot successfully started as @{bot_info.username} (ID: {bot_info.id})")
    print(f"\n🚀 Bot is ONLINE! Logged in as: @{bot_info.username}")
    print(f"🔒 Master Password: {settings.MASTER_PASSWORD}")
    print(f"⚙️  Queue Workers: {settings.WORKER_COUNT} (Strict FIFO Order)")
    print("Press Ctrl+C to stop the bot.\n")

    # 8. Start Health-Check Web Server (for Cloud deployment: Render / Koyeb / Railway)
    web_runner = None
    if settings.ENABLE_WEB_SERVER:
        web_runner = await start_web_server(port=settings.PORT)

    # 9. Start Polling
    allowed_updates = ["message", "callback_query", "my_chat_member", "chat_member"]
    try:
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        stop_queue_workers()
        if web_runner:
            await web_runner.cleanup()
            logger.info("Health-check web server shut down gracefully.")
        await bot.session.close()
        logger.info("Bot polling stopped, workers halted, and session closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
