"""
统一入口：同时运行 Telegram Bot + 定时任务
python -m src.entrypoint
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .main import run_all
from .bot.server import run_bot, create_bot_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def scheduled_digest():
    """定时触发的摘要任务"""
    logger.info("Scheduled digest triggered")
    try:
        await run_all()
    except Exception as e:
        logger.error(f"Scheduled digest failed: {e}")


async def main():
    # 设置定时任务：周一、周四 08:00 Toronto 时间
    scheduler = AsyncIOScheduler(timezone="America/Toronto")
    scheduler.add_job(
        scheduled_digest,
        CronTrigger(day_of_week="mon,thu", hour=8, minute=0),
        id="email_digest",
        name="Email Digest Cron",
    )
    scheduler.start()
    logger.info("Scheduler started: Mon/Thu 08:00 Toronto time")

    # 运行 Bot
    app = create_bot_app()
    logger.info("Bot starting in polling mode...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running. Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
