"""Clients CRUD endpoints + Membership Module."""
from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import oracledb
from backend.core.database import get_db
from backend.core.security import get_current_user, require_admin
from backend.schemas.schemas import ClientCreate, ClientUpdate, ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_client(client_id: int, cursor) -> dict:
    await cursor.execute(
        """SELECT id, name, phone, email, birthday, skin_type, hair_type,
                  tag, preferences, visits, total_spent, source, created_at,
                  client_type, anniversary, preferred_staff,
                  visit_count, last_visit
           FROM clients WHERE id = :1""",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


async def _next_membership_id(cursor) -> str:
    await cursor.execute("SELECT COUNT(*) FROM memberships")
    row = await cursor.fetchone()
    count = (row[0] if row else 0) + 1
    return f"SBC{str(count).zfill(3)}"


# ── list clients ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[ClientOut])
async def list_clients(
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    client_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, le=500),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id, name, phone, email, birthday, skin_type, hair_type,
                    tag, preferences, NVL(visits,0) as visits,
                    NVL(total_spent,0) as total_spent, source, created_at,
                    NVL(client_type,'New') as client_type,
                    anniversary, preferred_staff,
                    NVL(visit_count,0) as visit_count,
                    last_visit
             FROM clients WHERE 1=1"""
    params = []
    def P():
        return f":{len(params)+1}"
    if search:
        s = f"%{search.upper()}%"
        sql += f" AND (UPPER(name) LIKE {P()} OR phone LIKE {P()})"
        params += [s, f"%{search}%"]
    if tag:
        sql += f" AND tag = {P()}"
        params.append(tag)
    if client_type:
        sql += f" AND NVL(client_type,'New') = {P()}"
        params.append(client_type)
    sql += f" ORDER BY created_at DESC OFFSET {P()} ROWS FETCH NEXT {P()} ROWS ONLY"
    params += [skip, limit]
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ── lookup by phone (for Daily Entry auto-detect) ────────────────────────────

@router.get("/lookup")
async def lookup_by_phone(
    phone: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT c.id, c.name, c.phone, c.email,
                  NVL(c.client_type,'New') as client_type,
                  NVL(c.visit_count,0) as visit_count,
                  NVL(c.total_spent,0) as total_spent,
                  c.last_visit,
                  m.membership_id, m.status as mem_status,
                  m.expiry_date, m.beauty_points
           FROM clients c
           LEFT JOIN memberships m ON m.client_id=c.id AND m.status='Active'
           WHERE c.phone=:1""",
        [phone]
    )
    row = await cursor.fetchone()
    if not row:
        return None
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


# ── create client ─────────────────────────────────────────────────────────────

@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    data: ClientCreate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    if data.phone:
        await cursor.execute("SELECT id FROM clients WHERE phone = :1", [data.phone])
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Client with this phone already exists")

    bday = data.birthday.strftime("%Y-%m-%d") if data.birthday else None
    ann = data.anniversary.strftime("%Y-%m-%d") if data.anniversary else None
    await cursor.execute(
        """INSERT INTO clients (name, phone, email, birthday, skin_type, hair_type,
                                tag, preferences, source, client_type,
                                anniversary, preferred_staff)
           VALUES (:1,:2,:3,TO_DATE(:4,'YYYY-MM-DD'),:5,:6,:7,:8,:9,'New',
                   TO_DATE(:10,'YYYY-MM-DD'),:11)
           RETURNING id INTO :12""",
        [data.name, data.phone, data.email, bday, data.skin_type, data.hair_type,
         data.tag, data.preferences, data.source, ann,
         getattr(data,'preferred_staff',None),
         cursor.var(oracledb.NUMBER)]
    )
    new_id = cursor.bindvars[-1].getvalue()
    await db.commit()
    return await _get_client(int(new_id[0] if isinstance(new_id, list) else new_id), cursor)


# ── get single client ─────────────────────────────────────────────────────────

@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    return await _get_client(client_id, cursor)


# ── update client ─────────────────────────────────────────────────────────────

@router.put("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    updates = []
    params = []
    if data.name is not None:
        updates.append("name=:n"); params.append(data.name)
    if data.phone is not None:
        updates.append("phone=:ph"); params.append(data.phone)
    if data.email is not None:
        updates.append("email=:em"); params.append(data.email)
    if data.birthday is not None:
        updates.append("birthday=TO_DATE(:bd,'YYYY-MM-DD')"); params.append(data.birthday.strftime("%Y-%m-%d"))
    if data.skin_type is not None:
        updates.append("skin_type=:sk"); params.append(data.skin_type)
    if data.hair_type is not None:
        updates.append("hair_type=:hr"); params.append(data.hair_type)
    if data.tag is not None:
        updates.append("tag=:tg"); params.append(data.tag)
    if data.preferences is not None:
        updates.append("preferences=:pf"); params.append(data.preferences)
    if hasattr(data,'anniversary') and data.anniversary is not None:
        updates.append("anniversary=TO_DATE(:ann,'YYYY-MM-DD')"); params.append(data.anniversary.strftime("%Y-%m-%d"))
    if hasattr(data,'preferred_staff') and data.preferred_staff is not None:
        updates.append("preferred_staff=:pst"); params.append(data.preferred_staff)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at=SYSTIMESTAMP")
    params.append(client_id)
    await cursor.execute(f"UPDATE clients SET {', '.join(updates)} WHERE id=:{len(params)}", params)
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.commit()
    return await _get_client(client_id, cursor)


# ── delete client ─────────────────────────────────────────────────────────────

@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        for sql in [
            "UPDATE daily_entries SET client_id=NULL WHERE client_id=:1",
            "UPDATE appointments SET client_id=NULL WHERE client_id=:1",
        ]:
            try:
                await cursor.execute(sql, [client_id])
                await db.commit()
            except Exception:
                try: await db.rollback()
                except Exception: pass
        await cursor.execute("DELETE FROM memberships WHERE client_id=:1", [client_id])
        await db.commit()
        await cursor.execute("DELETE FROM clients WHERE id=:1", [client_id])
        await db.commit()
        return {"deleted": client_id}
    except Exception as e:
        try: await db.rollback()
        except Exception: pass
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# MEMBERSHIP ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{client_id}/membership")
async def create_membership(
    client_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Enroll client as Exclusive Member."""
    cursor = db.cursor()
    # Check no active membership already
    await cursor.execute(
        "SELECT id FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Client already has active membership")

    mem_id = await _next_membership_id(cursor)
    start = date.today()
    expiry = start + timedelta(days=365)

    await cursor.execute(
        """INSERT INTO memberships
               (client_id, membership_id, status, fee_paid, start_date, expiry_date,
                beauty_points, lifetime_points, notes)
           VALUES (:1,:2,'Active',:3,TO_DATE(:4,'YYYY-MM-DD'),TO_DATE(:5,'YYYY-MM-DD'),
                   0,0,:6)
           RETURNING id INTO :7""",
        [client_id, mem_id, data.get('fee_paid', 1000),
         start.strftime('%Y-%m-%d'), expiry.strftime('%Y-%m-%d'),
         data.get('notes', ''),
         cursor.var(oracledb.NUMBER)]
    )
    await db.commit()

    # Upgrade client to Exclusive
    await cursor.execute(
        "UPDATE clients SET client_type='Exclusive' WHERE id=:1",
        [client_id]
    )
    await db.commit()

    return {
        "membership_id": mem_id,
        "start_date": str(start),
        "expiry_date": str(expiry),
        "status": "Active"
    }


@router.get("/{client_id}/membership")
async def get_membership(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT m.id, m.membership_id, m.status, m.fee_paid,
                  TO_CHAR(m.start_date,'YYYY-MM-DD') as start_date,
                  TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                  m.beauty_points, m.lifetime_points, m.notes,
                  (m.expiry_date - SYSDATE) as days_remaining
           FROM memberships m
           WHERE m.client_id=:1
           ORDER BY m.created_at DESC""",
        [client_id]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@router.post("/{client_id}/membership/renew")
async def renew_membership(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active membership found")
    mem_db_id = row[0]
    new_expiry = (date.today() + timedelta(days=365)).strftime('%Y-%m-%d')
    await cursor.execute(
        """UPDATE memberships
           SET expiry_date=TO_DATE(:1,'YYYY-MM-DD'),
               start_date=TO_DATE(:2,'YYYY-MM-DD')
           WHERE id=:3""",
        [new_expiry, date.today().strftime('%Y-%m-%d'), mem_db_id]
    )
    await db.commit()
    return {"renewed": True, "new_expiry": new_expiry}


@router.put("/{client_id}/membership/points")
async def update_points(
    client_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Add, edit or redeem beauty points manually."""
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id, beauty_points, lifetime_points FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active membership")
    mem_id, current_pts, lifetime_pts = row

    action = data.get('action', 'add')  # add / redeem / set
    points = int(data.get('points', 0))

    if action == 'redeem':
        if points > current_pts:
            raise HTTPException(status_code=400, detail="Insufficient points")
        new_pts = current_pts - points
        new_lifetime = lifetime_pts
    elif action == 'set':
        new_pts = points
        new_lifetime = lifetime_pts
    else:  # add
        new_pts = current_pts + points
        new_lifetime = lifetime_pts + points

    await cursor.execute(
        "UPDATE memberships SET beauty_points=:1, lifetime_points=:2 WHERE id=:3",
        [new_pts, new_lifetime, mem_id]
    )
    # Log the transaction
    await cursor.execute(
        """INSERT INTO beauty_points_log
               (membership_id, entry_type, points, reference_inv, notes)
           VALUES (:1,:2,:3,:4,:5)""",
        [mem_id, action, points,
         data.get('invoice', ''), data.get('notes', '')]
    )
    await db.commit()
    return {"beauty_points": new_pts, "lifetime_points": new_lifetime}


@router.get("/membership/expiry-notifications")
async def expiry_notifications(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Return memberships expiring in 15 days or already expired."""
    cursor = db.cursor()
    await cursor.execute(
        """SELECT c.name, c.phone, m.membership_id, m.status,
                  TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                  ROUND(m.expiry_date - SYSDATE) as days_remaining,
                  c.id as client_id, m.id as mem_id
           FROM memberships m
           JOIN clients c ON c.id=m.client_id
           WHERE m.status='Active'
             AND m.expiry_date <= SYSDATE + 15
           ORDER BY m.expiry_date ASC"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]