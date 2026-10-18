#!/usr/bin/env python3
"""Download / stage MEE model weights into the canonical ``models/`` tree.

Canonical layout (all under ``<repo>/models/``):

    models/
      vision_emotion/   enet_b0_8_best_vgaf.onnx   (+ .pt)     [EmotiEffLib]
      voice/            wav2vec2.ckpt, hyperparams.yaml,
                        label_encoder.txt, model.ckpt,         [SpeechBrain]
                        custom_interface.py, *.wav (examples)
      voice_gpu/        emotion_iemocap.onnx, .onnx.data       [ONNX/TRT, opt-in]

Vision *face* detection (MediaPipe ``face_landmark.tflite``) is intentionally
NOT downloaded here — it ships inside the ``mediapipe`` pip wheel and is
reproducible with ``pip install mediapipe``.

Usage:
    python3 tools/download_models.py                 # vision_emotion + voice
    python3 tools/download_models.py --only voice    # just one subfolder
    python3 tools/download_models.py --only voice_gpu   # opt-in GPU ONNX
    python3 tools/download_models.py --mirror        # copy already-present
                                                      weights (e.g. from the
                                                      existing ~/.insightface,
                                                      ~/.emotiefflib) into
                                                      models/ instead of
                                                      downloading
    python3 tools/download_models.py --verify        # re-check checksums only
    python3 tools/download_models.py --no-link       # don't create the
                                                      backend symlinks

Idempotent: existing files with matching size are skipped; --force re-downloads.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
MODELS = REPO / "models"

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass
class File:
    name: str
    url: Optional[str] = None          # remote URL (for --download)
    mirror: Optional[str] = None       # local source (for --mirror), expanduser'd
    size: Optional[int] = None         # expected bytes (for sanity check)
    optional: bool = False             # skip if missing and not fatal


@dataclass
class Model:
    key: str                            # subfolder under models/
    title: str
    backend: str
    license: str
    files: list = field(default_factory=list)
    # Where the backend expects these weights to live (for the symlink step).
    # A tuple of (expected_dir, expected_filename) pairs; we symlink the file
    # into expected_dir if the canonical copy exists in models/.
    link_targets: list = field(default_factory=list)


# --- EmotiEffLib (vision emotion) — GitHub raw -----------------------------
_EMOTIEFF_BASE = "https://github.com/sb-ai-lab/EmotiEffLib/raw/main/models/affectnet_emotions"
_EMOTIEFF_ONNX = _EMOTIEFF_BASE + "/onnx"
EMOTIEFF_MODEL = "enet_b0_8_best_vgaf"

VISION_EMOTION = Model(
    key="vision_emotion",
    title="Vision emotion — EmotiEffLib enet_b0_8_best_vgaf (AffectNet)",
    backend="onnxruntime",
    license="Apache-2.0 (weights, released by SB-AI-Lab) — see docs/THIRD_PARTY_LICENSES.md",
    files=[
        File(f"{EMOTIEFF_MODEL}.onnx", url=f"{_EMOTIEFF_ONNX}/{EMOTIEFF_MODEL}.onnx",
             mirror="~/.emotiefflib/" + f"{EMOTIEFF_MODEL}.onnx", size=16039595),
        File(f"{EMOTIEFF_MODEL}.pt", url=f"{_EMOTIEFF_BASE}/{EMOTIEFF_MODEL}.pt",
             mirror="~/.emotiefflib/" + f"{EMOTIEFF_MODEL}.pt", size=16419305, optional=True),
    ],
    link_targets=[
        # EmotiEffLib reads from ~/.emotiefflib/<file> (hardcoded, no env override)
        ("~/.emotiefflib", f"{EMOTIEFF_MODEL}.onnx"),
        ("~/.emotiefflib", f"{EMOTIEFF_MODEL}.pt"),
    ],
)

# --- SpeechBrain (voice) — Hugging Face / SpeechBrain hub ------------------
# The SpeechBrain wav2vec2-IEMOCAP hub repo provides the full runnable bundle.
_VOICE_HF = "https://huggingface.co/speechbrain/emotion-recognition-wav2vec2-IEMOCAP/resolve/main"
_VOICE_MIRROR_DIR = "~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP"
VOICE = Model(
    key="voice",
    title="Voice emotion — SpeechBrain wav2vec2-IEMOCAP",
    backend="speechbrain",
    license="Apache-2.0 — see docs/THIRD_PARTY_LICENSES.md",
    files=[
        File("wav2vec2.ckpt", url=f"{_VOICE_HF}/wav2vec2.ckpt", mirror=f"{_VOICE_MIRROR_DIR}/wav2vec2.ckpt", size=377575130),
        File("hyperparams.yaml", url=f"{_VOICE_HF}/hyperparams.yaml", mirror=f"{_VOICE_MIRROR_DIR}/hyperparams.yaml"),
        File("label_encoder.txt", url=f"{_VOICE_HF}/label_encoder.txt", mirror=f"{_VOICE_MIRROR_DIR}/label_encoder.txt"),
        File("model.ckpt", url=f"{_VOICE_HF}/model.ckpt", mirror=f"{_VOICE_MIRROR_DIR}/model.ckpt"),
        File("custom_interface.py", url=f"{_VOICE_HF}/custom_interface.py", mirror=f"{_VOICE_MIRROR_DIR}/custom_interface.py"),
        # Example clips (helpful for smoke tests; small)
        File("anger.wav", url=f"{_VOICE_HF}/anger.wav", mirror=f"{_VOICE_MIRROR_DIR}/anger.wav", optional=True),
        File("hap.wav", url=f"{_VOICE_HF}/hap.wav", mirror=f"{_VOICE_MIRROR_DIR}/hap.wav", optional=True),
        File("neutral.wav", url=f"{_VOICE_HF}/neutral.wav", mirror=f"{_VOICE_MIRROR_DIR}/neutral.wav", optional=True),
        File("sad.wav", url=f"{_VOICE_HF}/sad.wav", mirror=f"{_VOICE_MIRROR_DIR}/sad.wav", optional=True),
    ],
    link_targets=[
        # The engine default points at ~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP
        ("~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP", "wav2vec2.ckpt"),
    ],
)

# --- GPU voice ONNX (opt-in) — already in the repo at models/exported ------
VOICE_GPU = Model(
    key="voice_gpu",
    title="Voice emotion (GPU) — IEMOCAP ONNX for ORT/TensorRT (opt-in)",
    backend="onnxruntime-cuda/trt",
    license="Apache-2.0 — see docs/THIRD_PARTY_LICENSES.md",
    files=[
        # These live in the repo already (committed graph + gitignored data).
        # No remote URL; --mirror copies from models/exported into voice_gpu.
        File("emotion_iemocap.onnx", mirror=str(REPO / "models" / "exported" / "emotion_iemocap.onnx"), size=741128),
        File("emotion_iemocap.onnx.data", mirror=str(REPO / "models" / "exported" / "emotion_iemocap.onnx.data"), size=377552896),
    ],
)


ALL_MODELS = [VISION_EMOTION, VOICE]          # default set
OPT_IN = [VOICE_GPU]                          # not in the default set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: Optional[int]) -> str:
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def target_dir(model: Model) -> Path:
    d = MODELS / model.key
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch(url: str, dest: Path) -> None:
    """Stream a URL to dest with resume support."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    done = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "MEE-download-models/1.0"})
    if done:
        req.add_header("Range", f"bytes={done}-")
    with urllib.request.urlopen(req) as resp:
        mode = "ab" if done and resp.status == 206 else "wb"
        if mode == "wb":
            done = 0
        total = None
        clen = resp.headers.get("Content-Length")
        if clen:
            total = done + int(clen)
        with open(tmp, mode) as out:
            if total:
                print(f"    {dest.name}: {human(done)} / {human(total)}", end="", flush=True)
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                out.write(chunk)
                if total:
                    done += len(chunk)
                    print(f"\r    {dest.name}: {human(done)} / {human(total)} ({100*done//total}%)", end="", flush=True)
            if total:
                print()
    shutil.move(str(tmp), str(dest))


def place(model: Model, f: File, mirror: bool, force: bool) -> str:
    """Return status: downloaded | copied | skipped | missing | error:<msg>"""
    dest = target_dir(model) / f.name
    if dest.exists() and not force:
        if f.size and dest.stat().st_size == f.size:
            return "skipped"
        if f.size is None:
            return "skipped"
        # size mismatch -> redownload below
    try:
        if mirror:
            src = Path(os.path.expanduser(f.mirror or ""))
            if not src.exists():
                return "missing"
            shutil.copy2(src, dest)
            return "copied"
        else:
            if not f.url:
                return "missing"
            fetch(f.url, dest)
            return "downloaded"
    except Exception as exc:  # noqa: BLE001
        return f"error:{exc.__class__.__name__}:{exc}"
    finally:
        # clean any partial
        part = dest.with_suffix(dest.suffix + ".part")
        if part.exists():
            part.unlink(missing_ok=True)


def make_link(model: Model) -> list:
    """Create backend symlinks so the (unchanged) default paths resolve to
    the canonical models/ copies. Returns list of (expected, created) str."""
    created = []
    for exp_dir, exp_file in model.link_targets:
        canonical = MODELS / model.key / exp_file
        if not canonical.exists():
            continue
        exp_dir = Path(os.path.expanduser(exp_dir))
        exp_dir.mkdir(parents=True, exist_ok=True)
        link = exp_dir / exp_file
        # If it's a real file (not our symlink) with the same content, leave it.
        if link.exists() and not link.is_symlink():
            if sha256(link) == sha256(canonical):
                created.append(f"kept {link}")
                continue
            # different content — leave the real file in place (don't clobber)
            created.append(f"skipped (real file present) {link}")
            continue
        if link.is_symlink():
            link.unlink()
        try:
            link.symlink_to(canonical)
            created.append(f"linked {link} -> {canonical}")
        except OSError as exc:
            created.append(f"link-failed {link}: {exc}")
    return created


def verify(model: Model) -> list:
    out = []
    for f in model.files:
        p = MODELS / model.key / f.name
        if not p.exists():
            out.append(f"  MISSING  {f.name}")
            continue
        h = sha256(p)
        size_ok = (f.size is None) or (p.stat().st_size == f.size)
        out.append(f"  {'OK' if size_ok else 'SIZE?'}  {f.name}  sha256={h[:16]}…  ({human(p.stat().st_size)})")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Populate the canonical models/ tree.")
    ap.add_argument("--only", choices=[m.key for m in ALL_MODELS + OPT_IN] + ["all"],
                    help="process a single subfolder (default: all defaults)")
    ap.add_argument("--include-opt-in", action="store_true",
                    help="also process opt-in models (voice_gpu)")
    ap.add_argument("--mirror", action="store_true",
                    help="copy already-present weights (from the existing "
                         "~/.insightface, ~/.emotiefflib, models/exported) into "
                         "models/ instead of downloading")
    ap.add_argument("--verify", action="store_true", help="re-check checksums/sizes only")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    # 2026-10-17: the engine now resolves models/ directly (resolver layer), so
    # backend symlinks are OPTIONAL. --no-link is the default; --link restores
    # them for hosts that still rely on the old hardcoded default paths.
    ap.add_argument("--no-link", action="store_true", default=True,
                    help="(default) don't create backend symlinks — the engine "
                         "resolves models/ directly")
    ap.add_argument("--link", dest="no_link", action="store_false",
                    help="also create backend symlinks (legacy fallback for "
                         "hosts that read ~/.emotiefflib / ~/.insightface)")
    ap.add_argument("--dry-run", action="store_true", help="print what would happen, change nothing")
    args = ap.parse_args()

    models = []
    if args.only and args.only != "all":
        models = [m for m in ALL_MODELS + OPT_IN if m.key == args.only]
    else:
        models = list(ALL_MODELS)
        if args.include_opt_in:
            models += OPT_IN

    if not models:
        ap.error("no models selected")

    print(f"Canonical models root: {MODELS}")
    print(f"Mode: {'mirror (copy local)' if args.mirror else 'download'}"
          f"{'  + verify' if args.verify else ''}")
    print()

    ok = True
    for model in models:
        print(f"== {model.key} — {model.title} ==")
        print(f"   backend: {model.backend}")
        print(f"   license: {model.license}")
        if args.verify:
            for line in verify(model):
                print(line)
            print()
            continue
        if args.dry_run:
            for f in model.files:
                present = (MODELS / model.key / f.name).exists()
                src = f.mirror if args.mirror else (f.url or "(no url)")
                print(f"   {'[present] ' if present else '[fetch]   '} {f.name}  <- {src}")
            print()
            continue
        for f in model.files:
            status = place(model, f, mirror=args.mirror, force=args.force)
            tag = {
                "downloaded": "downloaded", "copied": "copied",
                "skipped": "skipped (present)", "missing": "MISSING (source not found)",
            }.get(status, status)
            print(f"   {tag:22} {f.name}  ({human(f.size)})")
            if status.startswith("error") or status == "missing":
                if f.optional:
                    ok = False
                    print(f"                    (optional — continuing)")
                else:
                    ok = False
        if not args.no_link and not args.verify:
            for line in make_link(model):
                print(f"   {'link:' if line.startswith('linked') else 'note:'} {line}")
        print()

    if not args.verify:
        print("=== models/ tree ===")
        for sub in sorted(MODELS.iterdir()):
            if sub.is_dir():
                files = sorted(sub.iterdir())
                total = sum(p.stat().st_size for p in files if p.is_file())
                print(f"  {sub.name}/  ({human(total)})  " + ", ".join(p.name for p in files))
        print()
        print("Next steps:")
        print("  1. pip install mediapipe onnxruntime speechbrain transformers")
        print("     (mediapipe ships the face_landmark.tflite for vision *detection*)")
        print("  2. (optional) python3 tools/download_models.py --link  # legacy symlinks")
        print("  3. Restart the demo: bash mee-remotedemo-stop.sh && bash mee-remotedemo-start.sh")
        print("  4. Verify: python3 tools/download_models.py --verify")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
