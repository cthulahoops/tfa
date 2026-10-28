"""Cases from Terence Eden's TOTP Test Suite.

https://edent.codeberg.page/TOTP_Test_Suite/

The URIs are built exactly as the suite's page builds them. We deliberately
differ from the suite in two places: missing digits, period or algorithm take
the Key Uri Format defaults, and a lower-case algorithm is accepted because
some issuers send one.
"""

import base64
import hashlib
import hmac
import json
import struct

import pytest
import qrcode
from click.testing import CliRunner

from tfa.cli import cli, make_totp
from tfa.otpauth import parse_uri

LABEL = "issuer%3Aaccount%20name"


def query(**changes):
    values = {"digits": "6", "issuer": "issuer", "algorithm": "SHA1", "period": "30"}
    values.update(changes)
    return "&".join(f"{k}={v}" for k, v in values.items() if v is not None)


def uri(label=LABEL, secret="QWERTYUIOP", query_string=query(), scheme="otpauth"):
    return f"{scheme}://totp/{label}?secret={secret}&{query_string}"


REJECTED = {
    "0 digits": uri(query_string=query(digits="0")),
    "11 digits": uri(query_string=query(digits="11")),
    "1,000 digits": uri(query_string=query(digits="1000")),
    "negative period": uri(query_string=query(period="-1")),
    "zero period": uri(query_string=query(period="0")),
    "SHA384": uri(query_string=query(algorithm="SHA384")),
    "SHA-1": uri(query_string=query(algorithm="SHA-1")),
    "invalid secret": uri(
        "test%40example.com", "QWERT!£$%^)*(YUIOP", query(issuer="example.org")
    ),
    "empty secret": uri("test%40example.com", "", query(issuer="example.org")),
    "missing secret": (
        "otpauth://totp/test%40example.com?"
        "&digits=6&issuer=example.org&algorithm=SHA1&period=30"
    ),
}

# name: (uri, expected digits, period, algorithm)
ACCEPTED = {
    **{
        f"{d} digits": (uri(query_string=query(digits=str(d))), d, 30, "SHA1")
        for d in range(1, 11)
    },
    "missing digits": (uri(query_string=query(digits=None)), 6, 30, "SHA1"),
    **{
        f"{p}s period": (uri(query_string=query(period=str(p))), 6, p, "SHA1")
        for p in (3, 15, 30, 60, 1000)
    },
    "missing period": (uri(query_string=query(period=None)), 6, 30, "SHA1"),
    **{
        alg: (uri(query_string=query(algorithm=alg)), 6, 30, alg)
        for alg in ("SHA1", "SHA256", "SHA512")
    },
    "missing algorithm": (uri(query_string=query(algorithm=None)), 6, 30, "SHA1"),
    "lower-case algorithm": (uri(query_string=query(algorithm="sha1")), 6, 30, "SHA1"),
    "secret with padding": (uri(secret="QWERTYUIOP======"), 6, 30, "SHA1"),
    "lower-case secret": (uri(secret="qwertyuiop"), 6, 30, "SHA1"),
    "extremely long secret": (uri(secret="QWERTYUIOP" * 22), 6, 30, "SHA1"),
}

# name: (uri, expected issuer, expected account)
LABELS = {
    "no issuer in label": (
        uri("test%40example.com", query_string=query(issuer="")),
        None,
        "test@example.com",
    ),
    "separate issuer": (
        uri("test%40example.com", query_string=query(issuer="example.org")),
        "example.org",
        "test@example.com",
    ),
    "empty label": (uri("", query_string=query(issuer="")), None, None),
    "non-ASCII account": (
        uri("%E8%8E%8E%E5%A3%AB%E6%AF%94%E4%BA%9A", query_string=query(issuer="")),
        None,
        "莎士比亚",
    ),
    "non-ASCII account not encoded": (
        uri("莎士比亚", query_string=query(issuer="")),
        None,
        "莎士比亚",
    ),
    "emoji label not encoded": (
        uri("🏴‍☠️:🏳️‍🌈", query_string=query(issuer="")),
        "🏴‍☠️",
        "🏳️‍🌈",
    ),
    "extra colon in label": (
        uri("Matrix:@edent_:matrix.org", query_string=query(issuer="")),
        "Matrix",
        "@edent_:matrix.org",
    ),
    "extra spaces in label": (
        uri(
            "Spaces:" + "%20" * 12 + "test%40example.com", query_string=query(issuer="")
        ),
        "Spaces",
        "test@example.com",
    ),
    "issuer mismatch": (
        uri("example.com%3Aaccount%20name", query_string=query(issuer="microsoft.com")),
        "microsoft.com",
        "account name",
    ),
    "empty issuer": (
        uri("example.com%3Aaccount%20name", query_string=query(issuer="")),
        "example.com",
        "account name",
    ),
    "missing issuer": (
        uri(
            "example.com%3Aaccount%20name",
            query_string=query(issuer=None),
        ),
        "example.com",
        "account name",
    ),
    "apple-otpauth scheme": (
        uri(
            "Example%20Website%3Atest%40example.com",
            query_string=query(issuer=""),
            scheme="apple-otpauth",
        ),
        "Example Website",
        "test@example.com",
    ),
}


def parse_and_check(text):
    """Parse a URI and check we can generate codes from it, as `tfa add` does."""
    account, issuer = parse_uri(text)
    make_totp(account).now()
    return account, issuer


def reference_totp(secret, digits, period, algorithm, for_time):
    """RFC 6238, independently of pyotp."""
    secret = secret.upper().rstrip("=")
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = struct.pack(">Q", int(for_time // period))
    digest = hmac.new(key, counter, getattr(hashlib, algorithm.lower())).digest()
    offset = digest[-1] & 0xF
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % 10**digits).zfill(digits)


@pytest.mark.parametrize("text", REJECTED.values(), ids=REJECTED.keys())
def test_rejected(text):
    with pytest.raises(ValueError):
        parse_and_check(text)


@pytest.mark.parametrize(
    "text, digits, period, algorithm", ACCEPTED.values(), ids=ACCEPTED.keys()
)
def test_accepted_with_correct_codes(text, digits, period, algorithm):
    account, _ = parse_and_check(text)

    assert (account["digits"], account["period"]) == (digits, period)
    assert account["algorithm"] == algorithm
    for for_time in (0, 1_111_111_109, 2_000_000_000):
        assert make_totp(account).at(for_time) == reference_totp(
            account["key"], digits, period, algorithm, for_time
        )


@pytest.mark.parametrize("text, issuer, account", LABELS.values(), ids=LABELS.keys())
def test_labels(text, issuer, account):
    parsed, parsed_issuer = parse_and_check(text)

    assert parsed_issuer == issuer
    assert parsed["account"] == account


def test_reference_totp_matches_rfc_6238():
    # Appendix B test vector for SHA1.
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert reference_totp(secret, 8, 30, "SHA1", 59) == "94287082"


def test_empty_parameters_take_defaults():
    account, issuer = parse_uri(
        "otpauth://totp/Ex:me?secret=JBSWY3DPEHPK3PXP"
        "&digits=&period=&algorithm=&issuer=%20"
    )

    assert (account["digits"], account["period"], account["algorithm"]) == (
        6,
        30,
        "SHA1",
    )
    assert issuer == "Ex"


def test_rejects_hotp():
    with pytest.raises(ValueError, match="only TOTP"):
        parse_uri("otpauth://hotp/a?secret=JBSWY3DPEHPK3PXP&counter=0")


def test_rejects_non_integer_digits():
    with pytest.raises(ValueError, match="digits must be an integer"):
        parse_uri(uri(query_string=query(digits="six")))


@pytest.mark.parametrize("name", ["4 digits", "10 digits"], ids=str)
def test_add_from_qr_with_unusual_digits(name):
    text, digits, _, _ = ACCEPTED[name]
    runner = CliRunner()
    with runner.isolated_filesystem():
        qrcode.make(text).save("qr.png")

        result = runner.invoke(cli, ["add", "x", "--qr", "qr.png"])

        assert result.exit_code == 0, result.output
        assert len(result.output.strip()) == digits


@pytest.mark.parametrize("name", ["issuer mismatch", "apple-otpauth scheme"])
def test_add_from_qr_label_cases(name):
    text, issuer, account = LABELS[name]
    runner = CliRunner()
    with runner.isolated_filesystem():
        qrcode.make(text).save("qr.png")

        result = runner.invoke(cli, ["add", "x", "--qr", "qr.png"])

        assert result.exit_code == 0, result.output
        stored = json.loads(runner.invoke(cli, ["export"]).output)["x"]
        assert (stored["issuer"], stored["account"]) == (issuer, account)
