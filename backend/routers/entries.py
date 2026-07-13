"""Daily entries (bills/invoices) endpoints."""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
import oracledb
import io

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.schemas.schemas import DailyEntryCreate, DailyEntryOut
from backend.services.pdf_service import generate_daily_invoice, generate_daily_batch_pdf
from backend.services.whatsapp_service import send_whatsapp_message, build_daily_invoice_message

router = APIRouter(prefix="/entries", tags=["entries"])


async def _get_next_inv_no(cursor) -> str:
    await cursor.execute("SELECT seq_inv.NEXTVAL FROM DUAL")
    row = await cursor.fetchone()
    return f"INV-{row[0]}"


async def _get_entry_with_items(entry_id: int, cursor) -> dict:
    await cursor.execute(
        """SELECT id, inv_no, client_id, client_name, phone, entry_date, visit_type,
                  services, gross_total, discount, net_total, pay_method,
                  next_visit, remarks, wa_sent, created_at
           FROM daily_entries WHERE id = :1""",
        [entry_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")
    cols = [d[0].lower() for d in cursor.description]
    entry = dict(zip(cols, row))
    # Get items
    await cursor.execute(
        """SELECT id, service_name, price, qty, staff_id, staff_name, line_total
           FROM entry_items WHERE entry_id = :1 ORDER BY id""",
        [entry_id]
    )
    items = await cursor.fetchall()
    item_cols = [d[0].lower() for d in cursor.description]
    entry["items"] = [dict(zip(item_cols, r)) for r in items]
    return entry


@router.get("", response_model=List[DailyEntryOut])
async def list_entries(
    entry_date: Optional[date] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    pay_method: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id, inv_no, client_id, client_name, phone, entry_date, visit_type,
                    services, gross_total, discount, net_total, pay_method,
                    next_visit, remarks, wa_sent, created_at
             FROM daily_entries WHERE 1=1"""
    params = []
    if entry_date:
        sql += " AND entry_date = TO_DATE(:ed,'YYYY-MM-DD')"
        params.append(str(entry_date))
    if from_date:
        sql += " AND entry_date >= TO_DATE(:fd,'YYYY-MM-DD')"
        params.append(str(from_date))
    if to_date:
        sql += " AND entry_date <= TO_DATE(:td,'YYYY-MM-DD')"
        params.append(str(to_date))
    if pay_method:
        sql += " AND pay_method = :pm"
        params.append(pay_method)
    if visit_type:
        sql += " AND visit_type = :vt"
        params.append(visit_type)
    if search:
        sql += " AND (UPPER(client_name) LIKE :s1 OR inv_no LIKE :s2)"
        params += [f"%{search.upper()}%", f"%{search}%"]
    sql += " ORDER BY entry_date DESC, id DESC OFFSET :sk ROWS FETCH NEXT :lm ROWS ONLY"
    params += [skip, limit]
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    entries = []
    for r in rows:
        e = dict(zip(cols, r))
        await cursor.execute(
            "SELECT id, service_name, price, qty, staff_id, staff_name, line_total FROM entry_items WHERE entry_id = :1",
            [e["id"]]
        )
        item_rows = await cursor.fetchall()
        ic = [d[0].lower() for d in cursor.description]
        e["items"] = [dict(zip(ic, ir)) for ir in item_rows]
        entries.append(e)
    return entries


@router.post("", response_model=DailyEntryOut, status_code=201)
async def create_entry(
    data: DailyEntryCreate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    inv_no = await _get_next_inv_no(cursor)

    # Calculate totals
    gross = sum(item.price * item.qty for item in data.items)
    net = max(0, gross - data.discount)
    services_str = ", ".join(
        f"{item.service_name}{f' ×{item.qty}' if item.qty > 1 else ''}"
        for item in data.items
    )

    # Find or create client
    client_id = None
    if data.phone:
        await cursor.execute("SELECT id FROM clients WHERE phone = :1", [data.phone])
        row = await cursor.fetchone()
        if row:
            client_id = row[0]
    if not client_id:
        await cursor.execute(
            "SELECT id FROM clients WHERE UPPER(name) = :1 AND phone IS NULL",
            [data.client_name.upper()]
        )
        row = await cursor.fetchone()
        if row:
            client_id = row[0]
    if not client_id:
        # Auto-create client
        await cursor.execute(
            """INSERT INTO clients (name, phone, source) VALUES (:1,:2,'Daily Entry')
               RETURNING id INTO :3""",
            [data.client_name, data.phone, cursor.var(oracledb.NUMBER)]
        )
        cid_var = cursor.bindvars[-1]
        cid_val = cid_var.getvalue()
        client_id = int(cid_val[0] if isinstance(cid_val, list) else cid_val)

    # Update client stats
    await cursor.execute(
        "UPDATE clients SET visits = visits + 1, total_spent = total_spent + :1, updated_at = SYSTIMESTAMP WHERE id = :2",
        [net, client_id]
    )

    # Insert entry
    nv = str(data.next_visit) if data.next_visit else None
    await cursor.execute(
        """INSERT INTO daily_entries
           (inv_no, client_id, client_name, phone, entry_date, visit_type,
            services, gross_total, discount, net_total, pay_method, next_visit, remarks, created_by)
           VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),:6,:7,:8,:9,:10,:11,
                   TO_DATE(:12,'YYYY-MM-DD'),:13,:14)
           RETURNING id INTO :15""",
        [inv_no, client_id, data.client_name, data.phone, str(data.entry_date),
         data.visit_type, services_str, gross, data.discount, net, data.pay_method,
         nv, data.remarks, int(current_user["id"]),
         cursor.var(oracledb.NUMBER)]
    )
    eid_val = cursor.bindvars[-1].getvalue()
    entry_id = int(eid_val[0] if isinstance(eid_val, list) else eid_val)

    # Insert items + update staff commission
    for item in data.items:
        line_total = item.price * item.qty
        await cursor.execute(
            """INSERT INTO entry_items (entry_id, service_name, price, qty, staff_id, staff_name, line_total)
               VALUES (:1,:2,:3,:4,:5,:6,:7)""",
            [entry_id, item.service_name, item.price, item.qty,
             item.staff_id, item.staff_name, line_total]
        )
        if item.staff_id:
            await cursor.execute(
                """UPDATE staff
                   SET total_services = total_services + 1,
                       comm_earned = comm_earned + :1,
                       updated_at = SYSTIMESTAMP
                   WHERE id = :2""",
                [line_total * (await _get_staff_commission(item.staff_id, cursor) / 100), item.staff_id]
            )

    await db.commit()
    return await _get_entry_with_items(entry_id, cursor)


async def _get_staff_commission(staff_id: int, cursor) -> float:
    await cursor.execute("SELECT commission_pct FROM staff WHERE id = :1", [staff_id])
    row = await cursor.fetchone()
    return float(row[0]) if row else 10.0


@router.get("/{entry_id}", response_model=DailyEntryOut)
async def get_entry(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    return await _get_entry_with_items(entry_id, cursor)


# ── PDF Invoice ───────────────────────────────────────────
@router.get("/{entry_id}/pdf")
async def download_invoice_pdf(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    entry = await _get_entry_with_items(entry_id, cursor)
    pdf_bytes = generate_daily_invoice(entry, entry["items"])
    filename = f"Invoice_{entry['inv_no']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ── Batch PDF for a date ──────────────────────────────────
@router.get("/batch/pdf")
async def download_batch_pdf(
    entry_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Download all invoices for a date as a single PDF."""
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id FROM daily_entries WHERE entry_date = TO_DATE(:1,'YYYY-MM-DD') ORDER BY id",
        [str(entry_date)]
    )
    ids = [r[0] for r in await cursor.fetchall()]
    if not ids:
        raise HTTPException(status_code=404, detail=f"No entries for date {entry_date}")

    entries_data = []
    for eid in ids:
        e = await _get_entry_with_items(eid, cursor)
        entries_data.append({"entry": e, "items": e["items"]})

    pdf_bytes = generate_daily_batch_pdf(entries_data, entry_date)
    filename = f"DailyReport_{entry_date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ── Send WhatsApp ─────────────────────────────────────────
@router.post("/{entry_id}/whatsapp")
async def send_invoice_whatsapp(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    entry = await _get_entry_with_items(entry_id, cursor)

    if not entry.get("phone"):
        raise HTTPException(status_code=400, detail="No phone number for this entry")

    message = build_daily_invoice_message(entry, entry["items"])
    result = await send_whatsapp_message(entry["phone"], message)

    if result["success"]:
        await cursor.execute(
            "UPDATE daily_entries SET wa_sent = 1 WHERE id = :1", [entry_id]
        )
        await db.commit()
        return {"success": True, "message": "WhatsApp sent"}
    else:
        return {"success": False, "error": result.get("error")}


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        await cursor.execute("DELETE FROM entry_items WHERE entry_id=:1", [entry_id])
        await db.commit()
        await cursor.execute("DELETE FROM daily_entries WHERE id=:1", [entry_id])
        await db.commit()
        return {"deleted": entry_id}
    except Exception as e:
        try: await db.rollback()
        except Exception: pass
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.patch("/{entry_id}")
async def update_entry(
    entry_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    # Update main entry fields
    fields = []
    values = []
    allowed = ['client_name','phone','discount','pay_method','remarks','net_total','gross_total']
    if data.get('entry_date'):
        fields.append(f"entry_date=TO_DATE(:{len(fields)+1},'YYYY-MM-DD')")
        values.append(data['entry_date'])
    for k, v2 in data.items():
        if k in allowed:
            fields.append(f"{k}=:{len(values)+1}")
            values.append(v2)
    if fields:
        values.append(entry_id)
        await cursor.execute(
            f"UPDATE daily_entries SET {','.join(fields)},updated_at=SYSTIMESTAMP WHERE id=:{len(values)}",
            values
        )
    # Update items if provided
    items = data.get('items')
    if items is not None:
        # Delete existing items and re-insert (now includes staff assignment)
        await cursor.execute("DELETE FROM entry_items WHERE entry_id=:1", [entry_id])
        for it in items:
            await cursor.execute(
                """INSERT INTO entry_items (entry_id, service_name, price, qty, staff_id, staff_name, line_total)
                   VALUES (:1,:2,:3,:4,:5,:6,:7)""",
                [entry_id, it.get('service_name',''), it.get('price',0),
                 it.get('qty',1), it.get('staff_id'), it.get('staff_name'),
                 it.get('line_total',0)]
            )
        # Update services string in main entry
        svc_str = ', '.join(it.get('service_name','') for it in items if it.get('service_name'))
        await cursor.execute(
            "UPDATE daily_entries SET services=:1 WHERE id=:2",
            [svc_str[:2000], entry_id]
        )
    await db.commit()
    return {"updated": entry_id}