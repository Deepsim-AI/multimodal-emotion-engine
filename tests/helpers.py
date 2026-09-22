"""Shared test helpers for MEE test suite.

TASK_MEE_010: Jetson hardware detection helper used by test_vision.py
and test_voice.py to skip GPU-specific tests on non-Jetson environments.
"""
from __future__ import annotations

import os
import subprocess


def is_jetson() -> bool:
    """Return True if running on Jetson hardware.

    Checks (in order):
      1. /sys/class/nvmap exists (Jetson unified memory allocator)
      2. /sys/devices/platform/bd700000.gpu exists (Jetson GPU platform device)
      3. nvidia-smi reports a Jetson GPU name
    """
    if os.path.exists("/sys/class/nvmap"):
        return True
    if os.path.exists("/sys/devices/platform/bd700000.gpu"):
        return True
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and "Jetson" in r.stdout:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False
