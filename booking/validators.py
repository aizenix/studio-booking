import re

LOCAL_COUNTRY_CODE = "998"
_PHONE_RE = re.compile(r"^\+\d{10,15}$")


def normalize_phone(value):
    """Return the phone in +998901234567 form, or None if it does not look like a phone."""
    phone = re.sub(r"[\s\-()]", "", value or "")
    if phone.isdigit() and len(phone) == 9:
        # Local Uzbek format without the country code: 90 123 45 67
        phone = LOCAL_COUNTRY_CODE + phone
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone if _PHONE_RE.match(phone) else None
