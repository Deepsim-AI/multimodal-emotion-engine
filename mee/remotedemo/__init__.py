"""TASK_MEE_014 Subtask 1: MEE remote demo package.

WebSocket bridge between a browser client (camera + mic) and the public
``EmotionEngine.process()`` API. The browser never sees model weights or
source code — it only speaks the documented JSON protocol.

Public exports:
    RemotedemoConfig   — configuration (config.py)
    RemotedemoServer   — WebSocket server (server.py)
    run_server         — asyncio entrypoint (server.py)
    PROTOCOL_VERSION   — protocol identifier
"""
from .config import RemotedemoConfig, build_config_from_env, default_state_dir
from .server import (
    PROTOCOL_VERSION,
    AuthAuditor,
    AuthError,
    CommunityRequestRateLimiter,
    LicenseHTTPServer,
    PayloadTooLarge,
    RateLimiter,
    RemotedemoServer,
    RateLimited,
    decode_audio_f32,
    decode_image_bgr,
    run_server,
    serialize_result,
)

__all__ = [
    "PROTOCOL_VERSION",
    "AuthAuditor",
    "AuthError",
    "CommunityRequestRateLimiter",
    "LicenseHTTPServer",
    "PayloadTooLarge",
    "RateLimiter",
    "RateLimited",
    "RemotedemoConfig",
    "RemotedemoServer",
    "build_config_from_env",
    "default_state_dir",
    "decode_audio_f32",
    "decode_image_bgr",
    "run_server",
    "serialize_result",
]
