"""Ed25519 signed-token verification for MEE licensing (TASK_MEE_015).

R43: uses ``cryptography.hazmat.primitives.asymmetric.ed25519.
Ed25519PublicKey.from_public_bytes()`` for verification. If the import
fails the caller receives an ``ImportError`` — **no silent fallback**.

R44: base64url decoding uses ``base64.urlsafe_b64decode()`` with no
padding. The signed data is the **raw base64url-encoded payload string**
(the bytes of the string before the ``.``), not the decoded JSON.

Token format (verified against Keygate 0.1.15 OpenAPI spec, CTO_PLAN §1.2):
    ``<base64url-payload>.<base64url-signature>``
where the signature covers the exact bytes of the ``<base64url-payload>``
string.
"""

from __future__ import annotations

import base64
import json
import time

# R43: hard import-time dependency. Callers must handle ImportError — there
# is intentionally NO pure-Python fallback (per spec: "No silent fallback").
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
except ImportError as _exc:  # pragma: no cover - environment dependent
    raise ImportError(
        "ed25519 verification unavailable — install cryptography package"
    ) from _exc


class _TokenPayload:
    """Parsed signed-token payload (read-only projection)."""

    def __init__(self, raw: dict, token: str):
        self.raw = raw
        self.token = token
        self.lid = raw.get("lid")
        self.pid = raw.get("pid")
        self.pln = raw.get("pln")
        self.sts = raw.get("sts")
        self.did = raw.get("did")
        self.ftr = raw.get("ftr")
        self.iat = raw.get("iat")
        self.exp = raw.get("exp")
        self.vun = raw.get("vun")
        self.upd = raw.get("upd")
        self.grc = raw.get("grc")
        self.nce = raw.get("nce")

    @property
    def status(self) -> str | None:
        return self.sts

    @property
    def plan_id(self) -> str | None:
        return self.pln

    @property
    def features(self) -> dict | None:
        return self.ftr

    def is_within_ttl(self, now: float | None = None) -> bool:
        """True when ``iat + exp >= now`` — i.e. the check-in window has
        not elapsed (R4, R5, R41). ``exp`` is the check-in interval in
        seconds (server-set), not an absolute expiry (CTO_PLAN §1.2)."""
        if self.iat is None or self.exp is None:
            return False
        now = time.time() if now is None else now
        return (self.iat + self.exp) >= now


def _b64url_decode_no_pad(s: str) -> bytes:
    """base64url-decode with optional padding restored (R44)."""
    s = s.strip()
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))


def split_token(token: str) -> tuple[bytes, bytes]:
    """Split ``payload.signature`` into their raw byte forms (R44).

    The **signed data** is the exact base64url payload string bytes (not
    the decoded JSON) — per the Keygate token format.
    """
    parts = token.strip().split(".")
    if len(parts) != 2:
        raise ValueError("malformed token: expected '<payload>.<signature>'")
    payload_bytes = parts[0].encode("ascii")   # signed data
    signature = _b64url_decode_no_pad(parts[1])
    return payload_bytes, signature


def decode_payload(token: str) -> dict:
    """Decode the JSON payload of a signed token (for inspection)."""
    payload_bytes, _ = split_token(token)
    return json.loads(base64.urlsafe_b64decode(
        payload_bytes + b"=" * ((-len(payload_bytes)) % 4)
    ).decode("utf-8"))


def verify_signed_token(token: str, public_key_hex: str,
                        now: float | None = None) -> _TokenPayload:
    """Verify an ed25519-signed token against a cached public key (R5).

    Args:
        token: ``<base64url-payload>.<base64url-signature>``.
        public_key_hex: 64-char hex Ed25519 public key (from
            ``GET /api/v1/license/pubkey`` or cached from a prior response).
        now: optional unix timestamp override (for tests).

    Returns:
        :class:`_TokenPayload` with parsed fields.

    Raises:
        ValueError: malformed token or signature failure.
    """
    from cryptography.exceptions import InvalidSignature

    payload_bytes, signature = split_token(token)
    pubkey = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(public_key_hex.strip()))
    try:
        pubkey.verify(signature, payload_bytes)
    except InvalidSignature as exc:
        raise ValueError("invalid token signature") from exc
    return _TokenPayload(decode_payload(token), token)


def token_within_ttl(token: str, now: float | None = None) -> bool:
    """Convenience: True when the token is within its check-in window."""
    payload = _TokenPayload(decode_payload(token), token)
    return payload.is_within_ttl(now)


def sign_test_token(payload: dict, private_key_hex: str) -> str:
    """Create a Keygate-format signed token for testing.

    ``payload`` is JSON-encoded then base64url-encoded (no padding); the
    Ed25519 signature over those exact bytes is appended.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    priv = Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(private_key_hex.strip())[:32])
    sig = priv.sign(body.encode("ascii"))
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{body}.{sig_b64}"


def generate_test_keypair() -> tuple[str, str]:
    """Return (private_key_hex, public_key_hex) for test vectors (R44)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    priv = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption())
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return priv_bytes.hex(), pub_bytes.hex()
