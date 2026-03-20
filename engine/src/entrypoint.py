"""
统一入口：Telegram Bot + 定时 Digest + 手动触发轮询
python -m src.entrypoint
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .main import run_all, run_company
from .config import load_companies
from .storage.db import db
from .bot.server import create_bot_app

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


async def poll_manual_triggers():
    """每 15 秒检查 manual_triggers 表，处理手动触发请求"""
    try:
        resp = db.table("manual_triggers") \
            .select("*, digest_schedules(*)") \
            .eq("status", "pending") \
            .order("created_at") \
            .limit(1) \
            .execute()

        if not resp.data:
            return

        trigger = resp.data[0]
        trigger_id = trigger["id"]
        company_id = trigger.get("company_id")

        logger.info(f"Manual trigger found: {trigger_id}")

        # 标记为 running
        db.table("manual_triggers").update({"status": "running"}).eq("id", trigger_id).execute()

        try:
            if company_id:
                # 跑单个公司
                companies = load_companies()
                company = next((c for c in companies if c["id"] == company_id), None)
                if company:
                    result = await run_company(company)
                    logger.info(f"Manual run done: {result['company']} ({result['emails']} emails)")
                else:
                    raise ValueError(f"Company {company_id} not found")
            else:
                # 跑所有公司
                await run_all()

            db.table("manual_triggers").update({
                "status": "completed",
                "completed_at": "now()",
            }).eq("id", trigger_id).execute()

        except Exception as e:
            logger.error(f"Manual trigger failed: {e}")
            db.table("manual_triggers").update({
                "status": "failed",
                "error": str(e)[:500],
            }).eq("id", trigger_id).execute()

    except Exception as e:
        logger.error(f"Trigger poll error: {e}")


async def schedule_from_db():
    """从 digest_schedules 表加载定时任务（未来扩展用）"""
    # TODO: 从 DB 读取 digest_schedules 动态注册 cron jobs
    pass


async def main():
    # 定时任务：默认 Mon/Thu 08:00
    scheduler = AsyncIOScheduler(timezone="America/Toronto")
    scheduler.add_job(
        scheduled_digest,
        CronTrigger(day_of_week="mon,thu", hour=8, minute=0),
        id="email_digest",
        name="Email Digest Cron",
    )

    # 手动触发轮询：每 15 秒检查一次
    scheduler.add_job(
        poll_manual_triggers,
        "interval",
        seconds=15,
        id="manual_trigger_poll",
        name="Manual Trigger Poll",
    )

    scheduler.start()
    logger.info("Scheduler started: Cron + Manual trigger polling (15s)")

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
