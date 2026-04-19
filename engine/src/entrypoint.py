"""
统一入口：Telegram Bot + 从 DB 加载定时任务 + 手动触发轮询
所有推送计划从后台 digest_schedules 表读取，不硬编码。
python -m src.entrypoint
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .main import run_all, run_company, sync_all
from .config import settings, load_companies
from .storage.db import db
from .bot.server import create_bot_app
from .bot.lark_callback import create_callback_app
from .bot.daily_todo import send_all_daily_todos
from .bot.hourly_sync import hourly_sync
from .processors.calendar_sync import check_due_calendar_events as _check_due_calendar_events
from .utils.holidays import is_business_day
logger = logging.getLogger(__name__)

# Silence noisy loggers: APScheduler executor + httpx per-request logs
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

scheduler = AsyncIOScheduler(
    job_defaults={"misfire_grace_time": 300},  # 5 min grace for all jobs by default
)


async def execute_schedule(schedule_id: str):
    """执行一个推送计划（节假日/周日自动跳过）"""
    if not is_business_day():
        logger.info(f"Schedule {schedule_id} skipped — not a business day")
        return
    logger.info(f"=== execute_schedule called: {schedule_id} ===")
    try:
        resp = db.table("digest_schedules") \
            .select("*, companies(*)") \
            .eq("id", schedule_id) \
            .single() \
            .execute()
        schedule = resp.data
        if not schedule:
            logger.warning(f"Schedule {schedule_id} not found in DB")
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

    # Track which job_ids are still active
    active_job_ids = set()

    for s in schedules:
        job_id = f"schedule_{s['id']}"
        active_job_ids.add(job_id)

        existing = scheduler.get_job(job_id)
        if existing:
            # Only re-register if cron/tz changed — avoids resetting next_run_time
            try:
                cron_params = _parse_cron(s["cron_expression"])
                tz = s.get("timezone") or "America/Toronto"
                new_trigger = CronTrigger(timezone=tz, **cron_params)
                # Compare trigger string representation
                if str(existing.trigger) == str(new_trigger):
                    registered += 1
                    continue  # unchanged, skip
            except Exception:
                pass
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
                misfire_grace_time=600,  # Allow up to 10 min late execution
            )
            registered += 1
            logger.info(f"  Registered: {s['name']} ({s['cron_expression']} {tz})")
        except Exception as e:
            logger.error(f"  Failed to register {s['name']}: {e}")

    # Remove jobs for schedules that were deactivated/deleted
    for job in scheduler.get_jobs():
        if job.id.startswith("schedule_") and job.id not in active_job_ids:
            logger.info(f"  Removing stale schedule job: {job.name} ({job.id})")
            scheduler.remove_job(job.id)

    logger.info(f"Loaded {registered}/{len(schedules)} schedules from DB")
    return registered


async def reload_schedules():
    """每 5 分钟重新加载推送计划（后台修改后自动生效）"""
    try:
        load_schedules_from_db()
    except Exception as e:
        logger.error(f"Reload schedules error: {e}")


async def catchup_missed_jobs(grace_minutes: int = 30):
    """
    启动时补跑已错过的定时任务。

    APScheduler 的 misfire_grace_time 只对运行期间延迟的触发生效；
    对启动前已错过的 cron 触发，它会直接把 next_run_time 算成下一次，
    错过的那次不补发。此函数弥补这个行为。

    仅处理每日类任务（daily_todo / calendar_due_check / DB schedules），
    跳过 hourly_sync 避免在整点附近产生重复触发。
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/Toronto")
    now = datetime.now(et)
    window_start = now - timedelta(minutes=grace_minutes)

    catchup_ids = {"daily_todo", "calendar_due_check"}
    for job in scheduler.get_jobs():
        if not isinstance(job.trigger, CronTrigger):
            continue
        if job.id not in catchup_ids and not job.id.startswith("schedule_"):
            continue

        # 找到 window_start 之后、≤ now 的最近一次触发点 = 错过的触发
        fire = job.trigger.get_next_fire_time(None, window_start)
        if fire is None or fire > now:
            continue

        logger.info(f"[catchup] {job.name} missed at {fire.strftime('%Y-%m-%d %H:%M %Z')}, firing now")
        try:
            scheduler.add_job(
                job.func,
                args=job.args,
                kwargs=job.kwargs,
                id=f"catchup_{job.id}_{int(now.timestamp())}",
                name=f"Catchup: {job.name}",
                next_run_time=now,
            )
        except Exception as e:
            logger.error(f"[catchup] Failed to schedule {job.name}: {e}")


async def poll_manual_triggers():
    """每 60 秒检查 manual_triggers 表"""
    try:
        resp = db.table("manual_triggers") \
            .select("*") \
            .eq("status", "pending") \
            .order("created_at") \
            .limit(1) \
            .execute()

        if not resp.data:
            return  # silent: no pending triggers

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
    from datetime import datetime, timezone as tz
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/Toronto")
    logger.info(f"=== MailPulse Engine starting at {datetime.now(et).strftime('%Y-%m-%d %H:%M:%S %Z')} ===")

    # 从 DB 加载推送计划
    logger.info("Loading schedules from database...")
    load_schedules_from_db()

    # 手动触发轮询：每 60 秒
    scheduler.add_job(
        poll_manual_triggers,
        "interval",
        seconds=60,
        id="manual_trigger_poll",
        name="Manual Trigger Poll",
    )

    # 定期重新加载推送计划：每 10 分钟
    scheduler.add_job(
        reload_schedules,
        "interval",
        minutes=10,
        id="reload_schedules",
        name="Reload Schedules from DB",
    )

    # 心跳日志：每 5 分钟确认 engine 存活
    async def heartbeat():
        jobs = scheduler.get_jobs()
        logger.info(f"[heartbeat] alive, {len(jobs)} jobs registered")

    scheduler.add_job(
        heartbeat,
        "interval",
        minutes=5,
        id="heartbeat",
        name="Engine Heartbeat",
    )

    # 每日待办推送：9:30 AM
    scheduler.add_job(
        send_all_daily_todos,
        CronTrigger(hour=9, minute=30, day_of_week="mon-sat", timezone="America/Toronto"),
        id="daily_todo",
        name="Daily Todo Push",
        misfire_grace_time=600,
    )

    # 高频轻量 sync：周一到周六 10:00-17:00 每小时
    scheduler.add_job(
        hourly_sync,
        CronTrigger(hour="10-17", minute=0, day_of_week="mon-sat", timezone="America/Toronto"),
        id="hourly_sync",
        name="Hourly Lightweight Sync",
        misfire_grace_time=300,
    )

    # 日历到期提醒：每天 8:30 AM（节假日跳过）
    async def _calendar_check_guarded():
        if not is_business_day():
            logger.info("[Calendar] Skipped — not a business day")
            return
        await _check_due_calendar_events()

    scheduler.add_job(
        _calendar_check_guarded,
        CronTrigger(hour=8, minute=30, day_of_week="mon-sat", timezone="America/Toronto"),
        id="calendar_due_check",
        name="Calendar Due Date Reminder",
        misfire_grace_time=600,
    )


    scheduler.start()
    logger.info("Scheduler started (DB-driven + manual trigger polling + daily todo)")

    # 启动补发：对错过 ≤30 分钟的每日类任务立即补跑一次
    await catchup_missed_jobs(grace_minutes=30)

    # Start Lark callback server FIRST (for card button clicks)
    callback_runner = None
    if settings.lark_enabled and settings.lark_app_id:
        try:
            from aiohttp import web
            callback_app = create_callback_app()
            import os
            callback_port = int(os.environ.get("PORT", getattr(settings, "lark_callback_port", 8080)))
            callback_runner = web.AppRunner(callback_app)
            await callback_runner.setup()
            site = web.TCPSite(callback_runner, "0.0.0.0", callback_port)
            await site.start()
            logger.info(f"Lark callback server running on port {callback_port}")
        except Exception as e:
            logger.error(f"Lark callback server failed to start: {e}")

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
            if callback_runner:
                await callback_runner.cleanup()
    else:
        logger.info("Telegram disabled or no bot token — running scheduler only")
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down...")
        finally:
            scheduler.shutdown()
            if callback_runner:
                await callback_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
