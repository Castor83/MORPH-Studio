"""
Shared state for the ComfyUI MCP server.

Holds the MCPServer instance, the resolved configuration, the client id, and the
HTTP helpers. Both server.py and workflow_tools.py import from here, which is
what lets the tools live in separate modules without importing each other.
"""

import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from mcp.server import MCPServer

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"

# Resolved at startup from CLI args -> env var -> default, via configure().
_comfyui_url = DEFAULT_COMFYUI_URL
_output_dir: Optional[Path] = None

# One client id for the life of the server, reused for every request so
# ComfyUI can associate all of this server's jobs with a single client.
CLIENT_ID = str(uuid.uuid4())


def configure(url: Optional[str] = None, output_dir: Optional[str] = None) -> None:
    """Set the resolved configuration. Called once from server.py's __main__."""
    global _comfyui_url, _output_dir
    if url:
        _comfyui_url = url.rstrip("/")
    _output_dir = Path(output_dir) if output_dir else None


def get_comfyui_url() -> str:
    return _comfyui_url


def get_output_dir() -> Optional[Path]:
    """The ComfyUI output directory, or None if it was never configured."""
    return _output_dir


def get_input_dir() -> Optional[Path]:
    """The ComfyUI input directory, derived from the output directory.

    input/ and output/ sit side by side in a standard install. Used only to
    READ - uploads always go through /upload/image, which works without knowing
    where ComfyUI lives. Returns None when it cannot be resolved, so callers can
    say that subfolders were not covered instead of implying they were.
    """
    if _output_dir is None:
        return None
    candidate = _output_dir.parent / "input"
    return candidate if candidate.is_dir() else None


# ============================================================================
# Server Initialization
# ============================================================================

mcp = MCPServer("comfyui_mcp")


# ============================================================================
# HTTP
# ============================================================================

def _unreachable(exc: Exception) -> ConnectionError:
    return ConnectionError(
        f"ComfyUI is not reachable at {_comfyui_url}. Is it running? ({exc})"
    )


def http_get_json(path: str, timeout: int = 10) -> dict:
    """GET a JSON endpoint. Raises ConnectionError with an actionable message."""
    try:
        req = urllib.request.Request(f"{_comfyui_url}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise _unreachable(e)


def http_post_json(path: str, payload: dict, timeout: int = 30) -> dict:
    """POST JSON and decode the reply.

    ComfyUI answers a rejected graph with HTTP 400 and a body that names the
    offending node, so the body of an HTTPError is read and returned rather
    than discarded - it is the most useful diagnostic the server produces.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_comfyui_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise ConnectionError(f"ComfyUI returned HTTP {e.code} for {path}: {e}")
    except urllib.error.URLError as e:
        raise _unreachable(e)


def encode_multipart(fields: dict, file_field: str, filename: str, content: bytes) -> tuple:
    """Build a multipart/form-data body. Returns (content_type, body_bytes).

    Hand-rolled to keep the server dependency-free. Every form value is written
    as text: ComfyUI parses these fields as strings, so a Python bool would
    arrive as "True" and silently fail to mean true.
    """
    boundary = f"----ComfyUIMCP{uuid.uuid4().hex}"
    parts = []

    for name, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # Quotes would terminate the header value early; strip rather than escape,
    # since ComfyUI matches on the name it returns anyway.
    safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{safe_name}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(content)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    return f"multipart/form-data; boundary={boundary}", b"".join(parts)


def http_post_multipart(path: str, fields: dict, file_field: str, filename: str,
                        content: bytes, timeout: int = 60) -> dict:
    """POST a multipart form (a file plus text fields) and decode the reply."""
    content_type, body = encode_multipart(fields, file_field, filename, content)
    req = urllib.request.Request(
        f"{_comfyui_url}{path}",
        data=body,
        headers={"Content-Type": content_type, "Content-Length": str(len(body))},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise ConnectionError(
            f"ComfyUI rejected the upload with HTTP {e.code}"
            + (f": {detail}" if detail else "")
        )
    except urllib.error.URLError as e:
        raise _unreachable(e)
