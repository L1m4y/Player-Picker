"""Small JSON-over-Unix-socket protocol used by the daemon and the GUI."""

from __future__ import annotations

import json
import socket
from typing import Any

MAX_MESSAGE_BYTES = 64 * 1024


class ProtocolError(ValueError):
    """Raised when a message cannot be encoded, decoded or validated."""


def encode_message(payload: dict[str, Any]) -> bytes:
    if not isinstance(payload, dict):
        raise ProtocolError("message must be a JSON object")
    try:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"message is not JSON serializable: {exc}") from exc
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message is too large")
    return data + b"\n"


def decode_message(raw: bytes) -> dict[str, Any]:
    if not raw:
        raise ProtocolError("empty message")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message is too large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("message must be a JSON object")
    return payload


def validate_request(payload: dict[str, Any]) -> str:
    action = payload.get("action")
    if not isinstance(action, str) or not action:
        raise ProtocolError("missing or invalid 'action'")
    return action


def send_request(socket_path: str, payload: dict[str, Any], timeout: float = 1.0) -> dict[str, Any]:
    data = encode_message(payload)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path))
        sock.sendall(data)

        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_MESSAGE_BYTES:
                raise ProtocolError("response is too large")
            chunks.append(chunk)
    if not chunks:
        raise ProtocolError("daemon closed the connection without a response")
    return decode_message(b"".join(chunks))


def ok_response(**fields: Any) -> dict[str, Any]:
    return {"status": "ok", **fields}


def error_response(message: str) -> dict[str, Any]:
    return {"status": "error", "error": message}
