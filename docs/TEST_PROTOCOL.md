# TEST_PROTOCOL — TASK_MEE_009 End-to-End Validation

**Task ID:** TASK_MEE_009
**Status:** Implemented (this document is the evaluation protocol)
**Related:** `tools/evaluate_scenarios.py`, `tests/scenario_data.py`, `tests/test_scenarios.py`

---

## 1. Methodology

### What this validates

The full **pipeline glue** of `EmotionEngine.process()` is exercised end-to-end:

- the **vision channel** path (`_infer_vision` → `_MEEFaceResult` → fusion),
- the **voice channel** path (`_infer_voice` → fusion),
- the **fusion** step (weighted combination + explicit conflict reporting),
- **history recording** (each step appended to `EmotionFusion.history`),
- **trend analysis** (`analyze_trend` over the accumulated buffer),
- the **public return contract** (`face`, `voice`, `overall`, `trend`, `latency_ms`).

This confirms the pipeline *connects correctly*: the correct channel results flow into fusion, the conflict flag is preserved (not hidden), and the temporal state evolves as expected.

### Synthetic data — not live hardware

This system has no `insightface`, `librosa`, or `sounddevice` installed, so live camera/mic inference is impossible here. Instead of loading real models, the harness **monkey-patches** `EmotionEngine._infer_vision` and `_EmotionEngine._infer_voice` to return predetermined channel dicts that match the real `VisionProcessor`/`VoiceProcessor` output contract:

```python
# face dict contract: {emotion, confidence, scores, has_face}
# voice dict contract: {emotion, confidence, scores}
```

`process()` then runs its **real** code path (fusion, history, trend, latency) against those results. This is true integration testing of the pipeline logic without hardware or model downloads.

### What this does NOT validate

- Real model inference accuracy (that is the scope of MEE_010 + hardware bring-up).
- Absolute latency against a production target — the numbers are meaningful only **relative to this Jetson-class host**, not a latency SLA.
- The `VisionProcessor`/`VoiceProcessor` internal feature extraction (covered by their own unit tests and the hardware tasks).

---

## 2. Scenario Definitions

Five standardized scenarios, each a 10-step input sequence. A step specifies the vision and voice channel outputs at that point.

### Scenario A — Neutral (vision-only)
| Field | Value |
|-------|-------|
| Vision | `neutral`, confidence 0.85, present every step |
| Voice | absent |
| Exercises | single-modality (vision-only) path |

### Scenario B — Happy (both agree)
| Field | Value |
|-------|-------|
| Vision | `happy`, confidence 0.90 |
| Voice | `happy`, confidence 0.85 |
| Exercises | dual-channel **agreement** path |

### Scenario C — Sad (vision-only)
| Field | Value |
|-------|-------|
| Vision | `sad`, confidence 0.80 |
| Voice | absent |
| Exercises | single-modality (vision-only) path, negative emotion |

### Scenario D — Frustrated (conflicting modalities)
| Steps | Vision | Voice |
|-------|--------|-------|
| 0–4 | `happy` 0.85 | `angry` 0.75 |
| 5–9 | `happy` 0.70 | `sad` 0.65 |
| Exercises | **conflict path** — opposing dominant labels |

The vision channel (higher confidence) is expected to win; `conflict` must stay `True`.

### Scenario E — Cross-over (emotion shift over time)
| Steps | Vision | Voice |
|-------|--------|-------|
| 0–3 | `happy` 0.80 | `happy` 0.75 |
| 4–6 | `neutral` 0.40 | `neutral` 0.40 |
| 7–9 | `sad` 0.80 | `sad` 0.75 |
| Exercises | **temporal shift** — trend must reflect the transition |

---

## 3. Expected Results

| Scenario | Emotion (final) | Conflict (final) | Trend (final) | Why |
|----------|-----------------|------------------|---------------|-----|
| A | `neutral` | `False` | `stable` | single label, flat confidence |
| B | `happy` | `False` | `stable` | both agree, flat |
| C | `sad` | `False` | `stable` | single label, flat |
| D | `happy` | `True` | `stable` | higher-conf label wins; label never changes so trend stays calm |
| E | `sad` | `False` | `unstable` | dominant emotion changes within the window → shift detected |

Notes on the expected trend values:
- **D = stable** (not "unstable"): the *dominant* label is `happy` on every step (vision always wins), and the per-step fused confidence varies only mildly (within the trend `conf_threshold`), so the trajectory is classified stable even though a conflict is reported on each step.
- **E = unstable**: the dominant emotion transitions `happy → neutral → sad`; because no single label holds ≥50% of the window, `analyze_trend` classifies the stream as unstable. The harness accepts `unstable` (and would also accept `declining` if a confidence dip dominated) — the key property is that it is **not** `stable`.

---

## 4. Pass/Fail Criteria

A scenario **passes** if and only if the final step's results match all three expected values:

1. `overall.emotion` == expected emotion
2. `overall.conflict` == expected conflict (boolean)
3. `trend` == expected trend

Additionally, **every** scenario must satisfy the structural contract on **every** step:

- `process()` returns keys exactly `{face, voice, overall, trend, latency_ms}`
- `overall` has keys exactly `{emotion, confidence, conflict}`
- `face` is present (non-null) and `face.has_face` reflects the step's vision presence
- `0.0 ≤ overall.confidence ≤ 1.0`
- `latency_ms` is a non-negative number
- `process()` never raises on any synthetic input

The harness (`tools/evaluate_scenarios.py`) reports a per-scenario ✅/❌ and exits `0` only when **all five** pass.

The pytest suite (`tests/test_scenarios.py`) encodes these same assertions plus the cross-scenario coverage guarantees (vision exercised, voice exercised in B/D/E, conflict path exercised in D, trend computed over time in E).

---

## 5. How to Run

```bash
# 1) Pytest integration suite (fast, structured assertions)
python3 -m pytest tests/test_scenarios.py -v

# 2) Runnable harness (markdown table + JSON dump)
python3 tools/evaluate_scenarios.py
python3 tools/evaluate_scenarios.py --json /tmp/mee009.json   # optional file output

# 3) Confirm the full repo suite still passes
python3 -m pytest tests/ -q
```

---

## 6. Known Limitations

1. **No real inference.** The vision/voice channels are stubbed to fixed outputs, so model accuracy and real feature extraction are **not** tested here. That is deliberately scoped to MEE_010 and the Jetson bring-up tasks.
2. **Latency is host-relative.** The reported `latency_ms` reflects this host's timing of the pipeline glue (fusion + trend), not a production latency target. It is a sanity bound (asserted `< 100 ms`), not an SLA.
3. **Fusion/trend logic is unit-covered elsewhere.** The fusion math and trend estimator are covered by the `test_fusion.py` / `test_vision.py` / `test_voice.py` suites. This task validates that the engine **wires** them together correctly — the integration/glue, not the math.
4. **Synthetic frame/audio arrays are trivial** (`np.zeros`). They exist only to satisfy the `process()` contract; the patched `_infer_*` methods return predetermined results regardless of input content.
5. **Trend values depend on the shipped defaults** (`EmotionFusionConfig` and `MEEConfig` defaults: `conflict_threshold=0.5`, `trend_window=30`). The expected results above are computed against those defaults; changing them could change the `stable`/`unstable` classification for scenario D/E.

---

## 7. Environment Requirements

- Python ≥ 3.10
- `numpy` (for the synthetic frame/audio arrays)
- The `mee` package (installed in the repo, no extra deps for the synthetic path)
- `pytest` (for the suite)
- **No** `insightface` / `librosa` / `sounddevice` / `speechbrain` required — the synthetic path bypasses all model loading.
