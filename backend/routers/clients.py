"""Clients CRUD endpoints + Membership Module — all Oracle bind params positional."""
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
        """SELECT id, name, phone, email,
                  TO_CHAR(birthday,'YYYY-MM-DD') as birthday,
                  skin_type, hair_type, tag, preferences,
                  NVL(visits,0) as visits,
                  NVL(total_spent,0) as total_spent,
                  source, created_at,
                  NVL(client_type,'New') as client_type,
                  TO_CHAR(anniversary,'YYYY-MM-DD') as anniversary,
                  preferred_staff,
                  NVL(visit_count,0) as visit_count,
                  TO_CHAR(last_visit,'YYYY-MM-DD') as last_visit
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
    sql = """SELECT id, name, phone, email,
                    TO_CHAR(birthday,'YYYY-MM-DD') as birthday,
                    skin_type, hair_type, tag, preferences,
                    NVL(visits,0) as visits,
                    NVL(total_spent,0) as total_spent,
                    source, created_at,
                    NVL(client_type,'New') as client_type,
                    TO_CHAR(anniversary,'YYYY-MM-DD') as anniversary,
                    preferred_staff,
                    NVL(visit_count,0) as visit_count,
                    TO_CHAR(last_visit,'YYYY-MM-DD') as last_visit
             FROM clients WHERE 1=1"""
    params = []

    def P():
        return f":{len(params)+1}"

    if search:
        sql += f" AND (UPPER(name) LIKE {P()} OR phone LIKE {P()})"
        params += [f"%{search.upper()}%", f"%{search}%"]
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


# ── lookup by phone ───────────────────────────────────────────────────────────

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
                  TO_CHAR(c.last_visit,'YYYY-MM-DD') as last_visit,
                  m.membership_id, m.status as mem_status,
                  TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                  m.id as membership_db_id,
                  NVL((SELECT SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END)
                       FROM beauty_points_log l WHERE l.membership_id=m.id), m.beauty_points) as beauty_points
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
    ann = data.anniversary.strftime("%Y-%m-%d") if getattr(data, 'anniversary', None) else None
    pst = getattr(data, 'preferred_staff', None)

    gender = getattr(data, 'gender', None)
    address = getattr(data, 'address', None)
    client_type_val = getattr(data, 'client_type', 'New') or 'New'
    await cursor.execute(
        """INSERT INTO clients (name, phone, email, birthday, skin_type, hair_type,
                                tag, preferences, source, client_type,
                                anniversary, preferred_staff, gender, address)
           VALUES (:1,:2,:3,
                   CASE WHEN :4 IS NOT NULL THEN TO_DATE(:5,'YYYY-MM-DD') ELSE NULL END,
                   :6,:7,:8,:9,:10,:11,
                   CASE WHEN :12 IS NOT NULL THEN TO_DATE(:13,'YYYY-MM-DD') ELSE NULL END,
                   :14,:15,:16)
           RETURNING id INTO :17""",
        [data.name, data.phone, data.email,
         bday, bday,
         data.skin_type or 'Normal', data.hair_type or 'Normal',
         data.tag or 'Regular', data.preferences, data.source or 'Manual',
         client_type_val, ann, ann, pst, gender, address,
         cursor.var(oracledb.NUMBER)]
    )
    new_id = cursor.bindvars[-1].getvalue()
    await db.commit()
    return await _get_client(int(new_id[0] if isinstance(new_id, list) else new_id), cursor)


# ── get single client ─────────────────────────────────────────────────────────

# ── NFC Card endpoints ───────────────────────────────────────────────────────

@router.post("/{client_id}/nfc-card")
async def register_nfc_card(
    client_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Register or replace NFC card UID for a member."""
    cursor = db.cursor()
    uid = (data.get('card_uid') or '').strip()
    if not uid:
        raise HTTPException(status_code=400, detail="Card UID is required")

    # Check UID not already used by another client
    await cursor.execute(
        """SELECT n.id, c.name FROM nfc_cards n
           JOIN memberships m ON m.id=n.membership_id
           JOIN clients c ON c.id=m.client_id
           WHERE n.card_uid=:1 AND n.status='Active'""",
        [uid]
    )
    existing = await cursor.fetchone()
    if existing:
        raise HTTPException(status_code=400, detail=f"UID already assigned to {existing[1]}")

    # Get active membership id
    await cursor.execute(
        "SELECT id FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    mem_row = await cursor.fetchone()
    if not mem_row:
        raise HTTPException(status_code=404, detail="No active membership found for this client")
    mem_id = mem_row[0]

    # Deactivate any old cards for this membership
    await cursor.execute(
        "UPDATE nfc_cards SET status='Inactive', deactivated_at=SYSTIMESTAMP WHERE membership_id=:1 AND status='Active'",
        [mem_id]
    )

    # Insert new card
    await cursor.execute(
        """INSERT INTO nfc_cards (membership_id, card_uid, status, issued_date)
           VALUES (:1, :2, 'Active', SYSDATE)
           RETURNING id INTO :3""",
        [mem_id, uid, cursor.var(oracledb.NUMBER)]
    )
    await db.commit()
    return {"registered": True, "card_uid": uid, "membership_id": mem_id}


@router.get("/card-search")
async def nfc_lookup(
    uid: str,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Look up client by NFC card UID or membership ID."""
    cursor = db.cursor()
    uid = uid.strip()

    # Try NFC card UID first
    await cursor.execute(
        """SELECT c.id, c.name, c.phone, NVL(c.client_type,'New') as client_type,
                  m.membership_id, m.beauty_points,
                  TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                  m.status as mem_status
           FROM nfc_cards n
           JOIN memberships m ON m.id=n.membership_id
           JOIN clients c ON c.id=m.client_id
           WHERE n.card_uid=:1 AND n.status='Active'""",
        [uid]
    )
    row = await cursor.fetchone()

    # If not found by UID, try membership_id (SBC001 etc)
    if not row:
        await cursor.execute(
            """SELECT c.id, c.name, c.phone, NVL(c.client_type,'New') as client_type,
                      m.membership_id, m.beauty_points,
                      TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                      m.status as mem_status
               FROM memberships m
               JOIN clients c ON c.id=m.client_id
               WHERE UPPER(m.membership_id)=UPPER(:1) AND m.status='Active'""",
            [uid]
        )
        row = await cursor.fetchone()

    if not row:
        return None
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


@router.get("/{client_id}/nfc-card")
async def get_nfc_card(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Get NFC card status for a member."""
    cursor = db.cursor()
    await cursor.execute(
        """SELECT n.card_uid, n.status,
                  TO_CHAR(n.issued_date,'YYYY-MM-DD') as issued_date,
                  m.membership_id
           FROM nfc_cards n
           JOIN memberships m ON m.id=n.membership_id
           WHERE m.client_id=:1 AND n.status='Active'
           ORDER BY n.issued_date DESC""",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        return {"card_uid": None, "status": "Not Assigned", "issued_date": None, "membership_id": None}
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


@router.get("/{client_id}/membership/points-log")
async def get_points_log(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT l.entry_type, l.points, l.notes, l.reference_inv,
                  TO_CHAR(l.created_at,'YYYY-MM-DD HH24:MI') as created_at
           FROM beauty_points_log l
           WHERE l.membership_id IN (
               SELECT id FROM memberships WHERE client_id=:1
           )
           ORDER BY l.created_at ASC""",
        [client_id]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    # Calculate running balance for each row
    balance = 0
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        if d['entry_type'] == 'redeem':
            balance -= int(d['points'] or 0)
        else:
            balance += int(d['points'] or 0)
        d['running_balance'] = balance
        result.append(d)
    # Return newest first
    result.reverse()
    return result


@router.get("/membership/expiry-notifications")
async def expiry_notifications(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
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

    def add(col_expr, val):
        updates.append(col_expr.replace("?", f":{len(params)+1}"))
        params.append(val)

    if data.name is not None:          add("name=?", data.name)
    if data.phone is not None:         add("phone=?", data.phone)
    if data.email is not None:         add("email=?", data.email)
    if data.birthday is not None:
        bday = data.birthday.strftime("%Y-%m-%d")
        updates.append(f"birthday=TO_DATE(:{len(params)+1},'YYYY-MM-DD')")
        params.append(bday)
    if data.skin_type is not None:     add("skin_type=?", data.skin_type)
    if data.hair_type is not None:     add("hair_type=?", data.hair_type)
    if data.tag is not None:           add("tag=?", data.tag)
    if data.preferences is not None:   add("preferences=?", data.preferences)
    ann = getattr(data, 'anniversary', None)
    if ann is not None:
        av = ann.strftime("%Y-%m-%d")
        updates.append(f"anniversary=TO_DATE(:{len(params)+1},'YYYY-MM-DD')")
        params.append(av)
    pst = getattr(data, 'preferred_staff', None)
    if pst is not None:                add("preferred_staff=?", pst)
    gender = getattr(data, 'gender', None)
    if gender is not None:             add("gender=?", gender)
    address = getattr(data, 'address', None)
    if address is not None:            add("address=?", address)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at=SYSTIMESTAMP")
    params.append(client_id)
    sql = f"UPDATE clients SET {', '.join(updates)} WHERE id=:{len(params)}"
    await cursor.execute(sql, params)
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
        # Step 1: Nullify foreign keys in entries/appointments
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

        # Step 2: Get membership IDs before deleting
        await cursor.execute(
            "SELECT id FROM memberships WHERE client_id=:1",
            [client_id]
        )
        mem_rows = await cursor.fetchall()
        mem_ids = [r[0] for r in mem_rows]

        # Step 3: Delete beauty_points_log and nfc_cards (FK to memberships)
        for mid in mem_ids:
            try:
                await cursor.execute(
                    "DELETE FROM beauty_points_log WHERE membership_id=:1", [mid]
                )
                await db.commit()
            except Exception:
                try: await db.rollback()
                except Exception: pass
            try:
                await cursor.execute(
                    "DELETE FROM nfc_cards WHERE membership_id=:1", [mid]
                )
                await db.commit()
            except Exception:
                try: await db.rollback()
                except Exception: pass

        # Step 4: Now safe to delete memberships
        try:
            await cursor.execute(
                "DELETE FROM memberships WHERE client_id=:1", [client_id]
            )
            await db.commit()
        except Exception:
            try: await db.rollback()
            except Exception: pass

        # Step 5: Delete the client
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
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Client already has active membership")

    mem_id = await _next_membership_id(cursor)
    start = date.today()
    # Use provided start_date if given
    if data.get('start_date'):
        try:
            from datetime import datetime as _dt
            start = _dt.strptime(data['start_date'], '%Y-%m-%d').date()
        except Exception:
            pass
    # Use provided expiry_date if given, else +12 months
    expiry = start + timedelta(days=365)
    if data.get('expiry_date'):
        try:
            from datetime import datetime as _dt
            expiry = _dt.strptime(data['expiry_date'], '%Y-%m-%d').date()
        except Exception:
            pass
    # Starting points = 20 gift + any past service points
    past_pts = int(data.get('past_points', 0) or 0)
    starting_pts = 20 + past_pts

    await cursor.execute(
        """INSERT INTO memberships
               (client_id, membership_id, status, fee_paid, start_date, expiry_date,
                beauty_points, lifetime_points, notes)
           VALUES (:1,:2,'Active',:3,TO_DATE(:4,'YYYY-MM-DD'),TO_DATE(:5,'YYYY-MM-DD'),:6,:6,:7)
           RETURNING id INTO :8""",
        [client_id, mem_id, data.get('fee_paid', 1000),
         start.strftime('%Y-%m-%d'), expiry.strftime('%Y-%m-%d'),
         starting_pts,
         data.get('notes', ''),
         cursor.var(oracledb.NUMBER)]
    )
    new_mem_id = cursor.bindvars[-1].getvalue()
    new_mem_db_id = int(new_mem_id[0] if isinstance(new_mem_id, list) else new_mem_id)
    await db.commit()
    # Log the 20 gift points
    # Log 20 gift points
    await cursor.execute(
        """INSERT INTO beauty_points_log
               (membership_id, entry_type, points, reference_inv, notes)
           VALUES (:1,'add',20,'GIFT','Welcome gift — 20 joining points')""",
        [new_mem_db_id]
    )
    # Log past service points if any
    past_pts_val = int(data.get('past_points', 0) or 0)
    if past_pts_val > 0:
        await cursor.execute(
            """INSERT INTO beauty_points_log
                   (membership_id, entry_type, points, reference_inv, notes)
               VALUES (:1,'add',:2,'PAST','Points from past services before joining')""",
            [new_mem_db_id, past_pts_val]
        )
    # Sync DB with correct starting balance
    await cursor.execute(
        "UPDATE memberships SET beauty_points=:1, lifetime_points=:1 WHERE id=:2",
        [starting_pts, new_mem_db_id]
    )
    await db.commit()
    await cursor.execute(
        "UPDATE clients SET client_type='Exclusive' WHERE id=:1",
        [client_id]
    )
    await db.commit()
    return {"membership_id": mem_id, "start_date": str(start), "expiry_date": str(expiry), "status": "Active"}


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
                  m.beauty_points,
                  m.lifetime_points,
                  m.notes,
                  ROUND(m.expiry_date - SYSDATE) as days_remaining,
                  NVL((SELECT SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END)
                       FROM beauty_points_log l WHERE l.membership_id=m.id), m.beauty_points) as log_balance,
                  NVL((SELECT SUM(CASE WHEN l.entry_type!='redeem' THEN l.points ELSE 0 END)
                       FROM beauty_points_log l WHERE l.membership_id=m.id), 0) as log_earned
           FROM memberships m
           WHERE m.client_id=:1
           ORDER BY m.created_at DESC""",
        [client_id]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        # Use log_balance as truth if log exists, else fall back to DB beauty_points
        if d.get('log_balance') is not None:
            d['beauty_points'] = int(d['log_balance'])
        d['lifetime_points'] = int(d.get('log_earned') or d.get('lifetime_points') or 0)
        result.append(d)
    return result


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
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id, beauty_points, lifetime_points FROM memberships WHERE client_id=:1 AND status='Active'",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active membership")
    mem_id = row[0]
    action = data.get('action', 'add')
    points = int(data.get('points', 0))

    # Read TRUE current balance from log (not stale DB column)
    await cursor.execute(
        """SELECT NVL(SUM(CASE WHEN entry_type='redeem' THEN -points ELSE points END),0)
           FROM beauty_points_log WHERE membership_id=:1""",
        [mem_id]
    )
    log_row = await cursor.fetchone()
    true_balance = max(0, int(log_row[0] or 0)) if log_row else 0

    if action == 'redeem':
        if points > true_balance:
            raise HTTPException(status_code=400, detail=f"Insufficient points. Balance: {true_balance}")

    # Insert into log FIRST
    await cursor.execute(
        """INSERT INTO beauty_points_log
               (membership_id, entry_type, points, reference_inv, notes)
           VALUES (:1,:2,:3,:4,:5)""",
        [mem_id, action, points,
         data.get('invoice', '') or '',
         data.get('notes', '') or '']
    )
    # Sync DB beauty_points from log (source of truth)
    await db.commit()
    # Re-read correct balance directly from log (source of truth)
    await cursor.execute(
        """SELECT
               NVL(SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END), 0) as balance,
               NVL(SUM(CASE WHEN l.entry_type!='redeem' THEN l.points ELSE 0 END), 0) as earned
           FROM beauty_points_log l WHERE l.membership_id=:1""",
        [mem_id]
    )
    log_row = await cursor.fetchone()
    final_balance = max(0, int(log_row[0] or 0))
    final_earned = int(log_row[1] or 0)
    # Write correct values back to DB
    await cursor.execute(
        "UPDATE memberships SET beauty_points=:1, lifetime_points=:2 WHERE id=:3",
        [final_balance, final_earned, mem_id]
    )
    await db.commit()
    return {"beauty_points": final_balance, "lifetime_points": final_earned}