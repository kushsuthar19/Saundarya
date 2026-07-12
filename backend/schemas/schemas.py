"""
Pydantic v2 schemas for request validation and response serialization.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, EmailStr, ConfigDict
import re


# ── Auth ──────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def sanitize_username(cls, v: str) -> str:
        # Only alphanumeric, underscore, dot
        if not re.match(r"^[a-zA-Z0-9_.]+$", v):
            raise ValueError("Invalid username format")
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must have at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must have at least one digit")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("Password must have at least one special character")
        return v


# ── Client ────────────────────────────────────────────────
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    birthday: Optional[date] = None
    skin_type: Optional[str] = "Normal"
    hair_type: Optional[str] = "Normal"
    tag: Optional[str] = "Regular"
    preferences: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = "Manual"


class ClientUpdate(ClientCreate):
    name: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    birthday: Optional[date]
    skin_type: Optional[str]
    hair_type: Optional[str]
    tag: Optional[str]
    preferences: Optional[str]
    visits: int
    total_spent: float
    source: Optional[str]
    created_at: Optional[datetime]


# ── Staff ─────────────────────────────────────────────────
class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    join_date: Optional[date] = None
    base_salary: float = 0
    commission_pct: float = Field(10, ge=0, le=100)
    av_class: Optional[str] = "a0"
    # Optional linked user account
    username: Optional[str] = None
    password: Optional[str] = None


class StaffOut(BaseModel):
    id: int
    name: str
    role: Optional[str]
    phone: Optional[str]
    join_date: Optional[date]
    base_salary: float
    commission_pct: float
    days_present: int
    total_services: int
    comm_earned: float
    paid_salary: float
    av_class: Optional[str]
    is_active: int
    half_day_count: int = 0
    morning_duty_count: int = 0
    monthly_revenue: float = 0
    monthly_days_present: int = 0
    monthly_services: int = 0


# ── Attendance ────────────────────────────────────────────
class AttendanceUpsert(BaseModel):
    staff_id: int
    att_date: date
    is_present: bool
    half_day: bool = False
    morning_duty: bool = False   # Extra ₹150 for morning duty
    in_time: Optional[str] = None
    out_time: Optional[str] = None


class AttendanceOut(BaseModel):
    id: int
    staff_id: int
    att_date: date
    is_present: bool
    half_day: bool = False
    morning_duty: bool = False   # Extra ₹150 for morning duty
    in_time: Optional[str]
    out_time: Optional[str]
    hours_worked: Optional[float]


# ── Appointment ───────────────────────────────────────────
class AppointmentCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    service: Optional[str] = Field(None, max_length=200)
    appt_date: Optional[date] = None
    appt_time: Optional[str] = None
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None
    advance: float = 0
    status: str = "Confirmed"
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("appt_date", mode="before")
    @classmethod
    def coerce_appt_date(cls, v):
        if v == "" or v is None:
            return None
        return v

    @field_validator("phone", "service", "appt_time", "staff_name", "notes", mode="before")
    @classmethod
    def coerce_appt_str(cls, v):
        return None if v == "" else v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        allowed = {"Confirmed", "Pending", "Completed", "Cancelled"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v


class AppointmentOut(BaseModel):
    id: int
    client_name: str
    phone: Optional[str]
    service: Optional[str]
    appt_date: Optional[date]
    appt_time: Optional[str]
    staff_id: Optional[int]
    staff_name: Optional[str]
    advance: float
    status: str
    notes: Optional[str]
    created_at: Optional[datetime]


# ── Entry Items ───────────────────────────────────────────
class EntryItem(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(0, ge=0)
    qty: int = Field(1, ge=1)
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None

    @field_validator("staff_name", mode="before")
    @classmethod
    def coerce_staff(cls, v):
        return None if v == "" else v


# ── Daily Entry ───────────────────────────────────────────
class DailyEntryCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    entry_date: date
    visit_type: str = "Walk-in"
    items: List[EntryItem] = Field(..., min_length=1)
    discount: float = Field(0, ge=0)
    pay_method: str = "Cash"
    next_visit: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=500)

    @field_validator("next_visit", mode="before")
    @classmethod
    def coerce_next_visit(cls, v):
        if v == "" or v is None:
            return None
        return v

    @field_validator("phone", "remarks", mode="before")
    @classmethod
    def coerce_optional_str(cls, v):
        return None if v == "" else v

    @field_validator("pay_method")
    @classmethod
    def valid_method(cls, v: str) -> str:
        allowed = {"Cash", "UPI", "Card", "Split"}
        if v not in allowed:
            raise ValueError(f"Pay method must be one of {allowed}")
        return v


class EntryItemOut(BaseModel):
    id: int
    service_name: str
    price: float
    qty: int
    staff_id: Optional[int]
    staff_name: Optional[str]
    line_total: float


class DailyEntryOut(BaseModel):
    id: int
    inv_no: str
    client_id: Optional[int]
    client_name: str
    phone: Optional[str]
    entry_date: date
    visit_type: str
    services: Optional[str]
    gross_total: float
    discount: float
    net_total: float
    pay_method: str
    next_visit: Optional[date]
    remarks: Optional[str]
    wa_sent: int
    items: List[EntryItemOut] = []
    created_at: Optional[datetime]


# ── Bridal ────────────────────────────────────────────────
class BridalFunction(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    function_name: Optional[str] = None
    fn_date: Optional[date] = None
    fn_time: Optional[str] = None
    person_count: Optional[int] = None   # NUMBER in Oracle
    pkg_detail: Optional[str] = None
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None

    @field_validator("fn_date", mode="before")
    @classmethod
    def coerce_date(cls, v):
        if v == "" or v is None:
            return None
        return v

    @field_validator("fn_time", "pkg_detail", "artist_name", mode="before")
    @classmethod
    def coerce_str(cls, v):
        return None if v == "" else v

    @field_validator("person_count", mode="before")
    @classmethod
    def coerce_person_count(cls, v):
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class BridalCreate(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    booking_type: str = "Bride"
    client_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    wedding_date: Optional[date] = None
    venue: Optional[str] = Field(None, max_length=200)
    reference: Optional[str] = Field(None, max_length=200)
    package_name: Optional[str] = Field(None, max_length=200)
    pkg_amount: float = 0
    transport: float = 0
    discount: float = 0
    advance_paid: float = 0
    notes: Optional[str] = Field(None, max_length=1000)
    functions: List[BridalFunction] = []

    @field_validator("wedding_date", mode="before")
    @classmethod
    def coerce_wedding_date(cls, v):
        if v == "" or v is None:
            return None
        return v

    @field_validator("venue", "reference", "package_name", "notes", "phone", mode="before")
    @classmethod
    def coerce_str_fields(cls, v):
        if v == "" or v is None:
            return None
        # Truncate phone if too long
        return v

    @field_validator("booking_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in {"Bride", "Groom", "Sider"}:
            raise ValueError("Type must be Bride, Groom, or Sider")
        return v


class BridalFunctionOut(BaseModel):
    id: int
    function_name: Optional[str]
    fn_date: Optional[date]
    fn_time: Optional[str]
    person_count: Optional[int]   # NUMBER in Oracle
    pkg_detail: Optional[str]
    artist_name: Optional[str]


class BridalOut(BaseModel):
    id: int
    job_no: str
    booking_type: str
    client_name: str
    phone: Optional[str]
    wedding_date: Optional[date]
    venue: Optional[str]
    reference: Optional[str]
    package_name: Optional[str]
    pkg_amount: float
    transport: float
    discount: float
    advance_paid: float
    balance_due: float
    status: str
    wa_sent: int
    functions: List[BridalFunctionOut] = []
    created_at: Optional[datetime]


# ── Revenue / Reports ─────────────────────────────────────
class RevenueStats(BaseModel):
    today: float
    this_month: float
    this_year: float
    cash_month: float
    upi_month: float
    card_month: float
    pending_dues: float
    advance_paid_total: float = 0   # total advance collected from bridal
    bridal_total_value: float = 0   # total value of active bridal bookings


class DashboardStats(BaseModel):
    today_revenue: float
    today_appointments: int
    today_walkins: int
    active_bridal: int
    staff_present: int
    staff_total: int
    today_entries: int


# ── WhatsApp ──────────────────────────────────────────────
class WASendRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    type: Literal["invoice", "bridal"]
    ref_id: int


# ── Service Catalog ───────────────────────────────────────
class ServiceCatalogOut(BaseModel):
    id: int
    category: str
    name: str
    base_price: float
    sort_order: int


# ── Salary ────────────────────────────────────────────────
class SalaryPaymentCreate(BaseModel):
    staff_id: int
    pay_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    base_amount: float = 0
    commission: float = 0
    total_paid: float = 0
    notes: Optional[str] = None


# ── Config ────────────────────────────────────────────────
class ConfigUpdate(BaseModel):
    config_key: str
    config_value: str


# ── User management ───────────────────────────────────────
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = "staff"

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in {"admin", "staff"}:
            raise ValueError("Role must be admin or staff")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: str
    role: str
    is_active: int
    last_login: Optional[datetime]