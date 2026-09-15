#!/usr/bin/env python3
"""Parley bilingual TTS: pick the edge-tts voice by dominant reply language.

Usage: tts_bilingual.py <input_text_path> <output_audio_path>
PT-dominant -> pt-BR-ThalitaMultilingualNeural (handles embedded EN phrases)
EN-dominant -> en-US-AriaNeural
"""
import re
import sys

sys.path.insert(0, "/opt/data/lazy-packages")

PT_VOICE = "pt-BR-FranciscaNeural"
EN_VOICE = "en-US-AriaNeural"

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


def clean(text: str) -> str:
    text = re.sub(r"[*_`#]", "", text)
    return text.strip()


def main() -> int:
    raw = open(sys.argv[1], encoding="utf-8").read()
    text = clean(raw)
    if not text:
        return 1
    lang = dominant_language(text)
    voice = PT_VOICE if lang == "pt" else EN_VOICE
    import asyncio
    import subprocess
    import tempfile
    import edge_tts

    out = sys.argv[2]
    target = out if out.lower().endswith(".mp3") else out + ".src.mp3"

    async def synth():
        await edge_tts.Communicate(text, voice).save(target)

    asyncio.run(synth())
    if target != out:
        # iMessage renders audio/mp4 (.m4a, AAC) as a native voice-memo
        # bubble; transcode so the attachment matches that shape.
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", target,
             "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", out],
            check=True,
        )
    print(f"voice={voice} lang={lang}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
