"""Clients CRUD endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import oracledb
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.schemas.schemas import ClientCreate, ClientUpdate, ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=List[ClientOut])
async def list_clients(
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    sql = """SELECT id, name, phone, email, birthday, skin_type, hair_type,
                    tag, preferences, visits, total_spent, source, created_at
             FROM clients WHERE 1=1"""
    params = []
    if search:
        sql += " AND (UPPER(name) LIKE :s1 OR phone LIKE :s2)"
        s = f"%{search.upper()}%"
        params += [s, f"%{search}%"]
    if tag:
        sql += " AND tag = :t"
        params.append(tag)
    sql += " ORDER BY created_at DESC OFFSET :skip ROWS FETCH NEXT :lim ROWS ONLY"
    params += [skip, limit]
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    data: ClientCreate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    # Check duplicate phone
    if data.phone:
        await cursor.execute("SELECT id FROM clients WHERE phone = :1", [data.phone])
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Client with this phone already exists")

    bday = data.birthday.strftime("%Y-%m-%d") if data.birthday else None
    await cursor.execute(
        """INSERT INTO clients (name, phone, email, birthday, skin_type, hair_type,
                                tag, preferences, source)
           VALUES (:1,:2,:3,TO_DATE(:4,'YYYY-MM-DD'),:5,:6,:7,:8,:9)
           RETURNING id INTO :10""",
        [data.name, data.phone, data.email, bday, data.skin_type, data.hair_type,
         data.tag, data.preferences, data.source,
         cursor.var(oracledb.NUMBER)]
    )
    new_id = cursor.bindvars[-1].getvalue()
    await db.commit()
    return await _get_client(int(new_id[0] if isinstance(new_id, list) else new_id), cursor)


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    return await _get_client(client_id, cursor)


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        # Nullify ALL possible FK references before deleting
        for tbl_col in [
            ("daily_entries", "client_id"),
            ("appointments", "client_id"),
            ("bridal_bookings", "client_id"),
            ("salary_payments", "client_id"),
        ]:
            try:
                await cursor.execute(
                    f"UPDATE {tbl_col[0]} SET {tbl_col[1]}=NULL WHERE {tbl_col[1]}=:1",
                    [client_id]
                )
            except Exception:
                pass  # Column may not exist in all tables
        await cursor.execute("DELETE FROM clients WHERE id=:1", [client_id])
        await db.commit()
        return {"deleted": client_id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

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
        updates.append("name = :n"); params.append(data.name)
    if data.phone is not None:
        updates.append("phone = :ph"); params.append(data.phone)
    if data.email is not None:
        updates.append("email = :em"); params.append(data.email)
    if data.birthday is not None:
        updates.append("birthday = TO_DATE(:bd,'YYYY-MM-DD')"); params.append(data.birthday.strftime("%Y-%m-%d"))
    if data.skin_type is not None:
        updates.append("skin_type = :sk"); params.append(data.skin_type)
    if data.hair_type is not None:
        updates.append("hair_type = :hr"); params.append(data.hair_type)
    if data.tag is not None:
        updates.append("tag = :tg"); params.append(data.tag)
    if data.preferences is not None:
        updates.append("preferences = :pf"); params.append(data.preferences)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at = SYSTIMESTAMP")
    params.append(client_id)
    await cursor.execute(f"UPDATE clients SET {', '.join(updates)} WHERE id = :{len(params)}", params)
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.commit()
    return await _get_client(client_id, cursor)


async def _get_client(client_id: int, cursor) -> dict:
    await cursor.execute(
        """SELECT id, name, phone, email, birthday, skin_type, hair_type,
                  tag, preferences, visits, total_spent, source, created_at
           FROM clients WHERE id = :1""",
        [client_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))