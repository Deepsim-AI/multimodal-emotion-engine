# TASK_REQUEST — TASK_MEE_001: Project Setup & Architecture

**Task ID:** TASK_MEE_001
**Status:** Ready → awaiting CTO plan
**Requested By:** PM (DS-EO)
**Assignee (planning):** CTO · **Assignee (build):** Implementer · **Verifies:** Reviewer

## Objective
Establish the MEE repository skeleton, lock the stable public API boundary, and publish the V1 architecture + initial dependency/manifest. This is the foundation every other task builds on.

## Detailed Requirements
- Define the `mee/` package structure: `mee/`, `mee/vision/`, `mee/voice/`, `mee/fusion/`, `mee/state/`, `mee/api/`, `demo/`, `tests/`.
- Implement the **stable public API stub** `EmotionEngine.process(video_frame, audio) -> JSON-serializable dict` returning keys: `face`, `voice`, `overall`, `trend`, plus optional `conflict`/`latency_ms` (see ARCHITECTURE contract).
- Model backends are implementation details: when no backend is installed, inference returns graceful fallback (`has_face=False`, `emotion=None`, `confidence≈0`) — never crash.
- Create `pyproject.toml` / `requirements.txt` with optional dependency groups (vision, voice, demo, dev) and a permissive-ish license placeholder.
- Publish `docs/ARCHITECTURE.md` (V1 architecture, layered diagram, module responsibilities, stable API).
- Initialize the git repository with `.gitignore` (models, venv, `__pycache__`), README, LICENSE.

## Key Files (to create/modify)
- `mee/__init__.py`, `mee/api/__init__.py`, `mee/api/engine.py` (EmotionEngine + MEEConfig stubs)
- `mee/vision/__init__.py`, `mee/voice/__init__.py`, `mee/fusion/__init__.py`, `mee/state/__init__.py`
- `pyproject.toml`, `requirements.txt`, `README.md`, `LICENSE`, `.gitignore`
- `docs/ARCHITECTURE.md`

## Acceptance Criteria
- [ ] `pip install -e .` succeeds with no mandatory deps.
- [ ] `from mee.api.engine import EmotionEngine` works; `EmotionEngine().process(None, None)` raises the documented "supply at least one input" error (not an exception).
- [ ] `process(video_frame=<frame>)` returns a dict with `face`/`voice`/`overall`/`trend` keys and graceful vision fallback.
- [ ] `docs/ARCHITECTURE.md` documents layers, module responsibilities, and the exact public API.
- [ ] README documents install + a minimal usage example.

## Dependencies
- None (initialization task).

## Notes / Constraints
- MEE is an **independent** capability; must **not** depend on the AI Companion book Ch.15 at runtime.
- Terminology: use "facial-expression estimation" / "voice (acoustic) emotion estimation" / "affective-state estimation". **Never** claim the system "reads true emotion" or "determines internal psychological state."
