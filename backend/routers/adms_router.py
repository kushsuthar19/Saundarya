"""
ADMS (ZKTeco's push protocol, often called "iClock") receiver — lets the
K40 Pro fingerprint machine push punches straight to this server over the
internet, with no local bridge computer required. The device is already
configured (Menu -> Comm -> Cloud Server Setting) to call these exact
`/iclock/...` paths on its own, at whatever Server Address/Port it has
set — that path prefix is fixed by the device's firmware, not something
this app chooses, so these routes are mounted at the app root instead of
under the normal /api/v1 prefix.

This is a plain-text protocol, not JSON: the device expects very specific
response bodies ("OK", or a key=value options block), not a JSON API.

Three calls the device makes on its own, repeatedly, forever:
  - GET  /iclock/cdata?SN=...&options=all   — registration/config handshake
  - POST /iclock/cdata?SN=...&table=ATTLOG  — the actual punches, as lines
    of tab-separated text in the request body
  - GET  /iclock/getrequest?SN=...          — "any commands for me?" poll
  - POST /iclock/devicecmd?SN=...           — command-result acknowledgement
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from backend.core.database import get_connection

logger = logging.getLogger(__name__)

adms_router = APIRouter(prefix="/iclock", tags=["adms"])


def _ok() -> PlainTextResponse:
    return PlainTextResponse("OK")


@adms_router.get("/cdata")
async def adms_cdata_get(request: Request):
    sn = request.query_params.get("SN", "unknown")
    if request.query_params.get("options") == "all":
        # Device's first-ever registration call — it wants its push
        # schedule/config back in this exact key=value block.
        logger.info(f"ADMS device {sn} registered (options handshake)")
        body = (
            f"GET OPTION FROM: {sn}\n"
            "Stamp=9999\n"
            "OpStamp=0\n"
            "ErrorDelay=30\n"
            "Delay=10\n"
            "TransTimes=00:00;14:05\n"
            "TransInterval=1\n"
            "TransFlag=1111000000\n"
            "Realtime=1\n"
            "Encrypt=0\n"
        )
        return PlainTextResponse(body)
    # Periodic non-attendance pulls (e.g. table=OPERLOG) — nothing for us
    # to do, just acknowledge so the device doesn't keep retrying.
    return _ok()


@adms_router.post("/cdata")
async def adms_cdata_post(request: Request):
    sn = request.query_params.get("SN", "unknown")
    table = request.query_params.get("table", "")
    body = (await request.body()).decode(errors="replace")

    if table != "ATTLOG" or not body.strip():
        return _ok()

    processed = 0
    async with get_connection() as db:
        for line in body.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                parts = line.split()  # some firmwares use plain spaces
            if len(parts) < 2:
                continue
            pin_str, time_str = parts[0], parts[1]
            try:
                device_user_id = int(pin_str)
                punch_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.warning(f"ADMS {sn}: couldn't parse ATTLOG line: {line!r}")
                continue

            from backend.routers.main_routers import _ingest_punch
            result = await _ingest_punch(db, device_user_id, punch_dt)
            if result is None:
                logger.warning(f"ADMS {sn}: punch from unknown device_user_id={device_user_id}")
            else:
                processed += 1

    logger.info(f"ADMS {sn}: processed {processed} attendance line(s)")
    return _ok()


@adms_router.get("/getrequest")
async def adms_getrequest(request: Request):
    # No pending commands to send down to the device.
    return _ok()


@adms_router.post("/devicecmd")
async def adms_devicecmd(request: Request):
    return _ok()
