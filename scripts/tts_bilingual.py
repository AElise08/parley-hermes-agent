#!/usr/bin/env python3
"""Parley bilingual TTS: speak the language being practiced in its own voice.

Usage: tts_bilingual.py <input_text_path> <output_audio_path>

The voice is chosen by the profile's ``target_language`` (the language the
owner is learning), not by whichever language dominates the reply text: a
tutor's Portuguese must sound Portuguese even when the surrounding
explanation is English, and vice versa. Both voices are Microsoft
*Multilingual* neural voices, which read the other language's phrases with
native pronunciation, so one voice covers a mixed reply correctly.

Voices are keyed by ISO code (`en`, `de`, `ja`, `pt`, `fr`, …). Unknown
codes fall back to Ava multilingual, which can speak many languages.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/opt/data/lazy-packages")

PROFILE = os.environ.get("PARLEY_PROFILE", "/var/lib/hermes/tutor-profile.json")
VOICES = {
    "en": "en-US-AvaMultilingualNeural",
    "pt": "pt-BR-ThalitaMultilingualNeural",
    "de": "de-DE-SeraphinaMultilingualNeural",
    "fr": "fr-FR-VivienneMultilingualNeural",
    "es": "es-ES-ArabellaMultilingualNeural",
    "it": "it-IT-IsabellaNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "zh": "zh-CN-XiaoxiaoMultilingualNeural",
    "nl": "nl-NL-FennaNeural",
    "pl": "pl-PL-ZofiaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
    "sv": "sv-SE-SofieNeural",
    "tr": "tr-TR-EmelNeural",
}

PT_WORDS = re.compile(
    r"\b(voc[eê]|obrigad[ao]|est[áa]|tudo|qual|nome|prazer|ol[áa]|como|bem|"
    r"n[ãa]o|por favor|bom dia|boa tarde|boa noite|muito|agora|repita|diga|"
    r"frase|ingl[êe]s|portugu[êe]s|sou|s[ãa]o|sim|estou|meu|sua|seu)\b", re.I)
EN_WORDS = re.compile(
    r"\b(the|you|your|is|are|am|hello|hi|well|thank|please|name|how|what|"
    r"good|morning|say|now|try|means|listen|repeat|sentence|i'm|i am)\b", re.I)
PT_CHARS = re.compile(r"[ãõçâêôáéíóúÃÕÇÂÊÔÁÉÍÓÚ]")


def dominant_language(text: str) -> str:
    pt = 3 * len(PT_CHARS.findall(text)) + len(PT_WORDS.findall(text))
    en = len(EN_WORDS.findall(text))
    return "pt" if pt >= en else "en"


def target_language() -> str:
    try:
        with open(PROFILE, encoding="utf-8") as handle:
            return str(json.load(handle).get("target_language") or "").strip().lower()
    except (OSError, ValueError):
        return ""


def choose_voice(text: str) -> tuple[str, str]:
    target = target_language()
    if target in VOICES:
        return VOICES[target], target
    if target:
        code = target[:2]
        if code in VOICES:
            return VOICES[code], code
        return VOICES["en"], code
    lang = dominant_language(text)
    return VOICES.get(lang, VOICES["en"]), lang


def clean(text: str) -> str:
    text = re.sub(r"[*_`#]", "", text)
    return text.strip()


def main() -> int:
    raw = open(sys.argv[1], encoding="utf-8").read()
    text = clean(raw)
    if not text:
        return 1
    voice, lang = choose_voice(text)
    import asyncio
    import subprocess
    import tempfile
    import edge_tts

    out = sys.argv[2]

    async def synth(path: str) -> None:
        await edge_tts.Communicate(text, voice).save(path)

    if out.lower().endswith(".mp3"):
        asyncio.run(synth(out))
    else:
        # Edge TTS only emits MP3. Transcode to AAC/m4a — the shape an
        # iMessage voice memo must have — through a private temp file, so no
        # stray ``.src.mp3`` is left beside the deliverable.
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "tts.mp3")
            asyncio.run(synth(source))
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", source,
                 "-c:a", "aac", "-b:a", "64k", "-ar", "44100",
                 "-movflags", "+faststart", out],
                check=True,
            )
    print(f"voice={voice} lang={lang}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
