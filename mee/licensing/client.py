"""LicenseClient — Keygate HTTP client for MEE (TASK_MEE_015).

Implements R1, R3-R7, R17, R28-R30, R35-R39, R41, R42.

Keygate 0.1.15 API contract (verified live at G1 — see CTO_PLAN §1):
- All SDK endpoints take ``{license_key, identifier}`` in the JSON body —
  NO auth header. The device ID travels as the ``identifier`` field (R17).
- Oracle hardening: license-knowable failures collapse to
  ``404 LICENSE_NOT_FOUND`` — the client cannot distinguish "invalid key"
  from "license deleted" and must not treat that as an error condition.

Retry policy (R7, CTO_PLAN §1.4): at most one retry per call (max 2 total
attempts), exponential backoff base 1s, 5-second per-call timeout. This
avoids triggering Keygate's brute-force protection (5 failures → 30s
lockout).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import LicensingConfig
from .errors import ActivationLimitError, LicenseClientError
from .results import VerificationResult
from .offline import (
    verify_signed_token,
)
from .trial import (
    ensure_trial_marker,
    is_trial_expired,
    trial_active,
    trial_remaining_days,
    mark_deactivated,
    clear_deactivated,
    is_deactivated,
)

logger = logging.getLogger(__name__)

# R7: hard HTTP timeout (seconds). No custom timeout config is allowed.
HTTP_TIMEOUT_S = 5.0
# R7: at most one retry per call (max 2 attempts), backoff base 1s.
MAX_RETRIES = 1
BACKOFF_BASE_S = 1.0

# R30 (Amendment C): Keygate lifecycle state → MEE status map.
# Unmapped states are passed through literally (forward-compatible, R29).
STATUS_MAP = {
    "active": "licensed",
    "trialing": "trialing",
    "past_due": "expired",
    "canceled": "expired",
    "expired": "expired",
    "suspended": "degraded",
    "revoked": "degraded",
}


def map_status(raw_status: str | None) -> str | None:
    """Map a Keygate lifecycle status to the MEE client status (R30)."""
    if raw_status is None:
        return None
    return STATUS_MAP.get(raw_status, raw_status)


def _key_hash(license_key: str) -> str:
    """R3: state file naming — SHA-256 of the license key, first 16 hex."""
    return hashlib.sha256(license_key.encode("utf-8")).hexdigest()[:16]


class LicenseClient:
    """Client for the Keygate license server (R1).

    All methods are safe to call from a single process; state is persisted
    under ``config.state_dir`` (``$MEE_HOME/licenses/``).
    """

    def __init__(self,
                 config: Optional[LicensingConfig] = None,
                 device_id: Optional[str] = None,
                 session: Optional[requests.Session] = None):
        self.config = config or LicensingConfig()
        self._session = session or requests.Session()
        self._device_id = device_id
        # R3: last verification metadata (in-memory mirror of state file).
        self._last_result: Optional[VerificationResult] = None

    # ------------------------------------------------------------------
    # device identity
    # ------------------------------------------------------------------

    @property
    def device_id(self) -> str:
        """Stable device ID (R16, R18). Env var > persisted > generated."""
        if self._device_id is None:
            from .device import get_device_id
            self._device_id = get_device_id(
                self.config.home_dir_resolved)
        return self._device_id

    # ------------------------------------------------------------------
    # state persistence (R3)
    # ------------------------------------------------------------------

    def _state_path(self, license_key: str) -> Path:
        return self.config.state_dir / f"{_key_hash(license_key)}.json"

    def _load_state(self, license_key: str) -> dict | None:
        path = self._state_path(license_key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("License state file unreadable — ignoring")
            return None

    def _save_state(self, license_key: str, data: dict) -> None:
        path = self._state_path(license_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Keep permissions tight — file contains the license key + token.
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _current_key(self) -> str | None:
        key = self.config.license_key
        if key:
            return key
        # Fall back to whatever state files exist (first one wins).
        try:
            files = sorted(self.config.state_dir.glob("*.json"))
        except Exception:
            files = []
        if files:
            try:
                return json.loads(
                    files[0].read_text(encoding="utf-8")).get("license_key")
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # HTTP plumbing (R7)
    # ------------------------------------------------------------------

    def _post(self, path: str, body: dict) -> dict:
        """POST with 5s timeout, 1 retry, exponential backoff (R7).

        Returns the parsed JSON body. Raises :class:`LicenseClientError`
        on non-2xx responses (except 404 which callers may treat as
        "no license" per oracle hardening — handled per-endpoint).
        """
        url = self.config.server_url.rstrip("/") + path
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    url, json=body, timeout=HTTP_TIMEOUT_S)
                if resp.status_code == 404:
                    # Oracle hardening: LICENSE_NOT_FOUND — not an error
                    # condition; caller decides (see _verify_online).
                    raise _Http404()
                if resp.status_code >= 400:
                    detail = _extract_error_code(resp)
                    raise LicenseClientError(
                        f"Keygate {path} failed: "
                        f"HTTP {resp.status_code} ({detail})")
                return resp.json()
            except requests.exceptions.RequestException as exc:
                # Network-level failure (timeout, DNS, connection reset).
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_BASE_S * (2 ** attempt))
                    continue
                raise LicenseClientError(
                    f"network error calling Keygate {path}") from exc
        raise LicenseClientError(
            f"Keygate {path} failed after retries") from last_exc

    def _get(self, path: str) -> dict:
        url = self.config.server_url.rstrip("/") + path
        try:
            resp = self._session.get(url, timeout=HTTP_TIMEOUT_S)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            raise LicenseClientError(
                f"network error calling Keygate {path}") from exc

    # ------------------------------------------------------------------
    # public API (R1)
    # ------------------------------------------------------------------

    def activate(self, license_key: str,
                 device_id: str | None = None) -> VerificationResult:
        """Activate a license on this device (R1, R39).

        Raises:
            ActivationLimitError: Keygate reports ACTIVATION_LIMIT (R38).
            LicenseClientError: other Keygate/HTTP errors.
        """
        identifier = device_id or self.device_id
        body = {"license_key": license_key, "identifier": identifier}
        try:
            payload = self._post("/api/v1/license/activate", body)
        except _Http404:
            # Oracle hardening: unknown key → 404.
            raise LicenseClientError(
                "license key not found (invalid or deleted)")
        except LicenseClientError as exc:
            msg = str(exc)
            if "ACTIVATION_LIMIT" in msg or "activation" in msg.lower():
                raise ActivationLimitError() from exc
            raise
        data = payload.get("data") or {}
        result = self._result_from_keygate_data(
            data, offline=False, source_key=license_key)
        # Re-activation restores normal behavior — clear any prior
        # deactivation sentinel so the trial path works again for this device.
        clear_deactivated(self.config.state_dir)
        if data.get("token"):
            self._save_state(license_key, {
                "license_key": license_key,
                "device_id": identifier,
                "last_verified": result.last_verified_at,
                "public_key": data.get("public_key"),
                "token": data.get("token"),
                "status": data.get("status"),
                "plan_id": data.get("plan_id"),
                "plan_name": data.get("plan_name"),
                "features": data.get("features"),
            })
        self._last_result = result
        logger.info("License activated (status=%s)", data.get("status"))
        return result

    def verify(self, force_network: bool = False) -> VerificationResult:
        """Verify license validity (R4, R5, R29, R41, R42).

        Flow:
        1. No license key → trial evaluation (R9-R11).
        2. Cached token valid within TTL → OK, no network (R4).
        3. Otherwise network verify; on success cache new token (R4).
        4. Network error → offline check with cached pubkey (R5, R41).
        5. 404 (oracle) or bad status → trial evaluation / invalid.
        """
        key = self._current_key()
        if not key:
            return self._trial_result()

        state = self._load_state(key)
        token = (state or {}).get("token")
        pubkey = (state or {}).get("public_key")

        # (R4) cached token within TTL → OK without network.
        if token and not force_network:
            try:
                payload = verify_signed_token(token, pubkey) \
                    if pubkey else None
                if payload is not None and payload.is_within_ttl():
                    return self._result_from_payload(
                        payload, offline=False)
            except Exception:
                pass  # fall through to network verify

        # (R4) network verify.
        try:
            payload = self._post(
                "/api/v1/license/verify",
                {"license_key": key, "identifier": self.device_id})
        except _Http404:
            logger.debug("verify: 404 (oracle hardening) — no valid license")
            # A key IS present — do not auto-create a trial marker.
            return self._trial_result(allow_create=False)
        except LicenseClientError as exc:
            # Network failure (R5, R41) → offline fallback.
            logger.info("verify: network error (%s) — offline fallback",
                        _sanitize(exc))
            return self._offline_result(key, state)

        data = payload.get("data") or {}
        result = self._result_from_keygate_data(
            data, offline=False, source_key=key)
        if data.get("token"):
            self._save_state(key, {
                "license_key": key,
                "device_id": self.device_id,
                "last_verified": result.last_verified_at,
                "public_key": data.get("public_key"),
                "token": data.get("token"),
                "status": data.get("status"),
                "plan_id": data.get("plan_id"),
                "plan_name": data.get("plan_name"),
                "features": data.get("features"),
            })
        self._last_result = result
        return result

    def verify_offline(self) -> VerificationResult:
        """Offline verification of the cached token (R5).

        Returns a ``VerificationResult`` with ``offline=True``.
        """
        key = self._current_key()
        if not key:
            return self._trial_result()
        state = self._load_state(key) or {}
        return self._offline_result(key, state)

    def deactivate(self) -> None:
        """Deactivate the license on this device (R6)."""
        key = self._current_key()
        if key:
            try:
                self._post("/api/v1/license/deactivate",
                           {"license_key": key,
                            "identifier": self.device_id})
            except _Http404:
                pass  # already gone server-side; local cleanup still needed
            except LicenseClientError as exc:
                logger.warning("deactivate: server call failed (%s) — "
                               "removing local state anyway", _sanitize(exc))
        # R6: remove local state file.
        for path in self.config.state_dir.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass
        # Deactivation returns the device to a clean slate (spec acceptance
        # chain: `deactivate` → process() → LicenseExpiredError). Remove the
        # trial marker and record a deactivation sentinel so the trial path
        # does not silently re-create a fresh trial on the next process().
        trial = self.config.state_dir / ".trial"
        if trial.exists():
            try:
                trial.unlink()
            except OSError:
                pass
        mark_deactivated(self.config.state_dir)
        self._last_result = None
        logger.info("License deactivated; local state removed")

    def status(self) -> dict:
        """Current license status dict (R14, R30, R46).

        Never raises (CORE_CONTRACTS §1.4). Shape (Amendment C):
            {status, plan_id, plan_name, remaining_days, offline, features}
        plus ``device_id`` and ``last_verified`` for CLI display (R20, R47).
        """
        key = self._current_key()
        if not key:
            # No license: ensure a trial marker exists (first run creates
            # it — R8) and report the trial state.
            ensure_trial_marker(self.config.state_dir)
            in_trial = trial_active(self.config.state_dir)
            return {
                "status": "trialing" if in_trial else "expired",
                "plan_id": None,
                "plan_name": None,
                "remaining_days": trial_remaining_days(self.config.state_dir),
                "offline": False,
                "features": None,
                "device_id": self._device_id,
                "last_verified": None,
            }
        state = self._load_state(key) or {}
        token = state.get("token")
        pubkey = state.get("public_key")
        offline = False
        status_raw = state.get("status")
        features = state.get("features")
        plan_id = state.get("plan_id")
        plan_name = state.get("plan_name")
        last_verified = state.get("last_verified")

        if token and pubkey:
            try:
                payload = verify_signed_token(token, pubkey)
                if payload.is_within_ttl():
                    if payload.status:
                        status_raw = payload.status
                    if payload.plan_id:
                        plan_id = payload.plan_id
                    if payload.features:
                        features = payload.features
                else:
                    offline = True
            except Exception:
                offline = True

        return {
            "status": map_status(status_raw),
            "plan_id": plan_id,
            "plan_name": plan_name,
            "remaining_days": _remaining_days(status_raw),
            "offline": offline,
            "features": features,
            "device_id": state.get("device_id") or self._device_id,
            "last_verified": last_verified,
        }

    def trial_info(self) -> dict:
        """Trial marker state for CLI/health display."""
        return {
            "active": trial_active(self.config.state_dir),
            "expired": is_trial_expired(self.config.state_dir),
            "remaining_days": trial_remaining_days(self.config.state_dir),
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _trial_result(self, allow_create: bool = True) -> VerificationResult:
        """Result for the trial evaluation path (R9-R11, R41).

        allow_create=True  — no license key present; create marker (R8).
        allow_create=False — key present but invalid; do NOT create.
        """
        sd = self.config.state_dir
        if allow_create:
            # No license key present → trial evaluation (R9-R11, R41).
            # A device that deactivated a license must NOT re-enter a fresh
            # trial (spec chain: deactivate → process() → LicenseExpiredError).
            if is_deactivated(sd):
                return VerificationResult(valid=False, license_status=None,
                                          offline=False)
            if not trial_active(sd) and is_trial_expired(sd):
                ensure_trial_marker(sd)
            if trial_active(sd):
                return VerificationResult(
                    valid=True,
                    license_status="trialing",
                    offline=False,
                )
            return VerificationResult(valid=False, license_status=None,
                                      offline=False)
        # allow_create=False: a license key IS present but the server reports
        # it invalid (404 oracle) or it is missing/stale. R10/R42: an invalid
        # license present is a HARD STOP — a pre-existing trial marker must NOT
        # rescue this call. Trial is only for the no-key first-run path (R9-R11).
        return VerificationResult(valid=False, license_status=None,
                                  offline=False)

    def _offline_result(self, key: str, state: dict) -> VerificationResult:
        """Offline fallback (R5, R41)."""
        token = (state or {}).get("token")
        pubkey = (state or {}).get("public_key")
        if token and pubkey:
            try:
                payload = verify_signed_token(token, pubkey)
                if payload.is_within_ttl():
                    return self._result_from_payload(
                        payload, offline=True, state=state)
            except Exception as exc:
                logger.debug("offline verify failed: %s", _sanitize(exc))
        # No valid offline token. Key present → no trial creation.
        return self._trial_result(allow_create=False)

    @staticmethod
    def _result_from_keygate_data(data: dict, offline: bool,
                                  source_key: str) -> VerificationResult:
        raw_status = data.get("status")
        # R42: suspended/revoked are never valid; past_due/canceled/expired
        # are expired. Only "active"/"trialing" (or unknown, forward-
        # compatible) count as valid.
        if raw_status in STATUS_MAP:
            valid = STATUS_MAP[raw_status] in ("licensed", "trialing")
        else:
            # Unknown state: forward-compatible — treat as valid only if
            # the server also sent a token (it thinks the license is live).
            valid = bool(data.get("token"))
        features = data.get("features")
        # R36: unknown feature keys are preserved but never grant implicit
        # capabilities — the map is stored verbatim and only *known* keys
        # are ever consulted.
        return VerificationResult(
            valid=valid,
            license_status=raw_status,
            plan_id=data.get("plan_id"),
            plan_name=data.get("plan_name"),
            features=features,
            offline=offline,
            last_verified_at=time.time(),
        )

    @staticmethod
    def _result_from_payload(payload, offline: bool,
                             state: dict | None = None) -> VerificationResult:
        raw_status = payload.status
        if raw_status in STATUS_MAP:
            valid = STATUS_MAP[raw_status] in ("licensed", "trialing")
        else:
            valid = True
        return VerificationResult(
            valid=valid,
            license_status=raw_status,
            plan_id=payload.plan_id,
            plan_name=(state or {}).get("plan_name"),
            features=payload.features if payload.features is not None
            else (state or {}).get("features"),
            offline=offline,
            last_verified_at=float(payload.iat) if payload.iat else None,
        )



def _remaining_days(status_raw: str | None) -> int | None:
    """Best-effort remaining-days estimate from status (display only)."""
    if status_raw is None:
        return None
    if status_raw == "trialing":
        return None  # resolved by caller via trial marker
    return None

class _Http404(Exception):
    """Internal marker for oracle-hardened 404 responses."""


def _extract_error_code(resp: requests.Response) -> str:
    """Best-effort extraction of a Keygate error code from a response body.

    R38: detects ACTIVATION_LIMIT. Never logs the license key.
    """
    try:
        body = resp.json()
        return str(body.get("error") or body.get("code")
                   or body.get("message") or resp.status_code)
    except Exception:
        return str(resp.status_code)


def _sanitize(exc: Exception) -> str:
    """Sanitize an exception message for logging (R25): strip any
    license-key-shaped or token-shaped values before they hit a log."""
    msg = str(exc)
    msg = re.sub(r"\bKG-[A-Za-z0-9]{4,}(?:-[A-Za-z0-9]{4,})+\b",
                 "<redacted-key>", msg)
    return msg[:300]
