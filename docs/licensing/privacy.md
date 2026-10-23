# MEE Network Operations & Privacy Statement (TASK_MEE_020, C7)

**Binding rule C7 (CTO_PLAN §9):** no hidden telemetry, no data collection.

This page states, for customers, exactly what network operations MEE
performs and what data is sent. It is a **complete** list — there are no
other outbound calls.

---

## 1. Outbound network operations (the only ones)

MEE makes outbound network calls **only** in the following situations:

| Operation | Trigger | Destination | Data sent |
|-----------|---------|-------------|-----------|
| **License activation** | `mee-lic activate <key>` / first `verify()` with a key | Keygate license server | `license_key`, `device_id` |
| **License verification** | `verify()` (online path) / `mee-lic verify` | Keygate license server | `license_key`, `device_id` |
| **License deactivation** | `mee-lic deactivate` | Keygate license server | `license_key`, `device_id` |
| **Sigstore signature verification** | `tools/verify_release.sh` (customer-initiated) | Sigstore public CA (Fulcio + Rekor) | The artifact + identity to verify |

That is the complete set. **Nothing else** is sent over the network.

---

## 2. What is NOT sent

- **No telemetry** — MEE does not collect usage metrics, emotion results,
  frames, audio, or any runtime output.
- **No analytics** — there is no analytics endpoint, no crash reporter,
  no performance profiling data, no build fingerprint.
- **No license-key transmission to any third party** — the license key is
  sent **only** to the configured Keygate license server
  (`MEE_LICENSE_SERVER`, default `https://licenses.deepsim.ai:8443`).
- **No emotion inference data** — the vision/voice inference runs locally;
  frames and audio are never uploaded.

---

## 3. Offline operation

When the network is unavailable:

- A **valid cached license token** (within its `exp` check-in window)
  allows inference to proceed — **no network call is made** (C12,
  see `offline.md`).
- If the token is expired or missing, inference is **blocked** — MEE does
  **not** fall back to any "anonymous" or "degraded" network path.

---

## 4. Sigstore verification (customer-initiated)

`tools/verify_release.sh` contacts the **Sigstore public CA** (Fulcio for
certificate verification, Rekor for the transparency log) **only** when the
customer runs it to verify a release artifact. This is a standard,
public, read-only verification — no MEE-specific data is sent, and it does
not occur during normal MEE operation.

---

## 5. Configuration surface

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEE_LICENSE_SERVER` | `https://licenses.deepsim.ai:8443` | Keygate license server URL |
| `MEE_LICENSE_KEY` | unset | License key (auto-activate) |
| `MEE_DEVICE_ID` | auto-generated | Device identifier |
| `MEE_HOME` | `~/.config/mee-licensing` | Local license state dir |
| `MEE_INTEGRITY_CHECK` | unset (dev off / signed on) | Integrity gate toggle |
| `MEE_INTEGRITY_ANCHOR` | unset | Explicit integrity anchor path |

All of these are **local** configuration; none add outbound calls beyond
the table in §1.

---

## 6. Statement

> **MEE performs no telemetry, no analytics, and no hidden data
> collection.** The only outbound network operations are explicit
> license-management calls to the customer-configured Keygate server, and
> the customer-initiated Sigstore release-verification step. Emotion
> inference and all processing data remain on the customer's device.

This statement is the binding privacy commitment for the MEE client.
