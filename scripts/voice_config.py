#!/usr/bin/env python3
"""Seed native iMessage voice: STT auto-detect, auto_tts, bilingual command TTS.

plow-init owns provider keys; this only adds voice/stt/tts and leaves the rest.
Safe to run on every boot — existing values for language/model/auto_tts win
unless they are still the silent-English defaults that break Portuguese memos.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

TTS_COMMAND = (
    "/opt/hermes/.venv/bin/python3 /var/lib/hermes/scripts/tts_bilingual.py "
    "{input_path} {output_path}"
)


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))


def apply(path: Path | None = None) -> dict:
    config_path = path or (hermes_home() / "config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}

    stt = cfg.setdefault("stt", {})
    if not isinstance(stt, dict):
        stt = {}
        cfg["stt"] = stt
    # Empty restores per-audio auto-detect. The seeded default "en" silently
    # decodes Portuguese memos as English.
    if stt.get("language") in (None, "en"):
        stt["language"] = ""
    local = stt.setdefault("local", {})
    if not isinstance(local, dict):
        local = {}
        stt["local"] = local
    local.setdefault("model", "small")

    voice = cfg.setdefault("voice", {})
    if not isinstance(voice, dict):
        voice = {}
        cfg["voice"] = voice
    voice["auto_tts"] = True

    tts = cfg.setdefault("tts", {})
    if not isinstance(tts, dict):
        tts = {}
        cfg["tts"] = tts
    providers = tts.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        tts["providers"] = providers
    providers["parley-bilingual"] = {
        "type": "command",
        "command": TTS_COMMAND,
        "output_format": "m4a",
    }
    tts["provider"] = "parley-bilingual"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg


def main() -> int:
    apply()
    print("parley-voice: stt auto-detect, auto_tts, bilingual m4a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
