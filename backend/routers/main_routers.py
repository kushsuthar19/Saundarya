"""
Appointments, Staff, Attendance, Bridal Bookings, Revenue, Reports routers.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
import oracledb

from backend.core.database import get_db
from backend.core.security import get_current_user, require_admin
from backend.schemas.schemas import (
    AppointmentCreate, AppointmentOut,
    StaffCreate, StaffOut,
    AttendanceUpsert, AttendanceOut,
    BridalCreate, BridalOut,
    DashboardStats, RevenueStats, SalaryPaymentCreate,
)
from backend.services.pdf_service import generate_bridal_invoice, generate_sider_invoice
from backend.services.whatsapp_service import send_whatsapp_message, build_bridal_invoice_message
from backend.core.security import hash_password

# ════════════════════════════════
# APPOINTMENTS
# ════════════════════════════════
appt_router = APIRouter(prefix="/appointments", tags=["appointments"])


@appt_router.get("", response_model=List[AppointmentOut])
async def list_appointments(
    appt_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id, client_name, phone, service, appt_date, appt_time,
                    staff_id, staff_name, advance, status, notes, created_at
             FROM appointments WHERE 1=1"""
    params = []
    if appt_date:
        sql += " AND appt_date = TO_DATE(:1,'YYYY-MM-DD')"; params.append(str(appt_date))
    if status:
        sql += " AND status = :2"; params.append(status)
    if search:
        sql += " AND UPPER(client_name) LIKE :3"; params.append(f"%{search.upper()}%")
    sql += " ORDER BY appt_date DESC, appt_time"
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@appt_router.post("", response_model=AppointmentOut, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    ad = str(data.appt_date) if data.appt_date else None
    await cursor.execute(
        """INSERT INTO appointments (client_name, phone, service, appt_date, appt_time,
           staff_id, staff_name, advance, status, notes, created_by)
           VALUES (:1,:2,:3,TO_DATE(:4,'YYYY-MM-DD'),:5,:6,:7,:8,:9,:10,:11)
           RETURNING id INTO :12""",
        [data.client_name, data.phone, data.service, ad, data.appt_time,
         data.staff_id, data.staff_name, data.advance, data.status, data.notes,
         int(current_user["id"]), cursor.var(oracledb.NUMBER)]
    )
    new_id = int(cursor.bindvars[-1].getvalue()[0])
    await db.commit()
    await cursor.execute(
        "SELECT id,client_name,phone,service,appt_date,appt_time,staff_id,staff_name,advance,status,notes,created_at FROM appointments WHERE id=:1",
        [new_id]
    )
    row = await cursor.fetchone()
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


@appt_router.get("/{appt_id}")
async def get_appt(
    appt_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id,client_name,phone,service,appt_date,appt_time,staff_id,staff_name,advance,status,notes FROM appointments WHERE id=:1",
        [appt_id]
    )
    row = await cursor.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))

@appt_router.delete("/{appt_id}")
async def delete_appt(
    appt_id: int,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        await cursor.execute("DELETE FROM appointments WHERE id=:1", [appt_id])
        await db.commit()
        return {"deleted": appt_id}
    except Exception as e:
        await db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@appt_router.patch("/{appt_id}")
async def update_appt(
    appt_id: int,
    data: dict,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    fields = []
    values = []
    allowed = ['client_name','phone','service','appt_date','appt_time','staff_name','advance','status','notes']
    for k,v2 in data.items():
        if k in allowed:
            fields.append(f"{k}=:{len(values)+1}")
            values.append(v2)
    if not fields:
        return {"error": "No valid fields"}
    values.append(appt_id)
    await cursor.execute(f"UPDATE appointments SET {','.join(fields)},updated_at=SYSTIMESTAMP WHERE id=:{len(values)}", values)
    await db.commit()
    return {"updated": appt_id}

@appt_router.patch("/{appt_id}/status")
async def update_status(
    appt_id: int,
    status: str,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    allowed = {"Confirmed", "Pending", "Completed", "Cancelled"}
    if status not in allowed:
        raise HTTPException(400, f"Status must be one of {allowed}")
    cursor = db.cursor()
    await cursor.execute(
        "UPDATE appointments SET status=:1, updated_at=SYSTIMESTAMP WHERE id=:2",
        [status, appt_id]
    )
    if cursor.rowcount == 0:
        raise HTTPException(404, "Appointment not found")
    await db.commit()
    return {"id": appt_id, "status": status}



# ════════════════════════════════
# STAFF
# ════════════════════════════════
staff_router = APIRouter(prefix="/staff", tags=["staff"])


@staff_router.get("", response_model=List[StaffOut])
async def list_staff(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    from datetime import date
    today = date.today()
    month_start = today.strftime('%Y-%m-01')
    month_end = today.strftime('%Y-%m-') + str(today.day).zfill(2)

    await cursor.execute(
        """SELECT s.id, s.name, s.role, s.phone, s.join_date, s.base_salary, s.commission_pct,
                  s.days_present, s.total_services, s.comm_earned, s.paid_salary, s.av_class, s.is_active,
                  NVL(SUM(CASE WHEN a.half_day=1 THEN 1 ELSE 0 END), 0) AS half_day_count,
                  NVL(SUM(CASE WHEN a.morning_duty=1 THEN 1 ELSE 0 END), 0) AS morning_duty_count,
                  NVL(SUM(CASE WHEN a.is_present=1 THEN 1 ELSE 0 END), 0) AS monthly_days_present,
                  NVL((SELECT SUM(ei.line_total)
                       FROM entry_items ei
                       JOIN daily_entries de ON de.id=ei.entry_id
                       WHERE ei.staff_id=s.id
                         AND de.entry_date >= TO_DATE(:1,'YYYY-MM-DD')
                         AND de.entry_date <= TO_DATE(:2,'YYYY-MM-DD')
                  ), 0) AS monthly_revenue
           FROM staff s
           LEFT JOIN attendance a ON a.staff_id=s.id
             AND a.att_date >= TO_DATE(:3,'YYYY-MM-DD')
             AND a.att_date <= TO_DATE(:4,'YYYY-MM-DD')
           WHERE s.is_active=1
           GROUP BY s.id, s.name, s.role, s.phone, s.join_date, s.base_salary, s.commission_pct,
                    s.days_present, s.total_services, s.comm_earned, s.paid_salary, s.av_class, s.is_active
           ORDER BY s.name""",
        [month_start, month_end, month_start, month_end]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@staff_router.post("", response_model=StaffOut, status_code=201)
async def create_staff(
    data: StaffCreate,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    user_id = None

    # Create user account for staff login if username+password provided
    if data.username and data.password:
        await cursor.execute(
            """INSERT INTO users (username, full_name, hashed_pw, role)
               VALUES (:1,:2,:3,'staff') RETURNING id INTO :4""",
            [data.username, data.name, hash_password(data.password), cursor.var(oracledb.NUMBER)]
        )
        uid_val = cursor.bindvars[-1].getvalue()
        user_id = int(uid_val[0] if isinstance(uid_val, list) else uid_val)

    jd = str(data.join_date) if data.join_date else None
    await cursor.execute(
        """INSERT INTO staff (user_id, name, role, phone, join_date, base_salary,
           commission_pct, av_class)
           VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),:6,:7,:8)
           RETURNING id INTO :9""",
        [user_id, data.name, data.role, data.phone, jd,
         data.base_salary, data.commission_pct, data.av_class,
         cursor.var(oracledb.NUMBER)]
    )
    new_id = int(cursor.bindvars[-1].getvalue()[0])
    await db.commit()
    await cursor.execute(
        "SELECT id,name,role,phone,join_date,base_salary,commission_pct,days_present,total_services,comm_earned,paid_salary,av_class,is_active FROM staff WHERE id=:1",
        [new_id]
    )
    row = await cursor.fetchone()
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


@staff_router.get("/{staff_id}/month-detail")
async def staff_month_detail(
    staff_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM, defaults to current month"),
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    from datetime import date as _date
    import calendar
    if not month:
        month = _date.today().strftime('%Y-%m')
    yr, mo = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(yr, mo)[1]
    month_start = f"{yr}-{mo:02d}-01"
    month_end = f"{yr}-{mo:02d}-{days_in_month:02d}"

    # Staff base info
    await cursor.execute(
        "SELECT id, name, role, base_salary FROM staff WHERE id=:1",
        [staff_id]
    )
    srow = await cursor.fetchone()
    if not srow:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Staff not found")
    staff_info = {"id": srow[0], "name": srow[1], "role": srow[2], "base_salary": srow[3] or 0}

    # Day-by-day attendance for the month
    await cursor.execute(
        """SELECT TO_CHAR(att_date,'YYYY-MM-DD') as d, is_present, in_time, out_time,
                  hours_worked, NVL(half_day,0) as half_day, NVL(morning_duty,0) as morning_duty,
                  id
           FROM attendance
           WHERE staff_id=:1 AND att_date>=TO_DATE(:2,'YYYY-MM-DD') AND att_date<=TO_DATE(:3,'YYYY-MM-DD')
           ORDER BY att_date""",
        [staff_id, month_start, month_end]
    )
    att_rows = await cursor.fetchall()
    att_cols = [d[0].lower() for d in cursor.description]
    attendance_by_day = {r[0]: dict(zip(att_cols, r)) for r in att_rows}

    # Services done each day this month by this staff
    await cursor.execute(
        """SELECT TO_CHAR(de.entry_date,'YYYY-MM-DD') as d, de.client_name, ei.service_name,
                  ei.price, ei.qty, ei.line_total, de.inv_no, de.id as entry_id
           FROM entry_items ei
           JOIN daily_entries de ON de.id=ei.entry_id
           WHERE ei.staff_id=:1
             AND de.entry_date>=TO_DATE(:2,'YYYY-MM-DD') AND de.entry_date<=TO_DATE(:3,'YYYY-MM-DD')
           ORDER BY de.entry_date, de.id""",
        [staff_id, month_start, month_end]
    )
    svc_rows = await cursor.fetchall()
    svc_cols = [d[0].lower() for d in cursor.description]
    services_by_day = {}
    monthly_revenue = 0.0
    for r in svc_rows:
        rec = dict(zip(svc_cols, r))
        d = rec['d']
        services_by_day.setdefault(d, []).append(rec)
        monthly_revenue += float(rec['line_total'] or 0)

    # Build full day list
    days = []
    present_count = 0
    half_day_count = 0
    morning_duty_count = 0
    for day in range(1, days_in_month + 1):
        d_str = f"{yr}-{mo:02d}-{day:02d}"
        att = attendance_by_day.get(d_str)
        svcs = services_by_day.get(d_str, [])
        is_present = bool(att and att.get('is_present'))
        is_half = bool(att and att.get('half_day'))
        is_morning = bool(att and att.get('morning_duty'))
        if is_present:
            present_count += 1
        if is_half:
            half_day_count += 1
        if is_morning:
            morning_duty_count += 1
        day_revenue = sum(float(s['line_total'] or 0) for s in svcs)
        days.append({
            "date": d_str,
            "is_present": is_present,
            "half_day": is_half,
            "morning_duty": is_morning,
            "in_time": att.get('in_time') if att else None,
            "out_time": att.get('out_time') if att else None,
            "hours_worked": float(att['hours_worked']) if att and att.get('hours_worked') else None,
            "attendance_id": att.get('id') if att else None,
            "services": svcs,
            "day_revenue": day_revenue,
        })

    # Salary calculation — SAME formula as frontend
    per_day = (staff_info['base_salary'] or 0) / days_in_month if days_in_month else 0
    dp = present_count
    if dp >= half_day_count:
        effective_days = dp - (half_day_count * 0.5)
    else:
        effective_days = dp + (half_day_count * 0.5)
    base_earned = round(per_day * max(0, effective_days))
    morning_pay = morning_duty_count * 150
    comm_pct = 0.03 if monthly_revenue >= 100000 else 0.02
    commission = round(monthly_revenue * comm_pct)
    total_salary = base_earned + commission + morning_pay

    return {
        "staff": staff_info,
        "month": month,
        "days_in_month": days_in_month,
        "days": days,
        "summary": {
            "present_days": present_count,
            "half_day_count": half_day_count,
            "morning_duty_count": morning_duty_count,
            "effective_days": effective_days,
            "per_day_salary": round(per_day),
            "base_earned": base_earned,
            "monthly_revenue": monthly_revenue,
            "commission_pct": comm_pct,
            "commission_amt": commission,
            "morning_duty_pay": morning_pay,
            "total_salary": total_salary,
        }
    }


@staff_router.get("/{staff_id}")
async def get_staff_by_id(
    staff_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, name, role, phone, join_date, base_salary, commission_pct,
                  days_present, total_services, comm_earned, paid_salary, av_class, is_active
           FROM staff WHERE id=:1""",
        [staff_id]
    )
    row = await cursor.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Staff not found")
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))

@staff_router.put("/{staff_id}")
async def update_staff_by_id(
    staff_id: int,
    data: dict,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    fields = []
    values = []
    allowed = ['name','role','phone','join_date','base_salary','commission_pct']
    for k,v2 in data.items():
        if k in allowed:
            fields.append(f"{k}=:{len(values)+1}")
            values.append(v2)
    if not fields:
        return {"error": "No valid fields"}
    values.append(staff_id)
    await cursor.execute(
        f"UPDATE staff SET {','.join(fields)},updated_at=SYSTIMESTAMP WHERE id=:{len(values)}",
        values
    )
    await db.commit()
    return {"updated": staff_id}

@staff_router.delete("/{staff_id}")
async def delete_staff_by_id(
    staff_id: int,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute("UPDATE appointments SET staff_id=NULL WHERE staff_id=:1", [staff_id])
    await cursor.execute("UPDATE entry_items SET staff_id=NULL WHERE staff_id=:1", [staff_id])
    await cursor.execute("DELETE FROM attendance WHERE staff_id=:1", [staff_id])
    await cursor.execute("DELETE FROM salary_payments WHERE staff_id=:1", [staff_id])
    await cursor.execute("SELECT user_id FROM staff WHERE id=:1", [staff_id])
    row = await cursor.fetchone()
    await cursor.execute("UPDATE staff SET is_active=0 WHERE id=:1", [staff_id])
    if row and row[0]:
        await cursor.execute("UPDATE users SET is_active=0 WHERE id=:1", [row[0]])
    await db.commit()
    return {"deleted": staff_id}


# ════════════════════════════════
# ATTENDANCE
# ════════════════════════════════
att_router = APIRouter(prefix="/attendance", tags=["attendance"])


@att_router.get("", response_model=List[AttendanceOut])
async def get_attendance(
    att_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, staff_id, att_date, is_present, in_time, out_time, hours_worked,
                  NVL(half_day,0) AS half_day, NVL(morning_duty,0) AS morning_duty
           FROM attendance WHERE att_date = TO_DATE(:1,'YYYY-MM-DD')""",
        [str(att_date)]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@att_router.post("/upsert", response_model=AttendanceOut)
async def upsert_attendance(
    data: AttendanceUpsert,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    ad = str(data.att_date)

    # Calculate hours
    hours = None
    if data.in_time and data.out_time:
        try:
            ih, im = map(int, data.in_time.split(":"))
            oh, om = map(int, data.out_time.split(":"))
            mins = (oh * 60 + om) - (ih * 60 + im)
            if mins > 0:
                hours = round(mins / 60, 2)
        except Exception:
            pass

    # Check existing
    await cursor.execute(
        "SELECT id, is_present FROM attendance WHERE staff_id=:1 AND att_date=TO_DATE(:2,'YYYY-MM-DD')",
        [data.staff_id, ad]
    )
    existing = await cursor.fetchone()
    is_present = 1 if data.is_present else 0
    morning = 1 if getattr(data, 'morning_duty', False) else 0
    half = 1 if getattr(data, 'half_day', False) else 0

    if existing:
        old_present = existing[1]
        try:
            await cursor.execute(
                """UPDATE attendance SET is_present=:1, in_time=:2, out_time=:3,
                   hours_worked=:4, half_day=:5, morning_duty=:6, updated_at=SYSTIMESTAMP
                   WHERE staff_id=:7 AND att_date=TO_DATE(:8,'YYYY-MM-DD')""",
                [is_present, data.in_time, data.out_time, hours, half, morning, data.staff_id, ad]
            )
        except Exception:
            # Fallback if morning_duty column doesn't exist yet
            await cursor.execute(
                """UPDATE attendance SET is_present=:1, in_time=:2, out_time=:3,
                   hours_worked=:4, half_day=:5, updated_at=SYSTIMESTAMP
                   WHERE staff_id=:6 AND att_date=TO_DATE(:7,'YYYY-MM-DD')""",
                [is_present, data.in_time, data.out_time, hours, half, data.staff_id, ad]
            )
        # Update days_present count
        if old_present != is_present:
            delta = 1 if is_present else -1
            await cursor.execute(
                "UPDATE staff SET days_present=GREATEST(0, days_present+:1) WHERE id=:2",
                [delta, data.staff_id]
            )
    else:
        try:
            await cursor.execute(
                """INSERT INTO attendance (staff_id, att_date, is_present, in_time, out_time, hours_worked, half_day, morning_duty)
                   VALUES (:1,TO_DATE(:2,'YYYY-MM-DD'),:3,:4,:5,:6,:7,:8)""",
                [data.staff_id, ad, is_present, data.in_time, data.out_time, hours, half, morning]
            )
        except Exception:
            # Fallback if morning_duty column doesn't exist yet
            await cursor.execute(
                """INSERT INTO attendance (staff_id, att_date, is_present, in_time, out_time, hours_worked, half_day)
                   VALUES (:1,TO_DATE(:2,'YYYY-MM-DD'),:3,:4,:5,:6,:7)""",
                [data.staff_id, ad, is_present, data.in_time, data.out_time, hours, half]
            )
        if is_present:
            await cursor.execute(
                "UPDATE staff SET days_present=days_present+1 WHERE id=:1", [data.staff_id]
            )

    await db.commit()
    await cursor.execute(
        "SELECT id,staff_id,att_date,is_present,in_time,out_time,hours_worked,NVL(half_day,0) AS half_day,NVL(morning_duty,0) AS morning_duty FROM attendance WHERE staff_id=:1 AND att_date=TO_DATE(:2,'YYYY-MM-DD')",
        [data.staff_id, ad]
    )
    row = await cursor.fetchone()
    cols = [d[0].lower() for d in cursor.description]
    return dict(zip(cols, row))


@att_router.get("/monthly")
async def get_monthly_attendance(
    staff_id: int,
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    await cursor.execute(
        """SELECT id, att_date, is_present, in_time, out_time, hours_worked
           FROM attendance
           WHERE staff_id=:1
           AND TO_CHAR(att_date,'YYYY-MM')=:2
           ORDER BY att_date""",
        [staff_id, month]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ════════════════════════════════
# BRIDAL BOOKINGS
# ════════════════════════════════
bridal_router = APIRouter(prefix="/bridal", tags=["bridal"])


async def _next_job_no(booking_type: str, cursor) -> str:
    await cursor.execute("SELECT seq_inv.NEXTVAL FROM DUAL")
    row = await cursor.fetchone()
    prefix = {"Bride": "BR", "Groom": "GR", "Sider": "SD"}.get(booking_type, "BR")
    return f"{prefix}-{row[0]}"


async def _get_bridal(booking_id: int, cursor) -> dict:
    await cursor.execute(
        """SELECT id, job_no, booking_type, client_name, phone, wedding_date, venue,
                  reference, package_name, pkg_amount, transport, discount, advance_paid,
                  balance_due, status, wa_sent, created_at
           FROM bridal_bookings WHERE id=:1""",
        [booking_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Bridal booking not found")
    cols = [d[0].lower() for d in cursor.description]
    booking = dict(zip(cols, row))
    await cursor.execute(
        """SELECT id, function_name, fn_date, fn_time, person_count, pkg_detail, artist_name
           FROM bridal_functions WHERE booking_id=:1 ORDER BY id""",
        [booking_id]
    )
    fn_rows = await cursor.fetchall()
    fn_cols = [d[0].lower() for d in cursor.description]
    booking["functions"] = [dict(zip(fn_cols, r)) for r in fn_rows]
    return booking


@bridal_router.get("", response_model=List[BridalOut])
async def list_bridal(
    booking_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id FROM bridal_bookings WHERE 1=1"""
    params = []
    if booking_type:
        sql += " AND booking_type=:1"; params.append(booking_type)
    if status:
        sql += " AND status=:2"; params.append(status)
    if search:
        sql += " AND UPPER(client_name) LIKE :3"; params.append(f"%{search.upper()}%")
    sql += " ORDER BY created_at DESC"
    await cursor.execute(sql, params)
    ids = [r[0] for r in await cursor.fetchall()]
    return [await _get_bridal(bid, cursor) for bid in ids]


@bridal_router.post("", response_model=BridalOut, status_code=201)
async def create_bridal(
    data: BridalCreate,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    job_no = await _next_job_no(data.booking_type, cursor)
    balance = max(0, data.pkg_amount + data.transport - data.discount - data.advance_paid)
    wd = str(data.wedding_date) if data.wedding_date else None

    await cursor.execute(
        """INSERT INTO bridal_bookings
           (job_no, booking_type, client_name, phone, wedding_date, venue, reference,
            package_name, pkg_amount, transport, discount, advance_paid, balance_due,
            notes, created_by)
           VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),:6,:7,:8,:9,:10,:11,:12,:13,:14,:15)
           RETURNING id INTO :16""",
        [job_no, data.booking_type, data.client_name, data.phone, wd,
         data.venue, data.reference, data.package_name,
         data.pkg_amount, data.transport, data.discount, data.advance_paid,
         balance, data.notes, int(current_user["id"]),
         cursor.var(oracledb.NUMBER)]
    )
    new_id = int(cursor.bindvars[-1].getvalue()[0])

    for fn in data.functions:
        fnd = str(fn.fn_date) if fn.fn_date else None
        await cursor.execute(
            """INSERT INTO bridal_functions
               (booking_id, function_name, fn_date, fn_time, person_count, pkg_detail, artist_id, artist_name)
               VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8)""",
            [new_id, fn.function_name, fnd, fn.fn_time or None,
             fn.person_count or None, fn.pkg_detail or None,
             fn.artist_id, fn.artist_name or None]
        )

    await db.commit()
    return await _get_bridal(new_id, cursor)


@bridal_router.get("/{booking_id}", response_model=BridalOut)
async def get_bridal(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    return await _get_bridal(booking_id, cursor)


@bridal_router.patch("/{booking_id}/status")
async def update_bridal_status(
    booking_id: int,
    status: str,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    allowed = {"Active", "Completed", "Cancelled"}
    if status not in allowed:
        raise HTTPException(400, f"Status must be one of {allowed}")
    cursor = db.cursor()
    await cursor.execute(
        "UPDATE bridal_bookings SET status=:1, updated_at=SYSTIMESTAMP WHERE id=:2",
        [status, booking_id]
    )
    await db.commit()
    return {"id": booking_id, "status": status}


@bridal_router.get("/{booking_id}/pdf")
async def bridal_invoice_pdf(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    booking = await _get_bridal(booking_id, cursor)
    # Use sider-specific invoice for Sider bookings
    if booking.get("booking_type") == "Sider":
        from backend.services.pdf_service import generate_sider_invoice
        pdf_bytes = generate_sider_invoice(booking, booking["functions"])
    else:
        pdf_bytes = generate_bridal_invoice(booking, booking["functions"])
    filename = f"Invoice_{booking['job_no']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@bridal_router.post("/{booking_id}/whatsapp")
async def bridal_whatsapp(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    booking = await _get_bridal(booking_id, cursor)
    if not booking.get("phone"):
        raise HTTPException(400, "No phone number")
    message = build_bridal_invoice_message(booking)
    result = await send_whatsapp_message(booking["phone"], message)
    if result["success"]:
        await cursor.execute(
            "UPDATE bridal_bookings SET wa_sent=1 WHERE id=:1", [booking_id]
        )
        await db.commit()
    return result


@bridal_router.patch("/{booking_id}/edit")
async def edit_bridal(
    booking_id: int,
    data: dict,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    fields = []
    values = []
    allowed = ['client_name','phone','wedding_date','venue','reference',
               'package_name','pkg_amount','transport','discount',
               'advance_paid','status','notes']
    for k, v2 in data.items():
        if k in allowed:
            if k == 'wedding_date' and v2:
                fields.append(f"wedding_date=TO_DATE(:{len(values)+1},'YYYY-MM-DD')")
            else:
                fields.append(f"{k}=:{len(values)+1}")
            values.append(v2)
    if not fields:
        return {"error": "No valid fields"}
    # Recalculate balance_due
    pkg = data.get('pkg_amount', 0) or 0
    tr = data.get('transport', 0) or 0
    disc = data.get('discount', 0) or 0
    adv = data.get('advance_paid', 0) or 0
    balance = max(0, float(pkg) + float(tr) - float(disc) - float(adv))
    fields.append(f"balance_due=:{len(values)+1}")
    values.append(balance)
    fields.append(f"updated_at=SYSTIMESTAMP")
    values.append(booking_id)
    await cursor.execute(
        f"UPDATE bridal_bookings SET {','.join(fields)} WHERE id=:{len(values)}",
        values
    )
    await db.commit()
    return {"updated": booking_id, "balance_due": balance}

@bridal_router.delete("/{booking_id}")
async def delete_bridal(
    booking_id: int,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        # Delete child records first
        await cursor.execute("DELETE FROM bridal_functions WHERE booking_id=:1", [booking_id])
        await db.commit()
        # Then delete parent
        await cursor.execute("DELETE FROM bridal_bookings WHERE id=:1", [booking_id])
        await db.commit()
        return {"deleted": booking_id}
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@bridal_router.patch("/{booking_id}/payment")
async def record_advance_payment(
    booking_id: int,
    amount: float,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Record an advance/due payment. Reduces balance_due, increases advance_paid."""
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    cursor = db.cursor()
    # Get current booking
    await cursor.execute(
        "SELECT advance_paid, balance_due, pkg_amount, transport, discount FROM bridal_bookings WHERE id=:1",
        [booking_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Booking not found")
    advance_paid, balance_due, pkg_amount, transport, discount = row
    new_advance = float(advance_paid or 0) + amount
    new_balance = max(0, float(balance_due or 0) - amount)
    # If fully paid, mark completed
    new_status = "Completed" if new_balance == 0 else "Active"
    await cursor.execute(
        """UPDATE bridal_bookings
           SET advance_paid=:1, balance_due=:2, status=:3, updated_at=SYSTIMESTAMP
           WHERE id=:4""",
        [new_advance, new_balance, new_status, booking_id]
    )
    await db.commit()
    return {
        "booking_id": booking_id,
        "amount_paid": amount,
        "new_advance_paid": new_advance,
        "new_balance_due": new_balance,
        "status": new_status
    }


# ════════════════════════════════
# DASHBOARD
# ════════════════════════════════
dash_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dash_router.get("", response_model=DashboardStats)
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    today = date.today()
    today_str = str(today)

    await cursor.execute(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE entry_date=TO_DATE(:1,'YYYY-MM-DD')",
        [today_str]
    )
    today_rev = float((await cursor.fetchone())[0])

    await cursor.execute(
        "SELECT COUNT(*) FROM appointments WHERE appt_date=TO_DATE(:1,'YYYY-MM-DD')",
        [today_str]
    )
    today_appts = int((await cursor.fetchone())[0])

    await cursor.execute(
        "SELECT COUNT(*) FROM daily_entries WHERE entry_date=TO_DATE(:1,'YYYY-MM-DD') AND visit_type='Walk-in'",
        [today_str]
    )
    today_walkins = int((await cursor.fetchone())[0])

    await cursor.execute("SELECT COUNT(*) FROM bridal_bookings WHERE status='Active'")
    active_bridal = int((await cursor.fetchone())[0])

    await cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE att_date=TO_DATE(:1,'YYYY-MM-DD') AND is_present=1",
        [today_str]
    )
    staff_present = int((await cursor.fetchone())[0])

    await cursor.execute("SELECT COUNT(*) FROM staff WHERE is_active=1")
    staff_total = int((await cursor.fetchone())[0])

    await cursor.execute(
        "SELECT COUNT(*) FROM daily_entries WHERE entry_date=TO_DATE(:1,'YYYY-MM-DD')",
        [today_str]
    )
    today_entries = int((await cursor.fetchone())[0])

    return DashboardStats(
        today_revenue=today_rev,
        today_appointments=today_appts,
        today_walkins=today_walkins,
        active_bridal=active_bridal,
        staff_present=staff_present,
        staff_total=staff_total,
        today_entries=today_entries,
    )


# ════════════════════════════════
# REVENUE (Admin only)
# ════════════════════════════════
revenue_router = APIRouter(prefix="/revenue", tags=["revenue"])


@revenue_router.get("/stats", response_model=RevenueStats)
async def revenue_stats(
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    today_str = str(date.today())
    month_str = date.today().strftime("%Y-%m")
    year_str = date.today().strftime("%Y")

    async def scalar(sql, params=None):
        await cursor.execute(sql, params or [])
        row = await cursor.fetchone()
        return float(row[0]) if row and row[0] else 0.0

    today = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE entry_date=TO_DATE(:1,'YYYY-MM-DD')",
        [today_str]
    )
    month = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1",
        [month_str]
    )
    year = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY')=:1",
        [year_str]
    )
    cash = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1 AND pay_method='Cash'",
        [month_str]
    )
    upi = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1 AND pay_method='UPI'",
        [month_str]
    )
    card = await scalar(
        "SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1 AND pay_method='Card'",
        [month_str]
    )
    dues = await scalar("SELECT COALESCE(SUM(balance_due),0) FROM bridal_bookings WHERE balance_due>0 AND status='Active'")

    advance_paid = await scalar(
        "SELECT COALESCE(SUM(advance_paid),0) FROM bridal_bookings WHERE status IN ('Active','Completed')"
    )
    bridal_value = await scalar(
        "SELECT COALESCE(SUM(pkg_amount+transport-discount),0) FROM bridal_bookings WHERE status='Active'"
    )
    return RevenueStats(
        today=today, this_month=month, this_year=year,
        cash_month=cash, upi_month=upi, card_month=card, pending_dues=dues,
        advance_paid_total=advance_paid, bridal_total_value=bridal_value
    )


@revenue_router.get("/daily")
async def revenue_daily(
    entry_date: Optional[date] = Query(None),
    pay_method: Optional[str] = Query(None),
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id, inv_no, entry_date, client_name, services, gross_total,
                    discount, net_total, pay_method, visit_type
             FROM daily_entries WHERE 1=1"""
    params = []
    if entry_date:
        sql += " AND entry_date=TO_DATE(:1,'YYYY-MM-DD')"; params.append(str(entry_date))
    if pay_method:
        sql += " AND pay_method=:2"; params.append(pay_method)
    sql += " ORDER BY entry_date DESC, id DESC"
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@revenue_router.get("/monthly")
async def revenue_monthly(
    year: str = Query(default=str(date.today().year)),
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT TO_CHAR(entry_date,'MM') as month_num,
                  COUNT(*) as entries,
                  SUM(gross_total) as gross,
                  SUM(discount) as discounts,
                  SUM(net_total) as net,
                  SUM(CASE WHEN pay_method='Cash' THEN net_total ELSE 0 END) as cash,
                  SUM(CASE WHEN pay_method='UPI' THEN net_total ELSE 0 END) as upi,
                  SUM(CASE WHEN pay_method='Card' THEN net_total ELSE 0 END) as card
           FROM daily_entries
           WHERE TO_CHAR(entry_date,'YYYY')=:1
           GROUP BY TO_CHAR(entry_date,'MM')
           ORDER BY month_num""",
        [year]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@revenue_router.get("/pending-dues")
async def pending_dues(
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, job_no, booking_type, client_name, phone, wedding_date,
                  pkg_amount, advance_paid, balance_due, status
           FROM bridal_bookings WHERE balance_due > 0 AND status='Active'
           ORDER BY wedding_date"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ════════════════════════════════
# REPORTS (Admin only)
# ════════════════════════════════
reports_router = APIRouter(prefix="/reports", tags=["reports"])


@reports_router.get("/summary")
async def reports_summary(
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    month_str = date.today().strftime("%Y-%m")
    year_str = date.today().strftime("%Y")

    async def sc(sql, p=None):
        await cursor.execute(sql, p or [])
        r = await cursor.fetchone()
        return r[0] if r else 0

    daily_month = await sc("SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1", [month_str])
    bridal_advance_month = await sc(
        """SELECT COALESCE(SUM(advance_paid),0) FROM bridal_bookings
           WHERE TO_CHAR(updated_at,'YYYY-MM')=:1""", [month_str]
    )
    daily_year = await sc("SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY')=:1", [year_str])
    bridal_advance_year = await sc(
        """SELECT COALESCE(SUM(advance_paid),0) FROM bridal_bookings
           WHERE TO_CHAR(updated_at,'YYYY')=:1""", [year_str]
    )
    return {
        "monthly_revenue": daily_month,
        "bridal_advance_month": bridal_advance_month,
        "total_profit_month": daily_month + bridal_advance_month,
        "yearly_revenue": daily_year,
        "bridal_advance_year": bridal_advance_year,
        "total_profit_year": daily_year + bridal_advance_year,
        "total_clients": await sc("SELECT COUNT(*) FROM clients"),
        "bridal_bookings": await sc("SELECT COUNT(*) FROM bridal_bookings"),
        "staff_count": await sc("SELECT COUNT(*) FROM staff WHERE is_active=1"),
        "total_entries": await sc("SELECT COUNT(*) FROM daily_entries"),
    }


@reports_router.get("/service-revenue")
async def service_revenue(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT ei.service_name,
                    COUNT(*) as count,
                    SUM(ei.line_total) as revenue
             FROM entry_items ei
             JOIN daily_entries de ON de.id = ei.entry_id
             WHERE 1=1"""
    params = []
    if from_date:
        sql += " AND de.entry_date >= TO_DATE(:1,'YYYY-MM-DD')"; params.append(str(from_date))
    if to_date:
        sql += " AND de.entry_date <= TO_DATE(:2,'YYYY-MM-DD')"; params.append(str(to_date))
    sql += " GROUP BY ei.service_name ORDER BY revenue DESC"
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@reports_router.get("/staff-performance")
async def staff_performance(
    month: Optional[str] = Query(None, description="YYYY-MM, defaults to current month"),
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    from datetime import date as _date
    if month:
        yr, mo = month.split('-')
        month_start = f"{yr}-{mo}-01"
    else:
        today = _date.today()
        month_start = today.strftime('%Y-%m-01')
        month = today.strftime('%Y-%m')
    yr_i, mo_i = int(month_start[:4]), int(month_start[5:7])
    import calendar
    days_in_month = calendar.monthrange(yr_i, mo_i)[1]
    month_end = f"{yr_i}-{mo_i:02d}-{days_in_month:02d}"

    await cursor.execute(
        """SELECT s.id, s.name, s.role, s.base_salary,
                  COUNT(DISTINCT CASE WHEN a.is_present=1 THEN a.att_date END) as present_days,
                  NVL(SUM(CASE WHEN a.half_day=1 THEN 1 ELSE 0 END), 0) as half_day_count,
                  NVL(SUM(CASE WHEN a.morning_duty=1 THEN 1 ELSE 0 END), 0) as morning_duty_count,
                  NVL((SELECT COUNT(*) FROM entry_items ei
                       JOIN daily_entries de ON de.id=ei.entry_id
                       WHERE ei.staff_id=s.id
                         AND de.entry_date >= TO_DATE(:1,'YYYY-MM-DD')
                         AND de.entry_date <= TO_DATE(:2,'YYYY-MM-DD')
                  ), 0) AS services_count,
                  NVL((SELECT SUM(ei.line_total) FROM entry_items ei
                       JOIN daily_entries de ON de.id=ei.entry_id
                       WHERE ei.staff_id=s.id
                         AND de.entry_date >= TO_DATE(:3,'YYYY-MM-DD')
                         AND de.entry_date <= TO_DATE(:4,'YYYY-MM-DD')
                  ), 0) AS monthly_revenue
           FROM staff s
           LEFT JOIN attendance a ON a.staff_id=s.id
             AND a.att_date >= TO_DATE(:5,'YYYY-MM-DD')
             AND a.att_date <= TO_DATE(:6,'YYYY-MM-DD')
           WHERE s.is_active=1
           GROUP BY s.id, s.name, s.role, s.base_salary
           ORDER BY monthly_revenue DESC""",
        [month_start, month_end, month_start, month_end, month_start, month_end]
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    result = [dict(zip(cols, r)) for r in rows]
    for r in result:
        r['month'] = month
        r['days_in_month'] = days_in_month
    return result


# ════════════════════════════════
# SALARY
# ════════════════════════════════
salary_router = APIRouter(prefix="/salary", tags=["salary"])


@salary_router.post("/pay")
async def record_salary_payment(
    data: SalaryPaymentCreate,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """INSERT INTO salary_payments (staff_id, pay_month, base_amount, commission, total_paid, notes, created_by)
           VALUES (:1,:2,:3,:4,:5,:6,:7)""",
        [data.staff_id, data.pay_month, data.base_amount, data.commission,
         data.total_paid, data.notes, int(current_user["id"])]
    )
    await cursor.execute(
        "UPDATE staff SET paid_salary=paid_salary+:1 WHERE id=:2",
        [data.total_paid, data.staff_id]
    )
    await db.commit()
    return {"message": "Salary recorded", "staff_id": data.staff_id, "amount": data.total_paid}


# ════════════════════════════════
# SERVICES CATALOG
# ════════════════════════════════
svc_router = APIRouter(prefix="/services", tags=["services"])


@svc_router.get("")
async def list_services(
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = "SELECT id, category, name, base_price, sort_order FROM service_catalog WHERE is_active=1"
    params = []
    if category:
        sql += " AND category=:1"; params.append(category)
    sql += " ORDER BY category, sort_order"
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ════════════════════════════════════════════════
# INQUIRY ROUTER
# ════════════════════════════════════════════════

inquiry_router = APIRouter(prefix="/inquiries", tags=["inquiries"])

@inquiry_router.get("")
async def list_inquiries(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    sql = """SELECT id, name, phone, service, event_date, budget, source,
                    status, notes, created_at
             FROM inquiries WHERE 1=1"""
    params = []
    if search:
        sql += " AND (LOWER(name) LIKE :1 OR phone LIKE :2)"
        params += [f"%{search.lower()}%", f"%{search}%"]
    if status:
        sql += f" AND status=:{len(params)+1}"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]

@inquiry_router.post("")
async def create_inquiry(
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """INSERT INTO inquiries (name, phone, service, event_date, budget, source, status, notes)
           VALUES (:1, :2, :3, TO_DATE(:4,'YYYY-MM-DD'), :5, :6, :7, :8)""",
        [data.get('name'), data.get('phone'), data.get('service'),
         data.get('date') or None, data.get('budget') or 0,
         data.get('source','Walk-in'), data.get('status','New'), data.get('notes')]
    )
    await db.commit()
    return {"created": True}

@inquiry_router.put("/{inquiry_id}")
async def update_inquiry(
    inquiry_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    fields, values = [], []
    allowed = ['name','phone','service','budget','source','status','notes']
    for k, v2 in data.items():
        if k in allowed:
            fields.append(f"{k}=:{len(values)+1}")
            values.append(v2)
    if data.get('date'):
        fields.append(f"event_date=TO_DATE(:{len(values)+1},'YYYY-MM-DD')")
        values.append(data['date'])
    if not fields:
        return {"error": "No valid fields"}
    values.append(inquiry_id)
    await cursor.execute(
        f"UPDATE inquiries SET {','.join(fields)},updated_at=SYSTIMESTAMP WHERE id=:{len(values)}",
        values
    )
    await db.commit()
    return {"updated": inquiry_id}

@inquiry_router.delete("/{inquiry_id}")
async def delete_inquiry(
    inquiry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute("DELETE FROM inquiries WHERE id=:1", [inquiry_id])
    await db.commit()
    return {"deleted": inquiry_id}