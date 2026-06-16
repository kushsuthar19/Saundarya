"""
WhatsApp messaging service.
Supports: UltraMsg (recommended), CallMeBot, Meta Cloud API.

Setup guide:
-----------
UltraMsg (easiest, paid):
  1. Sign up at https://ultramsg.com
  2. Create an instance, scan QR code with your WhatsApp
  3. Set WA_PROVIDER=ultramsg, WA_INSTANCE_ID=<your_id>, WA_TOKEN=<your_token>
  4. WA_API_URL=https://api.ultramsg.com

CallMeBot (free, limited):
  1. Add +34 644 97 44 69 on WhatsApp
  2. Send: "I allow callmebot to send me messages"
  3. You get an API key
  4. Set WA_PROVIDER=callmebot, WA_TOKEN=<api_key>

Meta Cloud API (official, requires business verification):
  1. https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
  2. Set WA_PROVIDER=meta, WA_TOKEN=<bearer_token>, WA_INSTANCE_ID=<phone_number_id>
"""
import httpx
import logging
from typing import Optional
from backend.core.config import settings

logger = logging.getLogger(__name__)


def _format_phone(phone: str) -> str:
    """Normalize phone number to international format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "+91" + phone[1:]
    elif not phone.startswith("+"):
        phone = "+91" + phone
    return phone


async def send_whatsapp_message(phone: str, message: str) -> dict:
    """Send a WhatsApp text message. Returns {'success': bool, 'error': str|None}."""
    if not settings.WA_TOKEN or not settings.WA_API_URL:
        return {"success": False, "error": "WhatsApp not configured. Set WA_TOKEN and WA_API_URL in .env"}

    phone = _format_phone(phone)
    provider = settings.WA_PROVIDER.lower()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "ultramsg":
                resp = await client.post(
                    f"{settings.WA_API_URL}/{settings.WA_INSTANCE_ID}/messages/chat",
                    data={"token": settings.WA_TOKEN, "to": phone, "body": message},
                )
                data = resp.json()
                success = data.get("sent") == "true" or resp.status_code == 200
                return {"success": success, "error": None if success else data.get("error")}

            elif provider == "callmebot":
                import urllib.parse
                encoded = urllib.parse.quote(message)
                url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={settings.WA_TOKEN}"
                resp = await client.get(url)
                success = resp.status_code == 200
                return {"success": success, "error": None if success else resp.text[:200]}

            elif provider == "meta":
                # Meta Cloud API
                url = f"https://graph.facebook.com/v18.0/{settings.WA_INSTANCE_ID}/messages"
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone.replace("+", ""),
                    "type": "text",
                    "text": {"body": message},
                }
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.WA_TOKEN}"},
                )
                success = resp.status_code == 200
                return {"success": success, "error": None if success else resp.text[:200]}

            else:
                return {"success": False, "error": f"Unknown WA provider: {provider}"}

    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return {"success": False, "error": str(e)}


def build_daily_invoice_message(entry: dict, items: list) -> str:
    """Build WhatsApp invoice message for daily entry."""
    lines = [
        "🌸 *Saundarya Beauty Care*",
        "📍 Waghodiya Road, Vadodara",
        "📞 96621 35422 / 9723044589",
        "",
        "✨ *INVOICE*",
        "━━━━━━━━━━━━━━━━━━",
        f"🧾 *{entry.get('inv_no', '')}*  |  📅 {entry.get('entry_date', '')}",
        f"👤 *{entry.get('client_name', '')}*",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "💆 *Services:*",
    ]
    for item in items:
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        total = price * qty
        qty_str = f" ×{qty}" if qty > 1 else ""
        lines.append(f"• {item.get('service_name', '')}{qty_str} — ₹{int(total):,}")

    gross = entry.get("gross_total", 0)
    discount = entry.get("discount", 0)
    net = entry.get("net_total", 0)
    method = entry.get("pay_method", "Cash")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 Gross: ₹{int(gross):,}",
    ]
    if discount > 0:
        lines.append(f"🎁 Discount: — ₹{int(discount):,}")
    lines += [
        f"✅ *Net Paid: ₹{int(net):,}*",
        f"💳 Payment: {method}",
    ]
    if entry.get("next_visit"):
        lines.append(f"📅 Next Visit: {entry['next_visit']}")
    if entry.get("remarks"):
        lines.append(f"📝 Note: {entry['remarks']}")
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "",
        "💐 Thank you for choosing Saundarya!",
        "_Book again: 96621 35422_",
    ]
    return "\n".join(lines)


def build_bridal_invoice_message(booking: dict) -> str:
    """Build WhatsApp confirmation message for bridal booking."""
    w_date = booking.get("wedding_date", "")
    pkg_amt = booking.get("pkg_amount", 0)
    advance = booking.get("advance_paid", 0)
    balance = booking.get("balance_due", 0)

    lines = [
        "💍 *Saundarya Beauty Care*",
        "📍 Waghodiya Road, Vadodara",
        "📞 96621 35422 / 9723044589",
        "",
        "✨ *BRIDAL BOOKING CONFIRMATION*",
        "━━━━━━━━━━━━━━━━━━",
        f"📋 Job No.: *{booking.get('job_no', '')}*",
        f"👰 Client: *{booking.get('client_name', '')}*",
        f"💍 Wedding: {w_date}",
        f"📦 Package: {booking.get('package_name', '')}",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 Total: ₹{int(pkg_amt):,}",
        f"✅ Advance Paid: ₹{int(advance):,}",
        f"⏳ *Balance Due: ₹{int(balance):,}*",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "💐 Thank you for choosing Saundarya for your special day!",
    ]
    return "\n".join(lines)
