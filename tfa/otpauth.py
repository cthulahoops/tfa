"""Parse otpauth:// URIs, as found in TOTP QR codes.

pyotp.parse_uri is stricter than the authenticator apps that issuers test
against: it rejects digits outside 6-8, an issuer parameter that disagrees
with the label prefix, and Apple's apple-otpauth:// scheme. We only use the
URI to fill in an account, so accept anything we can generate codes for.

See https://github.com/google/google-authenticator/wiki/Key-Uri-Format
"""

import re
from urllib.parse import parse_qsl, unquote, urlsplit

from .storage import DEFAULTS

SCHEMES = ("otpauth", "apple-otpauth")
BASE32_PATTERN = re.compile(r"[A-Z2-7]+=*")


def is_otpauth_uri(text):
    scheme, separator, _ = text.partition("://")
    return bool(separator) and scheme.lower() in SCHEMES


def parse_uri(uri):
    """Parse a TOTP otpauth:// URI and return (account, issuer).

    The account dict has the key, the account name from the label (or None),
    and digits, period and algorithm, defaulted where the URI leaves them out
    or empty. Range checks on digits and period are left to make_totp. Raises
    ValueError for anything that isn't a TOTP URI with a valid secret.
    """
    parts = urlsplit(uri)
    if parts.scheme.lower() not in SCHEMES:
        raise ValueError("not an otpauth URI")
    if parts.netloc.lower() != "totp":
        raise ValueError("only TOTP is supported")

    # The label is "issuer:account" or just "account"; the account may itself
    # contain colons.
    label = unquote(parts.path.removeprefix("/"))
    label_issuer, colon, label_account = label.partition(":")
    if not colon:
        label_issuer, label_account = "", label

    params = dict(parse_qsl(parts.query, keep_blank_values=True))

    if params.get("encoder"):
        # Steam codes use a different alphabet; plain TOTP would be wrong.
        raise ValueError(f"unsupported encoder {params['encoder']!r}")

    secret = params.get("secret", "")
    if not secret:
        raise ValueError("no secret")
    if not BASE32_PATTERN.fullmatch(secret.upper()):
        raise ValueError("secret is not valid base32")

    account = {
        "account": label_account.strip() or None,
        "key": secret,
        "digits": parse_int(params, "digits"),
        "period": parse_int(params, "period"),
        "algorithm": (params.get("algorithm") or DEFAULTS["algorithm"]).upper(),
    }
    # The issuer parameter is preferred; the label prefix is for older apps.
    issuer = params.get("issuer", "").strip() or label_issuer.strip() or None
    return account, issuer


def parse_int(params, field):
    value = params.get(field)
    if not value:
        return DEFAULTS[field]
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{field} must be an integer, not {value!r}")
