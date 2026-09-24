"""TASK_MEE_014 Subtask 1: Configuration for the remote demo WebSocket server.

Prototype-grade settings. All values can be overridden via environment
variables (MEE_DEMO_*) so deployment on the Jetson does not require code
changes.

Security-relevant defaults follow gate/G3_RESPONSE.md (CTO decision 4a/4b/4d):
- Token: random 32-char hex via secrets.token_hex(32)
- Token dir: $HOME/.config/mee-remotedemo/
- Audit log: same dir, TimedRotatingFileHandler daily rotation
- CORS: Access-Control-Allow-Origin: * (prototype-grade)

Precedence per field (highest first):
  1. Explicit non-None argument passed to RemotedemoConfig(...)
  2. MEE_DEMO_* environment variable
  3. Built-in default
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional


def default_state_dir() -> Path:
    """Directory for persistent demo state (token, auth log)."""
    return Path(os.environ.get(
        "MEE_DEMO_HOME",
        str(Path.home() / ".config" / "mee-remotedemo"),
    ))


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class RemotedemoConfig:
    """WebSocket server configuration.

    All fields are keyword arguments defaulting to ``None``.  A custom
    ``__init__`` resolves each from (explicit arg, env var, built-in
    default) in that order.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        token: Optional[str] = None,
        token_file: Optional[Path] = None,
        auth_log_file: Optional[Path] = None,
        max_connections: Optional[int] = None,
        idle_timeout_s: Optional[int] = None,
        max_fps: Optional[int] = None,
        audio_chunk_ms: Optional[int] = None,
        max_audio_chunk_samples: Optional[int] = None,
        max_frame_bytes: Optional[int] = None,
        cors_origin: Optional[str] = None,
    ) -> None:
        sdir = default_state_dir()
        self.host = host if host is not None else _env("MEE_DEMO_HOST", "127.0.0.1")
        self.port = int(port) if port is not None else int(_env("MEE_DEMO_PORT", "8910"))
        self.token = token if token is not None else _env("MEE_DEMO_TOKEN", "")
        self.token_file = (token_file if token_file is not None
                           else Path(_env("MEE_DEMO_TOKEN_FILE", str(sdir / "token"))))
        self.auth_log_file = (auth_log_file if auth_log_file is not None
                              else Path(_env("MEE_DEMO_AUTH_LOG", str(sdir / "auth.log"))))
        self.max_connections = (int(max_connections) if max_connections is not None
                                else int(_env("MEE_DEMO_MAX_CONN", "10")))
        self.idle_timeout_s = (int(idle_timeout_s) if idle_timeout_s is not None
                               else int(_env("MEE_DEMO_IDLE_TIMEOUT_S", "1800")))
        self.max_fps = int(max_fps) if max_fps is not None else int(_env("MEE_DEMO_MAX_FPS", "15"))
        self.audio_chunk_ms = (int(audio_chunk_ms) if audio_chunk_ms is not None
                               else int(_env("MEE_DEMO_AUDIO_CHUNK_MS", "20")))
        self.max_audio_chunk_samples = (
            int(max_audio_chunk_samples) if max_audio_chunk_samples is not None
            else int(_env("MEE_DEMO_MAX_AUDIO_SAMPLES", "16000")))
        self.max_frame_bytes = (int(max_frame_bytes) if max_frame_bytes is not None
                                else int(_env("MEE_DEMO_MAX_FRAME_BYTES", str(4 * 1024 * 1024))))
        self.cors_origin = cors_origin if cors_origin is not None else _env("MEE_DEMO_CORS_ORIGIN", "*")

    def resolve_token(self, create: bool = True) -> str:
        """Return the active access credential, generating + persisting one if needed.

        Precedence:
          1. Explicit self.token (from code / env / CLI)
          2. Existing token_file contents
          3. Freshly generated secrets.token_hex(32), written to token_file
        """
        if self.token:
            return self.token
        if self.token_file.exists():
            existing = self.token_file.read_text().strip()
            if existing:
                return existing
        new_val = secrets.token_hex(32)
        if create:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(new_val + "\n")
            try:
                os.chmod(self.token_file, 0o600)
            except OSError:
                pass
        self.token = new_val
        return new_val

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        # Do not leak the secret credential into repr/logs.
        fields = {
            "host": self.host,
            "port": self.port,
            "token": ("***" if self.token else "***"),
            "token_file": str(self.token_file),
            "auth_log_file": str(self.auth_log_file),
            "max_connections": self.max_connections,
            "idle_timeout_s": self.idle_timeout_s,
            "max_fps": self.max_fps,
            "cors_origin": self.cors_origin,
        }
        inner = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"RemotedemoConfig({inner})"


def build_config_from_env() -> RemotedemoConfig:
    """Build a RemotedemoConfig from the current environment."""
    return RemotedemoConfig()
