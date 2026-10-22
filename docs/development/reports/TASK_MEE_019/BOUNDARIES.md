# BOUNDARIES — TASK_MEE_019 What This Task Does NOT Touch

**Task ID:** TASK_MEE_019  
**Date:** 2026-10-22

---

## Files NOT Modified (Out of Scope)

| File | Reason |
|------|--------|
| `mee/licensing/client.py` | Already complete in TASK_MEE_015 |
| `mee/licensing/cli.py` | CLI remains unchanged; AC5 requires this |
| `mee/licensing/config.py` | Licensing config untouched |
| `mee/licensing/trial.py` | Trial logic unchanged |
| `mee/licensing/offline.py` | Offline verification untouched |
| `mee/licensing/device.py` | Device ID generation unchanged |
| `mee/licensing/errors.py` | Error classes unchanged |
| `mee/licensing/results.py` | Result dataclass unchanged |
| `pyproject.toml` | No new dependencies needed |

## Files NOT Created (Out of Scope)

- New Keygate plans or prices (already created by owner)
- New Stripe products
- Docker/config deployment files
- Front-end build system (single HTML file, no bundler)
- CAPTCHA/bot protection (v0 rate-limit is sufficient per PM decision)

## Summary

**In scope:** 4 new server endpoints + UI in existing `server.py` and `index.html` + docs updates.  
**Out of scope:** All licensing infrastructure, Keygate config, Stripe config, deployment, models, engine gates, CLI modifications.
