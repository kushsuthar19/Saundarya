"""
WhatsApp Templates + Broadcast — click a template, pick an audience, send to
many clients in one go via AiSensy's approved campaigns.

Each row in wa_templates points at one AiSensy campaign you already had
WhatsApp-approve, plus a `params` list describing that campaign's {{1}},
{{2}}, ... variables in order:
  - type "client_name" / "phone": auto-filled per recipient from `clients`
  - type "static": typed once in the composer, reused for every recipient
"""
import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import oracledb

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.services.whatsapp_service import send_aisensy_template

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wa-templates", tags=["wa-templates"])

# Keep AiSensy from being hammered — small concurrency + delay between sends.
_BROADCAST_CONCURRENCY = 3
_BROADCAST_DELAY_SEC = 0.25


def _row_to_template(row, cols) -> dict:
    d = dict(zip(cols, row))
    try:
        d["params"] = json.loads(d["params"]) if d.get("params") else []
    except Exception:
        d["params"] = []
    return d


# ── list / create / update / delete templates ──────────────────────────────

@router.get("")
async def list_templates(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, name, campaign_name, params, is_active,
                  TO_CHAR(created_at,'YYYY-MM-DD HH24:MI') as created_at
           FROM wa_templates ORDER BY created_at DESC"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [_row_to_template(r, cols) for r in rows]


@router.post("", status_code=201)
async def create_template(
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    name = (data.get("name") or "").strip()
    campaign_name = (data.get("campaign_name") or "").strip()
    params = data.get("params") or []
    if not name or not campaign_name:
        raise HTTPException(status_code=400, detail="name and campaign_name are required")
    if not isinstance(params, list):
        raise HTTPException(status_code=400, detail="params must be a list")

    cursor = db.cursor()
    await cursor.execute(
        """INSERT INTO wa_templates (name, campaign_name, params, created_by)
           VALUES (:1,:2,:3,:4)
           RETURNING id INTO :5""",
        [name, campaign_name, json.dumps(params), current_user["id"], cursor.var(oracledb.NUMBER)]
    )
    new_id = cursor.bindvars[-1].getvalue()
    await db.commit()
    return {"id": int(new_id[0] if isinstance(new_id, list) else new_id), "name": name}


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    updates, params_sql = [], []

    def add(col, val):
        params_sql.append(val)
        updates.append(f"{col}=:{len(params_sql)}")

    if data.get("name") is not None:
        add("name", data["name"].strip())
    if data.get("campaign_name") is not None:
        add("campaign_name", data["campaign_name"].strip())
    if data.get("params") is not None:
        if not isinstance(data["params"], list):
            raise HTTPException(status_code=400, detail="params must be a list")
        add("params", json.dumps(data["params"]))
    if data.get("is_active") is not None:
        add("is_active", 1 if data["is_active"] else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at=SYSTIMESTAMP")
    params_sql.append(template_id)
    await cursor.execute(
        f"UPDATE wa_templates SET {', '.join(updates)} WHERE id=:{len(params_sql)}",
        params_sql
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.commit()
    return {"updated": True}


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute("DELETE FROM wa_templates WHERE id=:1", [template_id])
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.commit()
    return {"deleted": template_id}


# ── audience preview ────────────────────────────────────────────────────────

async def _resolve_audience(cursor, audience: str, tag: Optional[str], client_ids: Optional[list]) -> list:
    """Returns [{'id','name','phone'}] for whoever should receive the broadcast."""
    if audience == "manual":
        ids = [int(i) for i in (client_ids or [])]
        if not ids:
            return []
        placeholders = ",".join(f":{i+1}" for i in range(len(ids)))
        await cursor.execute(
            f"SELECT id, name, phone FROM clients WHERE id IN ({placeholders}) AND phone IS NOT NULL",
            ids
        )
    elif audience == "tag":
        if not tag:
            raise HTTPException(status_code=400, detail="tag is required for audience=tag")
        await cursor.execute(
            "SELECT id, name, phone FROM clients WHERE tag=:1 AND phone IS NOT NULL",
            [tag]
        )
    else:  # "all"
        await cursor.execute("SELECT id, name, phone FROM clients WHERE phone IS NOT NULL")
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@router.post("/audience-preview")
async def audience_preview(
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    recipients = await _resolve_audience(
        cursor, data.get("audience", "all"), data.get("tag"), data.get("client_ids")
    )
    return {"count": len(recipients)}


# ── broadcast send ──────────────────────────────────────────────────────────

@router.post("/{template_id}/broadcast")
async def broadcast_template(
    template_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id, name, campaign_name, params FROM wa_templates WHERE id=:1 AND is_active=1",
        [template_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found or inactive")
    _, tmpl_name, campaign_name, params_raw = row
    try:
        param_defs = json.loads(params_raw) if params_raw else []
    except Exception:
        param_defs = []

    audience = data.get("audience", "all")
    tag = data.get("tag")
    client_ids = data.get("client_ids")
    static_values = data.get("static_values") or {}

    recipients = await _resolve_audience(cursor, audience, tag, client_ids)
    if not recipients:
        raise HTTPException(status_code=400, detail="No clients match this audience (need a phone number on file)")

    def build_params(recipient: dict) -> list:
        out = []
        for p in param_defs:
            ptype = p.get("type", "static")
            if ptype == "client_name":
                out.append(recipient.get("name") or "")
            elif ptype == "phone":
                out.append(recipient.get("phone") or "")
            else:
                out.append(static_values.get(p.get("label", ""), ""))
        return out

    sem = asyncio.Semaphore(_BROADCAST_CONCURRENCY)
    failures = []
    sent_count = 0

    async def send_one(recipient: dict):
        nonlocal sent_count
        async with sem:
            result = await send_aisensy_template(
                recipient["phone"], campaign_name, build_params(recipient),
                user_name=recipient.get("name") or ""
            )
            await asyncio.sleep(_BROADCAST_DELAY_SEC)
            if result.get("success"):
                sent_count += 1
            else:
                failures.append({
                    "client_id": recipient["id"], "name": recipient.get("name"),
                    "phone": recipient.get("phone"), "error": result.get("error"),
                })

    await asyncio.gather(*(send_one(r) for r in recipients))

    audience_desc = {
        "all": "All clients",
        "tag": f"Tag: {tag}",
        "manual": f"{len(recipients)} hand-picked clients",
    }.get(audience, audience)

    try:
        await cursor.execute(
            """INSERT INTO wa_broadcasts
                   (template_id, template_name, audience_desc, total_count, sent_count, failed_count, failures, sent_by)
               VALUES (:1,:2,:3,:4,:5,:6,:7,:8)""",
            [template_id, tmpl_name, audience_desc, len(recipients), sent_count, len(failures),
             json.dumps(failures[:100]), current_user["id"]]
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log broadcast: {e}")

    return {
        "total": len(recipients),
        "sent": sent_count,
        "failed": len(failures),
        "failures": failures[:20],
    }


@router.get("/broadcasts/history")
async def broadcast_history(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, template_name, audience_desc, total_count, sent_count, failed_count,
                  TO_CHAR(created_at,'YYYY-MM-DD HH24:MI') as created_at
           FROM wa_broadcasts ORDER BY created_at DESC FETCH FIRST 50 ROWS ONLY"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]
