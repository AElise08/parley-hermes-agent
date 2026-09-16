#!/usr/bin/env python3
"""Send one Plow Chat message without the live gateway adapter.

Hermes `--deliver plow_chat:...` fails out-of-process (no standalone_sender).
Text posts to /v1/chats/{uid}/messages. Voice memos use the same
declare/upload flow as media, then POST /v1/chats/{uid}/voicememo with
{"attachment_uid": "att…"} — MP3 or M4A, one file, no body text. The live
gateway's send_voice uses that route; this script is for the outbox.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def s6_value(name: str) -> str:
    path = Path("/run/s6/container_environment") / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def chat_id_from_config() -> str:
    path = hermes_home() / "config.yaml"
    if not path.exists():
        return ""
    in_home = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("home_channel:"):
            in_home = True
            continue
        if in_home and stripped.startswith("chat_id:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if in_home and stripped and not stripped.startswith("#") and not stripped.startswith("chat_id") and not stripped.startswith("platform"):
            in_home = False
    return ""


def credentials() -> tuple[str, str, str]:
    env: dict[str, str] = {}
    home = hermes_home()
    for path in (
        home / ".parley" / "plow.env",
        home / ".env",
        Path("/var/lib/plow/credentials"),
    ):
        env.update(load_dotenv(path))
    base = (
        os.environ.get("PLOW_API_BASE")
        or env.get("PLOW_API_BASE")
        or s6_value("PLOW_API_BASE")
    ).rstrip("/")
    token = (
        os.environ.get("PLOW_AGENT_TOKEN")
        or env.get("PLOW_AGENT_TOKEN")
        or s6_value("PLOW_AGENT_TOKEN")
    )
    uid = (
        os.environ.get("PLOW_HOME_CHANNEL")
        or env.get("PLOW_HOME_CHANNEL")
        or s6_value("PLOW_HOME_CHANNEL")
        or chat_id_from_config()
    )
    missing = [name for name, value in (("PLOW_API_BASE", base), ("PLOW_AGENT_TOKEN", token), ("PLOW_HOME_CHANNEL", uid)) if not value]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)} — cannot send Plow Chat")
    return base, token, uid


def _request(url: str, *, method: str, headers: dict[str, str], data: bytes | None = None, timeout: int = 60):
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Plow Chat HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Plow Chat network error: {exc.reason}") from exc


def _post_json(url: str, token: str, payload: dict, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8")
    _status, raw = _request(
        url,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=body,
        timeout=timeout,
    )
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def send(text: str) -> None:
    text = (text or "").strip()
    if not text or text == "[SILENT]":
        return
    base, token, uid = credentials()
    _post_json(f"{base}/v1/chats/{uid}/messages", token, {"body": text})


def _audio_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".mp3":
        return "audio/mpeg"
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "application/octet-stream"


def send_voice(path: str, caption: str = "") -> None:
    """Native iMessage voice memo: declare → upload → POST .../voicememo."""
    audio = Path(path)
    if not audio.is_file():
        raise SystemExit(f"voice file not found: {path}")
    data = audio.read_bytes()
    if not data:
        raise SystemExit("voice file is empty")
    suffix = audio.suffix.lower()
    if suffix not in (".m4a", ".mp3"):
        raise SystemExit("voice memo must be MP3 or M4A")
    base, token, uid = credentials()
    declared = _post_json(
        f"{base}/v1/chats/{uid}/attachments",
        token,
        {"filename": audio.name, "content_type": _audio_content_type(audio), "size_bytes": len(data)},
        timeout=60,
    )
    attachment_uid = declared.get("uid") or declared.get("attachment_uid")
    upload_url = declared.get("upload_url")
    upload_headers = declared.get("upload_headers") or {}
    if not attachment_uid or not upload_url:
        raise SystemExit("Plow Chat attachment declare returned no uid/upload_url")
    headers = {str(k): str(v) for k, v in upload_headers.items()}
    _request(upload_url, method="PUT", headers=headers, data=data, timeout=120)
    _post_json(f"{base}/v1/chats/{uid}/voicememo", token, {"attachment_uid": attachment_uid})
    caption = (caption or "").strip()
    if caption:
        send(caption)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Send a message to the owner's Plow Chat.")
    p.add_argument("text", nargs="?", default="", help="Message body")
    p.add_argument("--file", help="Read body from a file, or - for stdin")
    p.add_argument("--voice", help="Send a native iMessage voice memo (MP3 or M4A)")
    p.add_argument("--caption", default="", help="Optional text after a voice memo")
    return p


def main() -> int:
    args = parser().parse_args()
    if args.voice:
        send_voice(args.voice, caption=args.caption)
        return 0
    if args.file:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text or sys.stdin.read()
    send(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
