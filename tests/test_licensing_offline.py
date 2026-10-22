"""R43, R44, R5 — offline ed25519 token verification (TASK_MEE_015)."""
from __future__ import annotations

import base64
import json
import time

import pytest

from mee.licensing.offline import (
    decode_payload,
    generate_test_keypair,
    sign_test_token,
    split_token,
    token_within_ttl,
    verify_signed_token,
)
from mee.licensing.results import VerificationResult


def test_ed25519_import_available():
    """R43: the cryptography Ed25519 import succeeds on the MEE host.
    (This is also the R45 pre-flight check — recorded here as a test.)"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    assert Ed25519PublicKey.from_public_bytes is not None


def test_base64url_roundtrip_no_padding():
    """R44: base64url encode/decode is reversible without padding."""
    msg = b"hello MEE licensing \x00\x01\x02\xff"
    enc = base64.urlsafe_b64encode(msg).decode("ascii").rstrip("=")
    assert "=" not in enc
    # Decode with padding restored.
    dec = base64.urlsafe_b64decode(enc + "=" * ((-len(enc)) % 4))
    assert dec == msg


def test_token_roundtrip_with_signature(test_privkey, test_pubkey):
    """R44: a token signed over the base64url payload string verifies."""
    now = int(time.time())
    payload = {"sts": "active", "iat": now, "exp": 604800, "pln": "plan-1"}
    token = sign_test_token(payload, test_privkey)
    # Token has exactly two base64url segments.
    body_b64, sig_b64 = token.split(".")
    assert "=" not in body_b64 and "=" not in sig_b64
    # Verify with the public key.
    result = verify_signed_token(token, test_pubkey)
    assert result.status == "active"
    assert result.plan_id == "plan-1"
    assert token_within_ttl(token) is True


def test_invalid_signature_rejected(test_privkey, test_pubkey):
    now = int(time.time())
    token = sign_test_token({"sts": "active", "iat": now, "exp": 600}, test_privkey)
    body_b64, sig_b64 = token.split(".")
    # Flip one bit of the signature.
    bad_sig = bytearray(base64.urlsafe_b64decode(sig_b64 + "=" * ((-len(sig_b64)) % 4)))
    bad_sig[0] ^= 1
    bad_sig_b64 = base64.urlsafe_b64encode(bytes(bad_sig)).decode("ascii").rstrip("=")
    bad_token = f"{body_b64}.{bad_sig_b64}"
    with pytest.raises(ValueError, match="signature"):
        verify_signed_token(bad_token, test_pubkey)


def test_wrong_key_rejected():
    priv, _ = generate_test_keypair()
    other_priv, other_pub = generate_test_keypair()
    now = int(time.time())
    token = sign_test_token({"sts": "active", "iat": now, "exp": 600}, priv)
    with pytest.raises(ValueError, match="signature"):
        verify_signed_token(token, other_pub)


def test_expired_token_not_within_ttl(test_privkey, test_pubkey):
    now = int(time.time())
    # iat in the far past, exp short → outside TTL.
    token = sign_test_token(
        {"sts": "active", "iat": now - 10_000_000, "exp": 600},
        test_privkey)
    assert token_within_ttl(token) is False


def test_payload_decode_returns_fields(test_privkey):
    now = int(time.time())
    token = sign_test_token(
        {"sts": "active", "pln": "plan-xyz", "ftr": {"a": 1},
         "iat": now, "exp": 600},
        test_privkey)
    payload = decode_payload(token)
    assert payload["sts"] == "active"
    assert payload["pln"] == "plan-xyz"
    assert payload["ftr"] == {"a": 1}
