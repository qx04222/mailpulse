"""
统一入口：Telegram Bot + 从 DB 加载定时任务 + 手动触发轮询
所有推送计划从后台 digest_schedules 表读取，不硬编码。
python -m src.entrypoint
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .main import run_all, run_company, sync_all
from .config import settings, load_companies
from .storage.db import db
from .bot.server import create_bot_app
from .bot.lark_callback import create_callback_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def execute_schedule(schedule_id: str):
    """执行一个推送计划"""
    try:
        resp = db.table("digest_schedules") \
            .select("*, companies(*)") \
            .eq("id", schedule_id) \
            .single() \
            .execute()
        schedule = resp.data
        if not schedule:
            return

        company_id = schedule.get("company_id")
        report_type = schedule.get("report_type", "brief")
        is_sync = report_type == "sync_only"

        logger.info(f"Schedule triggered: {schedule['name']} ({'sync' if is_sync else 'full'})")

        from datetime import datetime, timezone
        db.table("digest_schedules").update({
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "last_run_status": "running",
        }).eq("id", schedule_id).execute()

        if is_sync:
            # 仅同步：拉邮件 + AI 打分 + 入库
            if company_id:
                companies = load_companies()
                company = next((c for c in companies if c["id"] == company_id), None)
                if company:
                    result = await run_company(company, sync_only=True)
                    logger.info(f"Sync done: {result['company']} ({result['emails']} emails)")
            else:
                await sync_all()
        else:
            # 完整流程：同步 + 分析 + 报告 + 推送
            if company_id:
                companies = load_companies()
                company = next((c for c in companies if c["id"] == company_id), None)
                if company:
                    result = await run_company(company)
                    logger.info(f"Schedule done: {result['company']} ({result['emails']} emails)")
            else:
                await run_all()

        db.table("digest_schedules").update({
            "last_run_status": "completed",
        }).eq("id", schedule_id).execute()

    except Exception as e:
        logger.error(f"Schedule {schedule_id} failed: {e}")
        db.table("digest_schedules").update({
            "last_run_status": f"failed: {str(e)[:200]}",
        }).eq("id", schedule_id).execute()


def _parse_cron(cron_expr: str) -> dict:
    """解析 cron 表达式为 APScheduler CronTrigger 参数"""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron: {cron_expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def load_schedules_from_db():
    """从 digest_schedules 表加载所有活跃计划，注册到 scheduler"""
    resp = db.table("digest_schedules") \
        .select("id, name, cron_expression, timezone, is_active") \
        .eq("is_active", True) \
        .execute()

    schedules = resp.data or []
    registered = 0

    for s in schedules:
        job_id = f"schedule_{s['id']}"
        # 先移除旧的（如果有）
        existing = scheduler.get_job(job_id)
        if existing:
            scheduler.remove_job(job_id)

        try:
            cron_params = _parse_cron(s["cron_expression"])
            tz = s.get("timezone") or "America/Toronto"

            scheduler.add_job(
                execute_schedule,
                CronTrigger(timezone=tz, **cron_params),
                args=[s["id"]],
                id=job_id,
                name=s["name"],
            )
            registered += 1
            logger.info(f"  Registered: {s['name']} ({s['cron_expression']} {tz})")
        except Exception as e:
            logger.error(f"  Failed to register {s['name']}: {e}")

    logger.info(f"Loaded {registered}/{len(schedules)} schedules from DB")
    return registered


async def reload_schedules():
    """每 5 分钟重新加载推送计划（后台修改后自动生效）"""
    try:
        load_schedules_from_db()
    except Exception as e:
        logger.error(f"Reload schedules error: {e}")


async def poll_manual_triggers():
    """每 15 秒检查 manual_triggers 表"""
    try:
        resp = db.table("manual_triggers") \
            .select("*") \
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
        db.table("manual_triggers").update({"status": "running"}).eq("id", trigger_id).execute()

        try:
            if company_id:
                companies = load_companies()
                company = next((c for c in companies if c["id"] == company_id), None)
                if company:
                    result = await run_company(company)
                    logger.info(f"Manual run done: {result['company']} ({result['emails']} emails)")
                else:
                    raise ValueError(f"Company {company_id} not found")
            else:
                await run_all()

            from datetime import datetime, timezone
            db.table("manual_triggers").update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trigger_id).execute()

        except Exception as e:
            logger.error(f"Manual trigger failed: {e}")
            db.table("manual_triggers").update({
                "status": "failed",
                "error": str(e)[:500],
            }).eq("id", trigger_id).execute()

    except Exception as e:
        logger.error(f"Trigger poll error: {e}")


async def main():
    # 从 DB 加载推送计划
    logger.info("Loading schedules from database...")
    load_schedules_from_db()

    # 手动触发轮询：每 15 秒
    scheduler.add_job(
        poll_manual_triggers,
        "interval",
        seconds=15,
        id="manual_trigger_poll",
        name="Manual Trigger Poll",
    )

    # 定期重新加载推送计划：每 5 分钟
    scheduler.add_job(
        reload_schedules,
        "interval",
        minutes=5,
        id="reload_schedules",
        name="Reload Schedules from DB",
    )

    scheduler.start()
    logger.info("Scheduler started (DB-driven + manual trigger polling)")

    if settings.telegram_enabled and settings.telegram_bot_token:
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
    else:
        logger.info("Telegram disabled or no bot token — running scheduler only")

    # Start Lark callback server (for card button clicks)
    if settings.lark_enabled and settings.lark_app_id:
        from aiohttp import web
        callback_app = create_callback_app()
        callback_port = int(getattr(settings, "lark_callback_port", 8080))
        runner = web.AppRunner(callback_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", callback_port)
        await site.start()
        logger.info(f"Lark callback server running on port {callback_port}")

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
