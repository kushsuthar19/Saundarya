"""
Scheduled WhatsApp reminders — runs once daily inside the FastAPI process
via APScheduler (in-process; no OS-level cron needed). Registered from
main.py's lifespan on startup, shut down on app shutdown.

Three jobs:
  - run_winback_30_job()          ('winback_30') — any client whose
    last_visit was exactly 30 days ago (first, gentler reminder).
  - run_winback_job()             ('winback') — any client whose last_visit
    was exactly 60 days ago (follow-up if they still haven't come back).
  - run_membership_expiry_job()   ('membership') — Exclusive memberships
    expiring in exactly 7, 3, or 0 days.

All are best-effort per client: one client's send failing (bad phone,
AiSensy hiccup) never stops the rest of the batch, and every send already
goes through send_whatsapp_template()'s own non-blocking error handling.
Each also checks wa_log first so a server restart or manual re-trigger on
the same day can't double-send the same client.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.core.config import settings
from backend.core.database import get_connection
from backend.services.whatsapp_service import send_whatsapp_template

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


async def _already_sent_today(cursor, client_id, template_key: str) -> bool:
    if not client_id:
        return False
    await cursor.execute(
        """SELECT COUNT(*) FROM wa_log
           WHERE client_id=:1 AND template_key=:2 AND TRUNC(sent_at)=TRUNC(SYSDATE)""",
        [client_id, template_key]
    )
    row = await cursor.fetchone()
    return bool(row and row[0] > 0)


async def run_winback_job():
    """Any client (New/Regular/Exclusive) whose last recorded visit was
    exactly 60 days ago today."""
    try:
        async with get_connection() as db:
            cursor = db.cursor()
            await cursor.execute(
                """SELECT id, name, phone FROM clients
                   WHERE phone IS NOT NULL
                     AND last_visit IS NOT NULL
                     AND TRUNC(SYSDATE) - TRUNC(last_visit) = 60"""
            )
            rows = await cursor.fetchall()
            sent = 0
            for client_id, name, phone in rows:
                if await _already_sent_today(cursor, client_id, "winback"):
                    continue
                result = await send_whatsapp_template(
                    db, phone, "winback", [name],
                    client_id=client_id, ref_id=client_id, user_name=name,
                )
                if result.get("success"):
                    sent += 1
                else:
                    logger.warning(f"Winback send failed for client {client_id}: {result.get('error')}")
            logger.info(f"Winback job: {sent} sent, {len(rows)} candidate(s) checked.")
    except Exception as e:
        logger.error(f"Winback job failed: {e}")


async def run_winback_30_job():
    """Same as run_winback_job() but a first, gentler reminder at exactly
    30 days since last visit — the existing 60-day one above still fires
    as the follow-up if they still haven't come back by then."""
    try:
        async with get_connection() as db:
            cursor = db.cursor()
            await cursor.execute(
                """SELECT id, name, phone FROM clients
                   WHERE phone IS NOT NULL
                     AND last_visit IS NOT NULL
                     AND TRUNC(SYSDATE) - TRUNC(last_visit) = 30"""
            )
            rows = await cursor.fetchall()
            # The approved template has an Image header, so a media URL is
            # required on every send — without one the send fails outright.
            image_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/static/winback-30day.png" if settings.PUBLIC_BASE_URL else None
            sent = 0
            for client_id, name, phone in rows:
                if await _already_sent_today(cursor, client_id, "winback_30"):
                    continue
                result = await send_whatsapp_template(
                    db, phone, "winback_30", [name],
                    media_url=image_url, media_filename="winback-30day.png",
                    client_id=client_id, ref_id=client_id, user_name=name,
                )
                if result.get("success"):
                    sent += 1
                else:
                    logger.warning(f"30-day winback send failed for client {client_id}: {result.get('error')}")
            logger.info(f"30-day winback job: {sent} sent, {len(rows)} candidate(s) checked.")
    except Exception as e:
        logger.error(f"30-day winback job failed: {e}")


async def run_membership_expiry_job():
    """Active memberships whose expiry_date is exactly 7, 3, or 0 days
    from today — one of three phrasings goes into the {{2}} param."""
    phrases = {7: "expires in 7 days", 3: "expires in 3 days", 0: "expires today"}
    try:
        async with get_connection() as db:
            cursor = db.cursor()
            await cursor.execute(
                """SELECT c.id, c.name, c.phone,
                          TRUNC(m.expiry_date) - TRUNC(SYSDATE) as days_left
                   FROM memberships m
                   JOIN clients c ON c.id = m.client_id
                   WHERE m.status = 'Active'
                     AND c.phone IS NOT NULL
                     AND m.expiry_date IS NOT NULL
                     AND TRUNC(m.expiry_date) - TRUNC(SYSDATE) IN (7, 3, 0)"""
            )
            rows = await cursor.fetchall()
            sent = 0
            for client_id, name, phone, days_left in rows:
                phrase = phrases.get(int(days_left))
                if not phrase or await _already_sent_today(cursor, client_id, "membership"):
                    continue
                result = await send_whatsapp_template(
                    db, phone, "membership", [name, phrase],
                    client_id=client_id, ref_id=client_id, user_name=name,
                )
                if result.get("success"):
                    sent += 1
                else:
                    logger.warning(f"Membership expiry send failed for client {client_id}: {result.get('error')}")
            logger.info(f"Membership expiry job: {sent} sent, {len(rows)} candidate(s) checked.")
    except Exception as e:
        logger.error(f"Membership expiry job failed: {e}")


def start_scheduler():
    """Call once from main.py's lifespan on startup."""
    if _scheduler.running:
        return
    # 08:55 / 09:00 / 09:05 local server time — staggered a few minutes
    # apart so the jobs don't compete for DB connections at the exact same
    # tick.
    _scheduler.add_job(run_winback_30_job, CronTrigger(hour=8, minute=55), id="wa_winback_30", replace_existing=True)
    _scheduler.add_job(run_winback_job, CronTrigger(hour=9, minute=0), id="wa_winback", replace_existing=True)
    _scheduler.add_job(run_membership_expiry_job, CronTrigger(hour=9, minute=5), id="wa_membership_expiry", replace_existing=True)
    _scheduler.start()
    logger.info("WhatsApp reminder scheduler started (winback 08:55/09:00, membership expiry 09:05 daily).")


def stop_scheduler():
    """Call once from main.py's lifespan on shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
