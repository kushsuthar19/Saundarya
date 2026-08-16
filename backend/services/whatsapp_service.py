"""
WhatsApp messaging service.
Supports: UltraMsg, CallMeBot, Meta Cloud API, AiSensy.

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

AiSensy (official WhatsApp Business Solution Provider):
  1. In the AiSensy dashboard: Manage -> API Key -> copy it.
  2. AiSensy only sends via a pre-approved WhatsApp template ("Campaign") —
     it can't send arbitrary free text like the other providers. Create one
     API Campaign whose template body is a single variable, e.g. just
     "{{1}}" (Manage -> Campaigns -> create an API Campaign, get it
     WhatsApp-approved). This app then fills that {{1}} with the whole
     invoice message it already builds, so no other template setup is
     needed. Note the exact Campaign name.
  3. Set WA_PROVIDER=aisensy, WA_TOKEN=<api_key>, WA_CAMPAIGN_NAME=<campaign_name>
     (WA_API_URL / WA_INSTANCE_ID are not used for this provider — the
     endpoint is fixed.)
"""
import httpx
import logging
from typing import Optional
from backend.core.config import settings

logger = logging.getLogger(__name__)

AISENSY_URL = "https://backend.aisensy.com/campaign/t1/api/v2"


def _format_phone(phone: str) -> str:
    """Normalize phone number to international format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "+91" + phone[1:]
    elif not phone.startswith("+"):
        phone = "+91" + phone
    return phone


def _wa_not_configured(provider: str) -> Optional[dict]:
    """Returns an error dict if the configured provider is missing what it
    needs, else None. AiSensy's endpoint is fixed (no WA_API_URL) but needs
    a Campaign name instead — everyone else needs WA_API_URL."""
    if provider == "aisensy":
        if not settings.WA_TOKEN or not settings.WA_CAMPAIGN_NAME:
            return {"success": False, "error": "WhatsApp not configured. Set WA_TOKEN and WA_CAMPAIGN_NAME in .env"}
    elif not settings.WA_TOKEN or not settings.WA_API_URL:
        return {"success": False, "error": "WhatsApp not configured. Set WA_TOKEN and WA_API_URL in .env"}
    return None


def _aisensy_result(resp) -> dict:
    """AiSensy's docs only document HTTP 200 == success and don't specify a
    failure JSON shape, so treat any non-200 as a failure, and a 200 body
    that explicitly says success:false as one too."""
    try:
        data = resp.json()
    except Exception:
        data = {}
    success = resp.status_code == 200 and str(data.get("success", True)).lower() != "false"
    error = None if success else (data.get("message") or data.get("error") or resp.text[:200])
    return {"success": success, "error": error}


async def send_whatsapp_message(phone: str, message: str, user_name: str = "") -> dict:
    """Send a WhatsApp text message. Returns {'success': bool, 'error': str|None}."""
    provider = settings.WA_PROVIDER.lower()
    not_configured = _wa_not_configured(provider)
    if not_configured:
        return not_configured

    phone = _format_phone(phone)

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

            elif provider == "aisensy":
                # AiSensy only sends pre-approved WhatsApp templates, not free
                # text — WA_CAMPAIGN_NAME must point at a Campaign whose
                # template body is a single "{{1}}" variable, which we fill
                # with the whole message this app already composed.
                resp = await client.post(AISENSY_URL, json={
                    "apiKey": settings.WA_TOKEN,
                    "campaignName": settings.WA_CAMPAIGN_NAME,
                    "destination": phone,
                    "userName": user_name or "Customer",
                    "templateParams": [message],
                })
                return _aisensy_result(resp)

            else:
                return {"success": False, "error": f"Unknown WA provider: {provider}"}

    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return {"success": False, "error": str(e)}


async def send_whatsapp_document(phone: str, document_url: str, filename: str, caption: str = "", user_name: str = "") -> dict:
    """Send an actual file (e.g. an invoice PDF) as a WhatsApp document message
    — not just a link. document_url must be a publicly reachable URL; the WA
    provider fetches it server-side and attaches it as a real file in the chat.
    Returns {'success': bool, 'error': str|None}."""
    provider = settings.WA_PROVIDER.lower()
    not_configured = _wa_not_configured(provider)
    if not_configured:
        return not_configured

    phone = _format_phone(phone)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if provider == "ultramsg":
                resp = await client.post(
                    f"{settings.WA_API_URL}/{settings.WA_INSTANCE_ID}/messages/document",
                    data={
                        "token": settings.WA_TOKEN, "to": phone,
                        "document": document_url, "filename": filename, "caption": caption,
                    },
                )
                data = resp.json()
                success = data.get("sent") == "true" or resp.status_code == 200
                return {"success": success, "error": None if success else data.get("error")}

            elif provider == "meta":
                url = f"https://graph.facebook.com/v18.0/{settings.WA_INSTANCE_ID}/messages"
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone.replace("+", ""),
                    "type": "document",
                    "document": {"link": document_url, "filename": filename, "caption": caption},
                }
                resp = await client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {settings.WA_TOKEN}"},
                )
                success = resp.status_code == 200
                return {"success": success, "error": None if success else resp.text[:200]}

            elif provider == "aisensy":
                # Same fixed-template Campaign as send_whatsapp_message, plus
                # a media attachment — the AiSensy media URL must be publicly
                # reachable (it already is: apiDownload/public PDF links).
                resp = await client.post(AISENSY_URL, json={
                    "apiKey": settings.WA_TOKEN,
                    "campaignName": settings.WA_CAMPAIGN_NAME,
                    "destination": phone,
                    "userName": user_name or "Customer",
                    "media": {"url": document_url, "filename": filename},
                    "templateParams": [caption or filename],
                })
                return _aisensy_result(resp)

            else:
                return {"success": False, "error": f"{provider} doesn't support sending files, only text messages"}

    except Exception as e:
        logger.error(f"WhatsApp document send error: {e}")
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
    addons = [fn for fn in (booking.get("functions") or []) if fn.get("addon_amount")]

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
    ]
    for fn in addons:
        item = fn.get("addon_item") or "Add-on"
        lines.append(f"➕ {item} ({fn.get('function_name', '')}): ₹{int(fn['addon_amount']):,}")
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        f"💰 Total: ₹{int(pkg_amt):,}",
        f"✅ Advance Paid: ₹{int(advance):,}",
        f"⏳ *Balance Due: ₹{int(balance):,}*",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "💐 Thank you for choosing Saundarya for your special day!",
    ]
    return "\n".join(lines)
