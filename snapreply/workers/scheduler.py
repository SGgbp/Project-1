"""
APScheduler setup — all background jobs registered here.
In-process scheduler, no Redis or Celery needed.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/London")


def start_scheduler() -> None:
    from workers.daily_digest import send_all_daily_digests
    from workers.monday_report import send_all_monday_reports
    from workers.noshow_reminder import send_noshow_reminders
    from workers.trial_expiry import run_trial_expiry_checks
    from workers.health_check import check_platform_health
    from services.review_service import process_review_queue

    # Daily digest — 7pm UK time, every day
    scheduler.add_job(
        send_all_daily_digests,
        CronTrigger(hour=19, minute=0, timezone="Europe/London"),
        id="daily_digest",
        name="Daily Digest",
        misfire_grace_time=300,
        coalesce=True,
    )

    # Monday ROI report — 8am every Monday
    scheduler.add_job(
        send_all_monday_reports,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="Europe/London"),
        id="monday_report",
        name="Monday ROI Report",
        misfire_grace_time=300,
        coalesce=True,
    )

    # No-show reminders — every 60 minutes
    scheduler.add_job(
        send_noshow_reminders,
        IntervalTrigger(minutes=60),
        id="noshow_reminder",
        name="No-Show Reminders",
        misfire_grace_time=300,
        coalesce=True,
    )

    # Trial expiry checks — 9am daily
    scheduler.add_job(
        run_trial_expiry_checks,
        CronTrigger(hour=9, minute=0, timezone="Europe/London"),
        id="trial_expiry",
        name="Trial Expiry Checks",
        misfire_grace_time=300,
        coalesce=True,
    )

    # Review request queue — every 15 minutes
    scheduler.add_job(
        process_review_queue,
        IntervalTrigger(minutes=15),
        id="review_requests",
        name="Review Request Queue",
        misfire_grace_time=300,
        coalesce=True,
    )

    # Health check — every 5 minutes
    scheduler.add_job(
        check_platform_health,
        IntervalTrigger(minutes=5),
        id="health_check",
        name="Platform Health Check",
        misfire_grace_time=60,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Scheduler started with 6 jobs registered.")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
