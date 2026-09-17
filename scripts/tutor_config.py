#!/usr/bin/env python3
"""Owner-specific Parley settings: timezone, daily practice window, languages.

Nothing here assumes a country, a level, or a goal. Those belong in
tutor-profile.json after the owner says so in chat.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from send_chat import hermes_home

SETTINGS_NAME = "tutor-settings.json"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def settings_path() -> Path:
    return hermes_home() / SETTINGS_NAME


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def timezone_name(data: dict | None = None) -> str:
    data = data if data is not None else load_settings()
    # Owner JSON wins. Compose often exports TZ=UTC, which would otherwise
    # ignore a timezone saved in chat.
    name = (str(data.get("timezone") or "").strip() or os.environ.get("TZ") or "UTC").strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return name or "UTC"


def zone(data: dict | None = None) -> ZoneInfo:
    return ZoneInfo(timezone_name(data))


def practice_hour(data: dict | None = None) -> int:
    data = data if data is not None else load_settings()
    try:
        value = int(os.environ.get("PARLEY_PRACTICE_HOUR") or data.get("practice_hour", 18))
    except (TypeError, ValueError):
        value = 18
    return value if 0 <= value <= 23 else 18


def practice_window_minutes(data: dict | None = None) -> int:
    data = data if data is not None else load_settings()
    try:
        value = int(data.get("practice_window_minutes", 10))
    except (TypeError, ValueError):
        value = 10
    return value if 1 <= value <= 59 else 10


LOCALE_ALIASES = {
    "english": "en", "german": "de", "deutsch": "de", "portuguese": "pt",
    "portugues": "pt", "português": "pt", "french": "fr", "francais": "fr",
    "français": "fr", "spanish": "es", "espanol": "es", "español": "es",
    "italian": "it", "italiano": "it", "japanese": "ja", "korean": "ko",
    "chinese": "zh", "mandarin": "zh", "dutch": "nl", "russian": "ru",
    "arabic": "ar", "hindi": "hi", "swedish": "sv", "turkish": "tr",
    "polish": "pl", "ukrainian": "uk",
}


def normalize_locale(value: str | None) -> str | None:
    """ISO 639-1 (en, de, ja, …) or a common language name. Not just pt/en."""
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    if raw in LOCALE_ALIASES:
        return LOCALE_ALIASES[raw]
    if "-" in raw:
        raw = raw.split("-", 1)[0]
    if raw in {"cmn", "zh"}:
        return "zh"
    if len(raw) == 2 and raw.isalpha():
        return raw
    return None


def locale(data: dict | None = None) -> str:
    """Scaffolding language: the owner's native language, used for explanations."""
    data = data if data is not None else load_settings()
    return normalize_locale(os.environ.get("PARLEY_LOCALE") or data.get("locale")) or "en"


def write_settings(updates: dict) -> dict:
    data = load_settings()
    data.update(updates)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def set_locale(value: str) -> dict:
    loc = normalize_locale(value)
    if loc is None:
        raise ValueError("locale must be an ISO language code (en, de, pt, ja, …)")
    return write_settings({"locale": loc})


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Read or write this owner's Parley settings.")
    sub = parser.add_subparsers(dest="command", required=True)
    sl = sub.add_parser("set-locale", help="ISO code (en, de, pt, ja, …) — native language, for scaffolding")
    sl.add_argument("locale")
    sub.add_parser("show", help="Print timezone, practice hour, and locale")
    args = parser.parse_args()
    if args.command == "set-locale":
        try:
            data = set_locale(args.locale)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "locale": data.get("locale")}, ensure_ascii=False))
        return 0
    settings = load_settings()
    print(json.dumps({
        "timezone": timezone_name(settings),
        "practice_hour": practice_hour(settings),
        "locale": locale(settings),
        "path": str(settings_path()),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
