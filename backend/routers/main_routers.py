"""
Appointments, Staff, Attendance, Bridal Bookings, Revenue, Reports routers.
"""
import hashlib
import hmac
import logging
import os
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
import oracledb

from backend.core.config import settings
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
from backend.services.whatsapp_service import send_whatsapp_message, build_bridal_invoice_message, send_whatsapp_template
from backend.core.security import hash_password

logger = logging.getLogger(__name__)


def _bridal_pdf_token(booking_id: int) -> str:
    """Deterministic, unguessable token for sharing a booking's invoice PDF
    without requiring the recipient to log in — derived from SECRET_KEY so
    it can't be forged, and needs no DB storage since it's recomputed."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"bridal-pdf-{booking_id}".encode(),
        hashlib.sha256
    ).hexdigest()[:24]

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
                  ), 0) AS monthly_revenue,
                  NVL((SELECT COUNT(*)
                       FROM entry_items ei
                       JOIN daily_entries de ON de.id=ei.entry_id
                       WHERE ei.staff_id=s.id
                         AND de.entry_date >= TO_DATE(:3,'YYYY-MM-DD')
                         AND de.entry_date <= TO_DATE(:4,'YYYY-MM-DD')
                  ), 0) AS monthly_services
           FROM staff s
           LEFT JOIN attendance a ON a.staff_id=s.id
             AND a.att_date >= TO_DATE(:5,'YYYY-MM-DD')
             AND a.att_date <= TO_DATE(:6,'YYYY-MM-DD')
           WHERE s.is_active=1
           GROUP BY s.id, s.name, s.role, s.phone, s.join_date, s.base_salary, s.commission_pct,
                    s.days_present, s.total_services, s.comm_earned, s.paid_salary, s.av_class, s.is_active
           ORDER BY s.name""",
        [month_start, month_end, month_start, month_end, month_start, month_end]
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
           commission_pct, av_class, device_user_id)
           VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),:6,:7,:8,:9)
           RETURNING id INTO :10""",
        [user_id, data.name, data.role, data.phone, jd,
         data.base_salary, data.commission_pct, data.av_class, data.device_user_id,
         cursor.var(oracledb.NUMBER)]
    )
    new_id = int(cursor.bindvars[-1].getvalue()[0])
    await db.commit()
    await cursor.execute(
        "SELECT id,name,role,phone,join_date,base_salary,commission_pct,days_present,total_services,comm_earned,paid_salary,av_class,is_active,device_user_id FROM staff WHERE id=:1",
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
    # Policy: the first 2 absent-day-equivalents each month are paid
    # holidays (no deduction). Two half-days combine into one full
    # absent-day-equivalent (e.g. half + half = 1 day). Only the
    # equivalent days beyond the free allowance are deducted, at the
    # per-day rate.
    FREE_HOLIDAYS_PER_MONTH = 2
    per_day = (staff_info['base_salary'] or 0) / days_in_month if days_in_month else 0
    dp = present_count
    if dp >= half_day_count:
        effective_days = dp - (half_day_count * 0.5)
    else:
        effective_days = dp + (half_day_count * 0.5)
    full_absent_days = max(0, days_in_month - dp)
    absent_equivalent_days = full_absent_days + (half_day_count * 0.5)
    chargeable_absent_days = max(0, absent_equivalent_days - FREE_HOLIDAYS_PER_MONTH)
    absence_deduction = chargeable_absent_days * per_day
    base_earned = round((staff_info['base_salary'] or 0) - absence_deduction)
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
            "full_absent_days": full_absent_days,
            "absent_equivalent_days": absent_equivalent_days,
            "free_holidays": FREE_HOLIDAYS_PER_MONTH,
            "chargeable_absent_days": chargeable_absent_days,
            "absence_deduction": round(absence_deduction),
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
                  days_present, total_services, comm_earned, paid_salary, av_class, is_active,
                  device_user_id
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
    allowed = ['name','role','phone','join_date','base_salary','commission_pct','device_user_id']
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


async def _credit_beauty_points(cursor, client_id, inv_no, amount: float):
    """Bridal advance/due payments are real revenue too, so Exclusive members
    should earn beauty points on them exactly like a regular Daily Entry bill
    (₹100 = 1 point). This mirrors the points logic in entries.py's
    create_entry() — that one only runs for the Daily Entry form, so bridal
    payments (mirrored into daily_entries via raw SQL here, not via POST
    /entries) were silently never earning points, split-paid or not."""
    if not client_id or not amount:
        return
    pts_to_add = int(float(amount) // 100)
    if pts_to_add <= 0:
        return
    try:
        await cursor.execute(
            """INSERT INTO beauty_points_log
               (membership_id, entry_type, points, notes)
               SELECT id, 'Earned', :1, 'Service: '||:2
               FROM memberships WHERE client_id=:3 AND status='Active'""",
            [pts_to_add, str(inv_no), client_id]
        )
        await cursor.execute(
            """SELECT m.id,
                   NVL(SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END),0),
                   NVL(SUM(CASE WHEN l.entry_type!='redeem' THEN l.points ELSE 0 END),0)
               FROM memberships m
               LEFT JOIN beauty_points_log l ON l.membership_id=m.id
               WHERE m.client_id=:1 AND m.status='Active'
               GROUP BY m.id""",
            [client_id]
        )
        sync_row = await cursor.fetchone()
        if sync_row:
            await cursor.execute(
                "UPDATE memberships SET beauty_points=:1, lifetime_points=:2 WHERE id=:3",
                [max(0, int(sync_row[1] or 0)), int(sync_row[2] or 0), sync_row[0]]
            )
    except Exception:
        pass  # non-member or table not ready — don't fail the payment over this


async def _reverse_beauty_points(cursor, client_id, inv_no):
    """Undo what _credit_beauty_points() did for this inv_no — used when the
    bridal booking/payment it was earned from gets deleted, so the client
    isn't left holding points for a payment that no longer exists."""
    if not client_id:
        return
    try:
        await cursor.execute(
            """DELETE FROM beauty_points_log
               WHERE notes=:1
                 AND membership_id IN (SELECT id FROM memberships WHERE client_id=:2)""",
            ['Service: ' + str(inv_no), client_id]
        )
        await cursor.execute(
            """SELECT m.id,
                   NVL(SUM(CASE WHEN l.entry_type='redeem' THEN -l.points ELSE l.points END),0),
                   NVL(SUM(CASE WHEN l.entry_type!='redeem' THEN l.points ELSE 0 END),0)
               FROM memberships m
               LEFT JOIN beauty_points_log l ON l.membership_id=m.id
               WHERE m.client_id=:1 AND m.status='Active'
               GROUP BY m.id""",
            [client_id]
        )
        sync_row = await cursor.fetchone()
        if sync_row:
            await cursor.execute(
                "UPDATE memberships SET beauty_points=:1, lifetime_points=:2 WHERE id=:3",
                [max(0, int(sync_row[1] or 0)), int(sync_row[2] or 0), sync_row[0]]
            )
    except Exception:
        pass  # non-member or table not ready — don't fail the delete over this


async def _get_bridal(booking_id: int, cursor) -> dict:
    try:
        await cursor.execute(
            """SELECT id, job_no, booking_type, client_name, phone, booking_date, wedding_date,
                      venue, reference, package_name, pkg_amount, transport, discount,
                      advance_paid, balance_due, status, wa_sent, created_at
               FROM bridal_bookings WHERE id=:1""",
            [booking_id]
        )
    except oracledb.DatabaseError:
        # booking_date column not migrated yet on this DB — fall back gracefully
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
    booking.setdefault("booking_date", None)
    try:
        await cursor.execute(
            """SELECT id, function_name, fn_date, fn_time, person_count, person_name,
                      pkg_detail, artist_name, addon_item, addon_amount
               FROM bridal_functions WHERE booking_id=:1 ORDER BY id""",
            [booking_id]
        )
    except oracledb.DatabaseError:
        try:
            # addon_item/addon_amount not migrated yet on this DB — fall back gracefully
            await cursor.execute(
                """SELECT id, function_name, fn_date, fn_time, person_count, person_name,
                          pkg_detail, artist_name
                   FROM bridal_functions WHERE booking_id=:1 ORDER BY id""",
                [booking_id]
            )
        except oracledb.DatabaseError:
            # person_name column not migrated yet either — fall back further
            await cursor.execute(
                """SELECT id, function_name, fn_date, fn_time, person_count, pkg_detail, artist_name
                   FROM bridal_functions WHERE booking_id=:1 ORDER BY id""",
                [booking_id]
            )
    fn_rows = await cursor.fetchall()
    fn_cols = [d[0].lower() for d in cursor.description]
    booking["functions"] = [dict(zip(fn_cols, r)) for r in fn_rows]
    for f in booking["functions"]:
        f.setdefault("person_name", None)
    booking["payments"] = []
    try:
        await cursor.execute(
            """SELECT id, payment_type, amount, pay_method,
                      TO_CHAR(payment_date,'YYYY-MM-DD') as payment_date, notes
               FROM bridal_payments WHERE booking_id=:1 ORDER BY payment_date, id""",
            [booking_id]
        )
        pay_rows = await cursor.fetchall()
        pay_cols = [d[0].lower() for d in cursor.description]
        booking["payments"] = [dict(zip(pay_cols, r)) for r in pay_rows]
    except Exception:
        pass  # bridal_payments table not migrated yet — degrade gracefully
    booking["pdf_token"] = _bridal_pdf_token(booking_id)
    return booking


async def _recalc_bridal_balance(cursor, booking_id: int) -> float:
    """Recompute and persist a booking's balance_due from its current
    pkg_amount/transport/discount/advance_paid plus the live sum of its
    functions' addon_amount — used after editing or deleting a single
    Add-on Service row, since that changes what's owed without touching
    any of the other top-level booking fields."""
    await cursor.execute(
        "SELECT pkg_amount, transport, discount, advance_paid FROM bridal_bookings WHERE id=:1",
        [booking_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Bridal booking not found")
    pkg, transport, discount, advance = [float(x or 0) for x in row]
    addon_total = 0.0
    try:
        await cursor.execute(
            "SELECT NVL(SUM(addon_amount),0) FROM bridal_functions WHERE booking_id=:1",
            [booking_id]
        )
        addon_row = await cursor.fetchone()
        addon_total = float(addon_row[0] or 0) if addon_row else 0.0
    except oracledb.DatabaseError:
        pass  # addon_amount column not migrated yet on this DB — treat as 0
    balance = max(0, pkg + transport + addon_total - discount - advance)
    await cursor.execute(
        "UPDATE bridal_bookings SET balance_due=:1, updated_at=SYSTIMESTAMP WHERE id=:2",
        [balance, booking_id]
    )
    return balance


@bridal_router.patch("/{booking_id}/functions/{function_id}")
async def edit_bridal_function(
    booking_id: int,
    function_id: int,
    data: dict,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Edit a single function/add-on row in place — e.g. renaming a sider
    (Mom/Sister) or changing their function/date/item/amount — without
    touching the rest of the booking or replacing the whole schedule."""
    cursor = db.cursor()
    await cursor.execute(
        "SELECT id FROM bridal_functions WHERE id=:1 AND booking_id=:2",
        [function_id, booking_id]
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Function/add-on row not found on this booking")

    allowed = ['function_name', 'fn_date', 'fn_time', 'person_count', 'person_name',
               'pkg_detail', 'addon_item', 'addon_amount']
    fields, values = [], []
    for k, v2 in data.items():
        if k not in allowed:
            continue
        if k == 'fn_date' and v2:
            fields.append(f"fn_date=TO_DATE(:{len(values)+1},'YYYY-MM-DD')")
        else:
            fields.append(f"{k}=:{len(values)+1}")
        values.append(v2)
    if fields:
        values.append(function_id)
        try:
            await cursor.execute(
                f"UPDATE bridal_functions SET {','.join(fields)} WHERE id=:{len(values)}",
                values
            )
        except oracledb.DatabaseError as e:
            raise HTTPException(status_code=500, detail=f"Failed to update: {str(e)}")

    balance = await _recalc_bridal_balance(cursor, booking_id)
    await db.commit()
    return {"updated": function_id, "balance_due": balance}


@bridal_router.delete("/{booking_id}/functions/{function_id}")
async def delete_bridal_function(
    booking_id: int,
    function_id: int,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Remove a single function/add-on row (e.g. drop a sider like Mom or
    Sister) without touching the rest of the booking, then re-total the
    balance_due since that add-on's amount no longer applies."""
    cursor = db.cursor()
    await cursor.execute(
        "DELETE FROM bridal_functions WHERE id=:1 AND booking_id=:2",
        [function_id, booking_id]
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Function/add-on row not found on this booking")
    balance = await _recalc_bridal_balance(cursor, booking_id)
    await db.commit()
    return {"deleted": function_id, "balance_due": balance}


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
    # Add-on packages (e.g. a Sider makeup package tacked onto a specific
    # function like Sangeet, on top of the main package) count toward what's
    # owed just like transport/discount do.
    addon_total = sum(float(fn.addon_amount or 0) for fn in data.functions)
    balance = max(0, data.pkg_amount + data.transport + addon_total - data.discount - data.advance_paid)
    wd = str(data.wedding_date) if data.wedding_date else None
    bd = str(data.booking_date) if data.booking_date else date.today().strftime('%Y-%m-%d')

    try:
        await cursor.execute(
            """INSERT INTO bridal_bookings
               (job_no, booking_type, client_name, phone, booking_date, wedding_date, venue,
                reference, package_name, pkg_amount, transport, discount, advance_paid,
                balance_due, notes, created_by)
               VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),TO_DATE(:6,'YYYY-MM-DD'),:7,:8,:9,
                       :10,:11,:12,:13,:14,:15,:16)
               RETURNING id INTO :17""",
            [job_no, data.booking_type, data.client_name, data.phone, bd, wd,
             data.venue, data.reference, data.package_name,
             data.pkg_amount, data.transport, data.discount, data.advance_paid,
             balance, data.notes, int(current_user["id"]),
             cursor.var(oracledb.NUMBER)]
        )
    except oracledb.DatabaseError:
        # booking_date column not migrated yet on this DB — fall back gracefully
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
        try:
            await cursor.execute(
                """INSERT INTO bridal_functions
                   (booking_id, function_name, fn_date, fn_time, person_count, person_name,
                    pkg_detail, artist_id, artist_name, addon_item, addon_amount)
                   VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8,:9,:10,:11)""",
                [new_id, fn.function_name, fnd, fn.fn_time or None,
                 fn.person_count or None, fn.person_name or None, fn.pkg_detail or None,
                 fn.artist_id, fn.artist_name or None, fn.addon_item or None, fn.addon_amount or 0]
            )
        except oracledb.DatabaseError:
            try:
                # addon_item/addon_amount not migrated yet on this DB — fall back gracefully
                await cursor.execute(
                    """INSERT INTO bridal_functions
                       (booking_id, function_name, fn_date, fn_time, person_count, person_name,
                        pkg_detail, artist_id, artist_name)
                       VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8,:9)""",
                    [new_id, fn.function_name, fnd, fn.fn_time or None,
                     fn.person_count or None, fn.person_name or None, fn.pkg_detail or None,
                     fn.artist_id, fn.artist_name or None]
                )
            except oracledb.DatabaseError:
                # person_name column not migrated yet either — fall back further
                await cursor.execute(
                    """INSERT INTO bridal_functions
                       (booking_id, function_name, fn_date, fn_time, person_count, pkg_detail, artist_id, artist_name)
                       VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8)""",
                    [new_id, fn.function_name, fnd, fn.fn_time or None,
                     fn.person_count or None, fn.pkg_detail or None,
                     fn.artist_id, fn.artist_name or None]
                )

    await db.commit()

    # Auto-create Daily Entry for advance payment if advance > 0
    if data.advance_paid and float(data.advance_paid) > 0:
        try:
            from datetime import date as _date
            import oracledb as _oracledb
            # Use booking_date if provided, else today
            booking_dt = data.booking_date
            entry_date_str = booking_dt.strftime('%Y-%m-%d') if booking_dt else _date.today().strftime('%Y-%m-%d')
            btype = data.booking_type or 'Bride'
            client_label = f"{data.client_name} (Bridal Advance - {btype})"
            adv_inv = f"BR-ADV-{new_id}"
            pay_m = data.advance_pay_method or 'Cash'

            # Get or create client — match on last 10 digits so phone
            # formatting differences don't fragment this into a duplicate client.
            cl_id = None
            if data.phone:
                await cursor.execute(
                    """SELECT id FROM clients WHERE SUBSTR(REGEXP_REPLACE(phone,'[^0-9]',''),-10) =
                                                     SUBSTR(REGEXP_REPLACE(:1,'[^0-9]',''),-10)""",
                    [data.phone]
                )
                cl_row = await cursor.fetchone()
                if cl_row:
                    cl_id = cl_row[0]
            if not cl_id:
                await cursor.execute(
                    """INSERT INTO clients (name,phone,source,client_type,visit_count,total_spent)
                       VALUES (:1,:2,'Bridal','New',0,0) RETURNING id INTO :3""",
                    [data.client_name, data.phone, cursor.var(_oracledb.NUMBER)]
                )
                cl_id = int(cursor.bindvars[-1].getvalue()[0])

            adv_amount = float(data.advance_paid)
            await cursor.execute(
                """INSERT INTO daily_entries
                   (inv_no,client_id,client_name,phone,entry_date,visit_type,
                    services,gross_total,discount,net_total,pay_method,remarks,created_by)
                   VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),'Bridal Advance',
                           :6,:7,0,:8,:9,:10,:11)
                   RETURNING id INTO :12""",
                [adv_inv, cl_id, client_label, data.phone, entry_date_str,
                 f"Bridal Advance - {btype} (Job: {new_id})",
                 adv_amount, adv_amount, pay_m,
                 f"Bridal advance for booking #{new_id}",
                 int(current_user["id"]),
                 cursor.var(_oracledb.NUMBER)]
            )
            await db.commit()
            await _credit_beauty_points(cursor, cl_id, adv_inv, adv_amount)
            await db.commit()

            # Log this as the booking's "Advance" payment so the invoice can
            # show exactly when the advance was paid.
            try:
                await cursor.execute(
                    """INSERT INTO bridal_payments
                           (booking_id, payment_type, amount, pay_method, payment_date, notes, created_by)
                       VALUES (:1,'Advance',:2,:3,TO_DATE(:4,'YYYY-MM-DD'),'Advance paid at booking',:5)""",
                    [new_id, adv_amount, pay_m, entry_date_str, int(current_user["id"])]
                )
                await db.commit()
            except Exception:
                pass  # bridal_payments table not migrated yet — degrade gracefully
        except Exception as _e:
            pass  # Don't fail bridal save if daily entry fails

    # ── WhatsApp: auto-send booking confirmation ────────────────────────
    # One template per booking_type — never more than one of the three
    # fires for a given booking. Best-effort: any failure here is logged
    # and swallowed, never allowed to fail the save that already succeeded.
    if data.phone:
        try:
            template_key = {
                "Bride": "bridal_bride", "Groom": "bridal_groom", "Sider": "bridal_sider",
            }.get(data.booking_type)
            if template_key:
                event_dates = ", ".join(sorted({
                    str(fn.fn_date) for fn in data.functions if fn.fn_date
                })) or (wd or "")
                total_bill = data.pkg_amount + data.transport + addon_total - data.discount
                await send_whatsapp_template(
                    db, data.phone, template_key,
                    [data.client_name, event_dates, f"₹{int(total_bill):,}", f"₹{int(data.advance_paid):,}"],
                    ref_id=new_id, user_name=data.client_name,
                )
        except Exception as wa_err:
            logger.error(f"Bridal auto WhatsApp send failed (non-fatal): {wa_err}")

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


@bridal_router.get("/{booking_id}/functions/{function_id}/pdf")
async def bridal_sider_addon_pdf(
    booking_id: int,
    function_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Standalone one-off PDF for a single sider person added as an Add-on
    Service inside a Bride/Groom booking (e.g. the bride's Mom or Sister) —
    downloadable on its own from the Sider tab, without needing the whole
    parent booking's invoice."""
    from backend.services.pdf_service import generate_sider_addon_invoice
    cursor = db.cursor()
    booking = await _get_bridal(booking_id, cursor)
    fn = next((f for f in booking["functions"] if f.get("id") == function_id), None)
    if not fn:
        raise HTTPException(status_code=404, detail="Function/add-on row not found on this booking")
    pdf_bytes = generate_sider_addon_invoice(booking, fn)
    person = (fn.get("person_name") or "Guest").replace(" ", "_")
    filename = f"Sider_{person}_{booking['job_no']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@bridal_router.get("/{booking_id}/pdf/public")
async def bridal_invoice_pdf_public(
    booking_id: int,
    token: str = Query(...),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Unauthenticated invoice download for sharing via WhatsApp/SMS —
    only works with the correct signed token for this exact booking."""
    if token != _bridal_pdf_token(booking_id):
        raise HTTPException(status_code=403, detail="Invalid or expired link")
    cursor = db.cursor()
    booking = await _get_bridal(booking_id, cursor)
    if booking.get("booking_type") == "Sider":
        pdf_bytes = generate_sider_invoice(booking, booking["functions"])
    else:
        pdf_bytes = generate_bridal_invoice(booking, booking["functions"])
    filename = f"Invoice_{booking['job_no']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
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
    result = await send_whatsapp_message(booking["phone"], message, user_name=booking.get("client_name", ""))
    if result["success"]:
        await cursor.execute(
            "UPDATE bridal_bookings SET wa_sent=1 WHERE id=:1", [booking_id]
        )
        await db.commit()
    return result


@bridal_router.post("/{booking_id}/whatsapp/pdf")
async def bridal_whatsapp_pdf(
    booking_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Send the actual invoice PDF as a WhatsApp document — not a link.

    Was calling send_whatsapp_document(), which only checks/uses a generic
    WA_CAMPAIGN_NAME env var that's never been set — a different, older
    config path than the per-purpose AISENSY_CAMPAIGN_BRIDAL_* templates
    actually configured. Now uses send_whatsapp_template() (same one Daily
    Entry's equivalent /whatsapp/pdf endpoint uses) with the dedicated
    "_with_invoice" document-type templates — separate from the plain-text
    confirmation ones, since a template must be specifically approved with
    a File/Document header to carry a PDF attachment.
    """
    cursor = db.cursor()
    booking = await _get_bridal(booking_id, cursor)
    if not booking.get("phone"):
        raise HTTPException(400, "No phone number")
    template_key = {
        "Bride": "bridal_bride_with_invoice",
        "Groom": "bridal_groom_with_invoice",
        "Sider": "bridal_sider_with_invoice",
    }.get(booking.get("booking_type"))
    if not template_key:
        raise HTTPException(400, f"Unknown booking type: {booking.get('booking_type')}")
    functions = booking.get("functions") or []
    event_dates = ", ".join(sorted({
        str(fn.get("fn_date")) for fn in functions if fn.get("fn_date")
    })) or str(booking.get("wedding_date") or "")
    addon_total = sum(float(fn.get("addon_amount") or 0) for fn in functions)
    total_bill = float(booking.get("pkg_amount") or 0) + float(booking.get("transport") or 0) \
        + addon_total - float(booking.get("discount") or 0)
    # A cache-busting query param (ignored by the endpoint itself, which
    # only checks `token`) so WhatsApp/AiSensy's media cache treats every
    # send as a brand-new file — without it, the URL is identical on every
    # send for this booking, so after editing the booking (new dates,
    # add-ons, amounts) a re-send here kept delivering the stale PDF that
    # was cached from the very first send.
    from datetime import datetime as _dt
    doc_url = (f"{str(request.base_url).rstrip('/')}/api/v1/bridal/{booking_id}/pdf/public"
               f"?token={_bridal_pdf_token(booking_id)}&v={int(_dt.now().timestamp())}")
    result = await send_whatsapp_template(
        db, booking["phone"], template_key,
        [booking.get("client_name", ""), event_dates, f"₹{int(total_bill):,}", f"₹{int(booking.get('advance_paid') or 0):,}"],
        media_url=doc_url, media_filename=f"Invoice_{booking['job_no']}.pdf",
        ref_id=booking_id, user_name=booking.get("client_name", ""),
    )
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
    # Fetch current values first so we can tell if the advance amount is
    # being increased by this edit (vs. just re-saving the same number).
    prev_booking_date = None
    try:
        await cursor.execute(
            "SELECT client_name, phone, advance_paid, booking_type, booking_date FROM bridal_bookings WHERE id=:1",
            [booking_id]
        )
        prev_row = await cursor.fetchone()
        if not prev_row:
            raise HTTPException(404, "Bridal booking not found")
        prev_client_name, prev_phone, prev_advance, prev_type, prev_booking_date = prev_row
    except oracledb.DatabaseError:
        # booking_date column not migrated yet on this DB — fall back gracefully
        await cursor.execute(
            "SELECT client_name, phone, advance_paid, booking_type FROM bridal_bookings WHERE id=:1",
            [booking_id]
        )
        prev_row = await cursor.fetchone()
        if not prev_row:
            raise HTTPException(404, "Bridal booking not found")
        prev_client_name, prev_phone, prev_advance, prev_type = prev_row
    prev_advance = float(prev_advance or 0)

    allowed = ['client_name','phone','booking_date','wedding_date','venue','reference',
               'package_name','pkg_amount','transport','discount',
               'advance_paid','status','notes']

    def _build_fields(include_booking_date: bool):
        fields, values = [], []
        for k, v2 in data.items():
            if k == 'booking_date' and not include_booking_date:
                continue
            if k in allowed:
                if k in ('wedding_date', 'booking_date') and v2:
                    fields.append(f"{k}=TO_DATE(:{len(values)+1},'YYYY-MM-DD')")
                else:
                    fields.append(f"{k}=:{len(values)+1}")
                values.append(v2)
        return fields, values

    fields, values = _build_fields(True)
    if not fields and 'functions' not in data:
        return {"error": "No valid fields"}

    # Replace the Function Schedule + Add-ons if a "functions" list was
    # submitted — full edit support (previously only the top-level booking
    # fields like name/amount/dates could be changed after creation, never
    # the per-function schedule or add-ons).
    if isinstance(data.get('functions'), list):
        await cursor.execute("DELETE FROM bridal_functions WHERE booking_id=:1", [booking_id])
        for fn in data['functions']:
            fname = (fn.get('function_name') or '').strip()
            if not fname:
                continue
            fnd = fn.get('fn_date') or None
            try:
                await cursor.execute(
                    """INSERT INTO bridal_functions
                       (booking_id, function_name, fn_date, fn_time, person_count, person_name,
                        pkg_detail, artist_id, artist_name, addon_item, addon_amount)
                       VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8,:9,:10,:11)""",
                    [booking_id, fname, fnd, fn.get('fn_time') or None,
                     fn.get('person_count') or None, fn.get('person_name') or None,
                     fn.get('pkg_detail') or None, fn.get('artist_id') or None,
                     fn.get('artist_name') or None, fn.get('addon_item') or None,
                     fn.get('addon_amount') or 0]
                )
            except oracledb.DatabaseError:
                try:
                    # addon_item/addon_amount not migrated yet on this DB — fall back gracefully
                    await cursor.execute(
                        """INSERT INTO bridal_functions
                           (booking_id, function_name, fn_date, fn_time, person_count, person_name,
                            pkg_detail, artist_id, artist_name)
                           VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8,:9)""",
                        [booking_id, fname, fnd, fn.get('fn_time') or None,
                         fn.get('person_count') or None, fn.get('person_name') or None,
                         fn.get('pkg_detail') or None, fn.get('artist_id') or None,
                         fn.get('artist_name') or None]
                    )
                except oracledb.DatabaseError:
                    # person_name column not migrated yet either — fall back further
                    await cursor.execute(
                        """INSERT INTO bridal_functions
                           (booking_id, function_name, fn_date, fn_time, person_count, pkg_detail, artist_id, artist_name)
                           VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8)""",
                        [booking_id, fname, fnd, fn.get('fn_time') or None,
                         fn.get('person_count') or None, fn.get('pkg_detail') or None,
                         fn.get('artist_id') or None, fn.get('artist_name') or None]
                    )
        await db.commit()

    if not fields:
        return {"updated": True}

    # Recalculate balance_due — must include add-on amounts the same way
    # create_bridal does, or every edit to a booking that has add-ons
    # (even something unrelated like fixing a phone number) silently drops
    # them from the balance.
    pkg = data.get('pkg_amount', 0) or 0
    tr = data.get('transport', 0) or 0
    disc = data.get('discount', 0) or 0
    adv = data.get('advance_paid', 0) or 0
    addon_total = 0.0
    try:
        await cursor.execute(
            "SELECT NVL(SUM(addon_amount),0) FROM bridal_functions WHERE booking_id=:1",
            [booking_id]
        )
        addon_row = await cursor.fetchone()
        addon_total = float(addon_row[0] or 0) if addon_row else 0.0
    except oracledb.DatabaseError:
        pass  # addon_amount column not migrated yet on this DB — treat as 0
    balance = max(0, float(pkg) + float(tr) + addon_total - float(disc) - float(adv))
    fields.append(f"balance_due=:{len(values)+1}")
    values.append(balance)
    fields.append(f"updated_at=SYSTIMESTAMP")
    values.append(booking_id)
    try:
        await cursor.execute(
            f"UPDATE bridal_bookings SET {','.join(fields)} WHERE id=:{len(values)}",
            values
        )
    except oracledb.DatabaseError:
        # booking_date column not migrated yet on this DB — retry without it
        fields, values = _build_fields(False)
        fields.append(f"balance_due=:{len(values)+1}")
        values.append(balance)
        fields.append(f"updated_at=SYSTIMESTAMP")
        values.append(booking_id)
        await cursor.execute(
            f"UPDATE bridal_bookings SET {','.join(fields)} WHERE id=:{len(values)}",
            values
        )
    await db.commit()

    # If the Booking Date itself was changed, move every advance Daily Entry
    # tied to this booking — the original one from creation (inv_no
    # "BR-ADV-{id}") AND any later "advance increased" adjustment entries
    # (inv_no "BR-ADJ-*") both tag their services column with "(Job: {id})",
    # so match on that instead of one specific inv_no pattern.
    new_bkd = data.get('booking_date')
    prev_bkd_str = str(prev_booking_date)[:10] if prev_booking_date else None
    if new_bkd and new_bkd != prev_bkd_str:
        try:
            await cursor.execute(
                """UPDATE daily_entries SET entry_date=TO_DATE(:1,'YYYY-MM-DD')
                   WHERE visit_type='Bridal Advance' AND services LIKE :2""",
                [new_bkd, f"%(Job: {booking_id})%"]
            )
            await db.commit()
        except Exception:
            pass  # No advance entry exists yet (e.g. booking had ₹0 advance) — nothing to move
        try:
            await cursor.execute(
                """UPDATE bridal_payments SET payment_date=TO_DATE(:1,'YYYY-MM-DD')
                   WHERE booking_id=:2 AND payment_type='Advance'""",
                [new_bkd, booking_id]
            )
            await db.commit()
        except Exception:
            pass  # bridal_payments table not migrated yet — degrade gracefully

    # If this edit raised the advance amount, log the increase as revenue —
    # same as when a booking is first created — so it actually shows up in
    # Daily Entries/reports instead of silently vanishing. (A decrease is
    # treated as a data correction, not a refund, so it isn't reversed here.)
    # The adjustment entry is dated to this booking's Booking Date (the date
    # the advance was actually paid), not today, and function/event dates
    # are never touched by this.
    new_advance = float(adv or 0)
    if new_advance > prev_advance:
        delta = new_advance - prev_advance
        try:
            client_name = data.get('client_name') or prev_client_name
            phone = data.get('phone', prev_phone)
            entry_bkd = data.get('booking_date') or (str(prev_booking_date)[:10] if prev_booking_date else None)
            entry_date_str = entry_bkd or date.today().strftime('%Y-%m-%d')
            btype = prev_type or 'Bride'

            cl_id = None
            if phone:
                await cursor.execute(
                    """SELECT id FROM clients WHERE SUBSTR(REGEXP_REPLACE(phone,'[^0-9]',''),-10) =
                                                     SUBSTR(REGEXP_REPLACE(:1,'[^0-9]',''),-10)""",
                    [phone]
                )
                cl_row = await cursor.fetchone()
                if cl_row:
                    cl_id = cl_row[0]
            if not cl_id and client_name:
                await cursor.execute(
                    """INSERT INTO clients (name,phone,source,client_type,visit_count,total_spent)
                       VALUES (:1,:2,'Bridal','New',0,0) RETURNING id INTO :3""",
                    [client_name, phone, cursor.var(oracledb.NUMBER)]
                )
                cl_id = int(cursor.bindvars[-1].getvalue()[0])

            await cursor.execute("SELECT seq_inv.NEXTVAL FROM DUAL")
            inv_row = await cursor.fetchone()
            adv_inv = f"BR-ADJ-{inv_row[0]}"

            await cursor.execute(
                """INSERT INTO daily_entries
                   (inv_no,client_id,client_name,phone,entry_date,visit_type,
                    services,gross_total,discount,net_total,pay_method,remarks,created_by)
                   VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),'Bridal Advance',
                           :6,:7,0,:8,:9,:10,:11)""",
                [adv_inv, cl_id, f"{client_name} (Bridal Advance - {btype})", phone, entry_date_str,
                 f"Bridal Advance adjustment (Job: {booking_id})",
                 delta, delta, 'Cash',
                 f"Advance increased on edit for booking #{booking_id}",
                 int(current_user["id"])]
            )
            await db.commit()
            await _credit_beauty_points(cursor, cl_id, adv_inv, delta)
            await db.commit()

            try:
                await cursor.execute(
                    """INSERT INTO bridal_payments
                           (booking_id, payment_type, amount, pay_method, payment_date, notes, created_by)
                       VALUES (:1,'Advance',:2,'Cash',TO_DATE(:3,'YYYY-MM-DD'),'Advance updated via booking edit',:4)""",
                    [booking_id, delta, entry_date_str, int(current_user["id"])]
                )
                await db.commit()
            except Exception:
                pass  # bridal_payments table not migrated yet — degrade gracefully
        except Exception:
            pass  # Don't fail the booking edit if the revenue log fails

    return {"updated": booking_id, "balance_due": balance}

@bridal_router.delete("/{booking_id}")
async def delete_bridal(
    booking_id: int,
    current_user: dict = Depends(require_admin),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    try:
        # Clean up the Daily Entry row(s) this booking generated — the
        # initial advance (inv_no 'BR-ADV-<id>') and any later due payments
        # (matched by their exact remarks text) — since they're only linked
        # by text, not a real foreign key, and would otherwise keep showing
        # in Daily Entry / revenue reports / the client's Service History
        # forever after the booking itself is gone.
        await cursor.execute(
            """SELECT id, client_id, inv_no FROM daily_entries
               WHERE inv_no=:1 OR remarks=:2""",
            [f"BR-ADV-{booking_id}", f"Bridal due payment for booking #{booking_id}"]
        )
        linked_entries = await cursor.fetchall()
        for entry_id, client_id, inv_no in linked_entries:
            await _reverse_beauty_points(cursor, client_id, inv_no)
            await cursor.execute("DELETE FROM entry_items WHERE entry_id=:1", [entry_id])
            await cursor.execute("DELETE FROM daily_entries WHERE id=:1", [entry_id])
        await db.commit()

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
    pay_method: str = "Cash",
    entry_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Record an advance/due payment. Reduces balance_due, increases advance_paid,
    and mirrors it into daily_entries so it's counted in revenue reports
    (Today's Revenue, payment split, etc.) the same way the initial advance is."""
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    cursor = db.cursor()
    # Get current booking
    await cursor.execute(
        """SELECT advance_paid, balance_due, pkg_amount, transport, discount,
                  client_name, phone, booking_type
           FROM bridal_bookings WHERE id=:1""",
        [booking_id]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Booking not found")
    (advance_paid, balance_due, pkg_amount, transport, discount,
     client_name, phone, booking_type) = row
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

    # Mirror into daily_entries so this due payment shows up in daily/monthly
    # revenue reports, not just on the bridal booking itself.
    try:
        edate = entry_date or date.today().strftime('%Y-%m-%d')
        cl_id = None
        if phone:
            await cursor.execute(
                """SELECT id FROM clients WHERE SUBSTR(REGEXP_REPLACE(phone,'[^0-9]',''),-10) =
                                                 SUBSTR(REGEXP_REPLACE(:1,'[^0-9]',''),-10)""",
                [phone]
            )
            cl_row = await cursor.fetchone()
            if cl_row:
                cl_id = cl_row[0]
        if not cl_id:
            await cursor.execute(
                """INSERT INTO clients (name,phone,source,client_type,visit_count,total_spent)
                   VALUES (:1,:2,'Bridal','New',0,0) RETURNING id INTO :3""",
                [client_name, phone, cursor.var(oracledb.NUMBER)]
            )
            cl_id = int(cursor.bindvars[-1].getvalue()[0])
        await cursor.execute("SELECT seq_inv.NEXTVAL FROM DUAL")
        seq_row = await cursor.fetchone()
        inv_no = f"BR-DUE-{seq_row[0]}"
        await cursor.execute(
            """INSERT INTO daily_entries
               (inv_no,client_id,client_name,phone,entry_date,visit_type,
                services,gross_total,discount,net_total,pay_method,remarks,created_by)
               VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),'Bridal Due Payment',
                       :6,:7,0,:8,:9,:10,:11)""",
            [inv_no, cl_id, f"{client_name} (Bridal Due - {booking_type or 'Bride'})", phone, edate,
             f"Due payment for booking #{booking_id}", amount, amount, pay_method,
             f"Bridal due payment for booking #{booking_id}",
             int(current_user["id"])]
        )
        await db.commit()
        await _credit_beauty_points(cursor, cl_id, inv_no, amount)
        await db.commit()
    except Exception:
        pass  # Don't fail the payment record if the daily-entry mirror fails

    # Log this payment on the booking's own payment history, so the invoice
    # can show every payment date (advance + each due payment) separately.
    try:
        pay_type = "Final Payment" if new_balance == 0 else "Due Payment"
        await cursor.execute(
            """INSERT INTO bridal_payments
                   (booking_id, payment_type, amount, pay_method, payment_date, notes, created_by)
               VALUES (:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'),:6,:7)""",
            [booking_id, pay_type, amount, pay_method,
             entry_date or date.today().strftime('%Y-%m-%d'),
             f"Balance after this payment: {new_balance}",
             int(current_user["id"])]
        )
        await db.commit()
    except Exception:
        pass  # bridal_payments table not migrated yet — degrade gracefully

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

    async def scalar(sql, params=None, multi=False):
        await cursor.execute(sql, params or [])
        row = await cursor.fetchone()
        if multi:
            return row if row else []
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
    # Split-aware cash/upi/card totals
    # Handles: Cash, UPI, GPay, Card, Split|Cash:N|UPI:N|Card:N
    cash_upi_card = await scalar(
        """SELECT
            SUM(CASE
                WHEN pay_method='Cash' THEN net_total
                WHEN pay_method LIKE 'Split|%' THEN
                    CASE WHEN REGEXP_SUBSTR(pay_method,'Cash:([0-9]+)',1,1,'',1) IS NOT NULL
                         THEN TO_NUMBER(REGEXP_SUBSTR(pay_method,'Cash:([0-9]+)',1,1,'',1))
                         ELSE 0 END
                ELSE 0 END) as cash_total,
            SUM(CASE
                WHEN pay_method IN ('UPI','GPay','GPay/UPI') THEN net_total
                WHEN pay_method LIKE 'Split|%' THEN
                    CASE WHEN REGEXP_SUBSTR(pay_method,'UPI:([0-9]+)',1,1,'',1) IS NOT NULL
                         THEN TO_NUMBER(REGEXP_SUBSTR(pay_method,'UPI:([0-9]+)',1,1,'',1))
                         ELSE 0 END
                ELSE 0 END) as upi_total,
            SUM(CASE
                WHEN pay_method='Card' THEN net_total
                WHEN pay_method LIKE 'Split|%' THEN
                    CASE WHEN REGEXP_SUBSTR(pay_method,'Card:([0-9]+)',1,1,'',1) IS NOT NULL
                         THEN TO_NUMBER(REGEXP_SUBSTR(pay_method,'Card:([0-9]+)',1,1,'',1))
                         ELSE 0 END
                ELSE 0 END) as card_total
           FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY-MM')=:1""",
        [month_str], multi=True
    )
    cash = float(cash_upi_card[0] or 0) if cash_upi_card else 0
    upi = float(cash_upi_card[1] or 0) if cash_upi_card else 0
    card = float(cash_upi_card[2] or 0) if cash_upi_card else 0
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
    month: Optional[str] = Query(None, description="YYYY-MM format"),
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
    elif month:
        sql += " AND TO_CHAR(entry_date,'YYYY-MM')=:1"; params.append(month)
    if pay_method:
        sql += f" AND pay_method=:{len(params)+1}"; params.append(pay_method)
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
    # booking_date (not updated_at) is what actually represents "when the
    # advance was paid" — updated_at changes on ANY edit to the booking
    # (fixing a phone number, adding an add-on, anything), which was
    # silently re-attributing old advances to whatever month they were
    # last touched in, inflating that month/year's total.
    bridal_advance_month = await sc(
        """SELECT COALESCE(SUM(advance_paid),0) FROM bridal_bookings
           WHERE TO_CHAR(booking_date,'YYYY-MM')=:1""", [month_str]
    )
    daily_year = await sc("SELECT COALESCE(SUM(net_total),0) FROM daily_entries WHERE TO_CHAR(entry_date,'YYYY')=:1", [year_str])
    bridal_advance_year = await sc(
        """SELECT COALESCE(SUM(advance_paid),0) FROM bridal_bookings
           WHERE TO_CHAR(booking_date,'YYYY')=:1""", [year_str]
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
# MEMBERSHIP NOTIFICATIONS (Dashboard)
# ════════════════════════════════════════════════

@dash_router.get("/membership-expiry")
async def membership_expiry_alerts(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor = db.cursor()
    await cursor.execute(
        """SELECT c.name, c.phone, m.membership_id, m.status,
                  TO_CHAR(m.expiry_date,'YYYY-MM-DD') as expiry_date,
                  ROUND(m.expiry_date - SYSDATE) as days_remaining,
                  c.id as client_id, m.id as mem_id,
                  m.beauty_points
           FROM memberships m
           JOIN clients c ON c.id=m.client_id
           WHERE m.status='Active'
             AND m.expiry_date <= SYSDATE + 15
           ORDER BY m.expiry_date ASC"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


@dash_router.get("/membership-inactivity")
async def membership_inactivity_alerts(
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """
    Exclusive members must visit at least once every 2 months (60 days) or
    their membership is automatically discontinued and they revert to a
    Regular client. Warns 15 days before that deadline; auto-converts once
    the deadline has passed (checked whenever this endpoint is called).
    """
    cursor = db.cursor()

    # Auto-discontinue memberships whose last visit was 60+ days ago.
    # Uses whichever is MOST RECENT of: the client's last visit, the
    # membership's own start_date, or the membership row's updated_at.
    # Without the start_date/updated_at fallbacks, a reactivated membership
    # would still get judged by the client's old stale last_visit (which is,
    # by definition, already 60+ days old — that's why they were
    # discontinued in the first place), auto-discontinuing it again on the
    # very next check. updated_at is the extra safety net: it's always set
    # to the exact moment of reactivation regardless of what start_date was
    # actually submitted on that form (e.g. if it was mistakenly left/reset
    # to an old date), so a just-touched membership always gets a fresh
    # 60-day window either way.
    await cursor.execute(
        """SELECT m.id, c.id, c.name
           FROM memberships m
           JOIN clients c ON c.id = m.client_id
           WHERE m.status = 'Active'
             AND GREATEST(NVL(c.last_visit, m.start_date), m.start_date, m.updated_at) <= SYSDATE - 60"""
    )
    to_discontinue = await cursor.fetchall()
    discontinued = []
    for mem_id, client_id, name in to_discontinue:
        await cursor.execute(
            """UPDATE memberships SET status='Discontinued',
                   notes = NVL(notes,'') || ' [Auto-discontinued: no visit in 2 months]'
               WHERE id=:1""",
            [mem_id]
        )
        await cursor.execute(
            "UPDATE clients SET client_type='Regular' WHERE id=:1",
            [client_id]
        )
        discontinued.append({"client_id": client_id, "name": name})
    if to_discontinue:
        await db.commit()

    # Warn about still-Active members approaching the 60-day deadline. Uses
    # the same GREATEST(last_visit, start_date, updated_at) baseline as the
    # auto-discontinue check above — otherwise a just-reactivated member
    # would still show an (incorrect, already-passed) deadline computed
    # from their old stale last_visit instead of the fresh reactivation.
    await cursor.execute(
        """SELECT c.name, c.phone, m.membership_id, c.id as client_id,
                  TO_CHAR(GREATEST(NVL(c.last_visit, m.start_date), m.start_date, m.updated_at),'YYYY-MM-DD') as last_visit,
                  TO_CHAR(GREATEST(NVL(c.last_visit, m.start_date), m.start_date, m.updated_at) + 60,'YYYY-MM-DD') as visit_deadline,
                  ROUND(GREATEST(NVL(c.last_visit, m.start_date), m.start_date, m.updated_at) + 60 - SYSDATE) as days_left
           FROM memberships m
           JOIN clients c ON c.id = m.client_id
           WHERE m.status = 'Active'
             AND GREATEST(NVL(c.last_visit, m.start_date), m.start_date, m.updated_at) <= SYSDATE - 45
           ORDER BY days_left ASC"""
    )
    rows = await cursor.fetchall()
    cols = [d[0].lower() for d in cursor.description]
    warnings = [dict(zip(cols, r)) for r in rows]

    return {"discontinued": discontinued, "warnings": warnings}


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


@inquiry_router.post("/{inquiry_id}/whatsapp")
async def send_inquiry_whatsapp(
    inquiry_id: int,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Manual WhatsApp button in the Inquiry section — sends the
    inquiry_response template (name + service(s) inquired about). Real API
    send, not the wa.me hand-off the button used before. Manual-only, no
    auto-send on inquiry save, per your answer to the open question."""
    cursor = db.cursor()
    await cursor.execute("SELECT name, phone, service FROM inquiries WHERE id=:1", [inquiry_id])
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    name, phone, service = row
    if not phone:
        raise HTTPException(status_code=400, detail="No phone number for this inquiry")
    result = await send_whatsapp_template(
        db, phone, "inquiry", [name, service or "our services"],
        ref_id=inquiry_id, user_name=name,
    )
    return result


# ── Service booklet (template #9: inquiry_response_with_booklet) ───────────
# One fixed PDF, admin-uploadable/replaceable from the app — not generated
# per-record like the invoices, so no per-record signed token needed.
_BOOKLET_FILENAME = "service_booklet.pdf"


def _booklet_path() -> str:
    return os.path.join(settings.UPLOAD_DIR, _BOOKLET_FILENAME)


@inquiry_router.post("/booklet")
async def upload_service_booklet(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin),
):
    """Admin-only — uploads/replaces the service booklet PDF sent by the
    'Send Booklet' button. Whatever's uploaded here is what every future
    'Send Booklet' click sends, until replaced again."""
    if not (file.content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf")):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    contents = await file.read()
    with open(_booklet_path(), "wb") as f:
        f.write(contents)
    return {"uploaded": True, "size": len(contents)}


@inquiry_router.get("/booklet/public")
async def get_service_booklet_public():
    """Public download for AiSensy to fetch and attach as a WhatsApp
    document. No signed token like the invoice PDFs — this is the same
    fixed marketing PDF for every inquiry, not personal/financial data, so
    there's nothing per-record to protect."""
    path = _booklet_path()
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No service booklet uploaded yet")
    return FileResponse(path, media_type="application/pdf", filename=_BOOKLET_FILENAME)


@inquiry_router.post("/{inquiry_id}/whatsapp/booklet")
async def send_inquiry_booklet_whatsapp(
    inquiry_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    """Manual 'Send Booklet' button — sends the uploaded booklet as a real
    attached WhatsApp document via inquiry_response_with_booklet. Requires
    the site to be reachable over HTTPS for AiSensy to fetch the PDF;
    code-complete now, actual delivery to be confirmed once HTTPS is live."""
    if not os.path.exists(_booklet_path()):
        raise HTTPException(status_code=400, detail="No service booklet uploaded yet — upload one first")
    cursor = db.cursor()
    await cursor.execute("SELECT name, phone, service FROM inquiries WHERE id=:1", [inquiry_id])
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    name, phone, service = row
    if not phone:
        raise HTTPException(status_code=400, detail="No phone number for this inquiry")
    doc_url = f"{str(request.base_url).rstrip('/')}/api/v1/inquiries/booklet/public"
    result = await send_whatsapp_template(
        db, phone, "inquiry_pdf", [name, service or "our services"],
        media_url=doc_url, media_filename=_BOOKLET_FILENAME,
        ref_id=inquiry_id, user_name=name,
    )
    return result