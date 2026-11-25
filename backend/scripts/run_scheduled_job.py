#!/usr/bin/env python3
"""
Runs exactly one scheduled job in its own disposable OS process, then exits.

Why this exists: a scheduled job (winback reminders, membership expiry,
auto Day-Off) used to run directly inside the main web server's event loop.
On 2026-11-10 a segfault inside the Oracle driver during one of these jobs
crashed the *entire* app process — taking the live website down with it for
~13 seconds, and killing the job before it could finish (which is why that
day's auto Day-Off never got recorded). Running each job in its own
subprocess means a crash here only kills this disposable process; the main
web server keeps serving requests untouched either way.

Usage:
    python3 -m backend.scripts.run_scheduled_job <job_name>

<job_name> is one of: winback_30, winback, membership_expiry, auto_day_off,
bridal_auto_complete
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

JOBS = {
    "winback_30": "run_winback_30_job",
    "winback": "run_winback_job",
    "membership_expiry": "run_membership_expiry_job",
    "auto_day_off": "run_auto_day_off_job",
    "bridal_auto_complete": "run_bridal_auto_complete_job",
}


async def main(job_name: str) -> int:
    from backend.core.database import init_pool, close_pool
    from backend.services import scheduler as job_module

    func = getattr(job_module, JOBS[job_name])
    await init_pool()
    try:
        await func()
        return 0
    finally:
        await close_pool()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        print(f"Usage: python3 -m backend.scripts.run_scheduled_job <{'|'.join(JOBS)}>")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
