#!/usr/bin/env python3
"""Parley STT: detect the speaker's language, then keep a mixed pair.

Usage: stt_bilingual.py <input_audio> [output_transcript]

No profile yet: one auto-detect pass (French, Portuguese, English, …) so the
tutor can ask, in that language, what they want to learn.

After native + target are set: transcribe both and merge by time, so a memo
that switches mid-clip does not collapse to one language.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass

sys.path.insert(0, "/opt/data/lazy-packages")

PROFILE = os.environ.get("PARLEY_PROFILE", "/var/lib/hermes/tutor-profile.json")
MODEL_NAME = os.environ.get("PARLEY_STT_MODEL", "small")

PT_WORDS = re.compile(
    r"\b(voc[eê]|obrigad[ao]|est[áa]|tudo|qual|nome|prazer|ol[áa]|como|bem|"
    r"n[ãa]o|por favor|bom dia|boa tarde|boa noite|muito|agora|repita|diga|"
    r"frase|ingl[êe]s|portugu[êe]s|sou|s[ãa]o|sim|estou|meu|sua|seu|depois|"
    r"agora|hoje|ontem|amanh[ãa]|quero|preciso|vamos|aqui|ali|isso|esse)\b",
    re.I,
)
EN_WORDS = re.compile(
    r"\b(the|you|your|is|are|am|hello|hi|well|thank|please|name|how|what|"
    r"good|morning|say|now|try|means|listen|repeat|sentence|i'm|i am|then|"
    r"today|yesterday|tomorrow|want|need|let's|here|there|this|that)\b",
    re.I,
)
PT_CHARS = re.compile(r"[ãõçâêôáéíóúàèìòùüÃÕÇÂÊÔÁÉÍÓÚÀÈÌÒÙÜ]")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+")


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    lang: str


def profile_languages() -> tuple[str, ...]:
    """Native + target once the owner has a pair. Empty means auto-detect."""
    langs: list[str] = []
    try:
        with open(PROFILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    for key in ("native_language", "target_language"):
        code = str(data.get(key) or "").strip().lower()[:2]
        if code.isalpha() and code not in langs:
            langs.append(code)
    return tuple(langs[:3])


def language_fit(text: str, lang: str) -> float:
    words = WORD_RE.findall(text)
    if not words:
        return 0.0
    pt = 3 * len(PT_CHARS.findall(text)) + len(PT_WORDS.findall(text))
    en = len(EN_WORDS.findall(text))
    other = max(len(words) - (pt if lang == "pt" else en), 0)
    if lang == "pt":
        return (pt - 0.6 * en) / len(words)
    if lang == "en":
        return (en - 0.6 * pt) / len(words)
    return -0.2 * other / len(words)


def score(segment: Segment) -> float:
    return (
        float(segment.avg_logprob)
        - 0.5 * float(segment.no_speech_prob)
        + 0.35 * language_fit(segment.text, segment.lang)
    )


def covering(segments: list[Segment], t: float) -> list[Segment]:
    return [s for s in segments if s.start - 0.04 <= t < s.end + 0.04]


def merge_segments(passes: dict[str, list[Segment]]) -> str:
    """Pick the better language at each timestamp; emit each winning segment once."""
    all_segs = [s for segs in passes.values() for s in segs if s.text.strip()]
    if not all_segs:
        return ""
    bounds = sorted({round(s.start, 3) for s in all_segs} | {round(s.end, 3) for s in all_segs})
    chosen: list[Segment] = []
    last_id: int | None = None
    for start, end in zip(bounds, bounds[1:]):
        if end - start < 0.08:
            continue
        candidates = covering(all_segs, (start + end) / 2)
        if not candidates:
            continue
        best = max(candidates, key=score)
        if last_id != id(best):
            chosen.append(best)
            last_id = id(best)
    return " ".join(s.text.strip() for s in chosen if s.text.strip())


def _as_segment(raw: object, lang: str) -> Segment | None:
    text = str(getattr(raw, "text", "") or "").strip()
    if not text:
        return None
    try:
        start = float(getattr(raw, "start", 0.0) or 0.0)
        end = float(getattr(raw, "end", start) or start)
        avg = float(getattr(raw, "avg_logprob", -1.0) or -1.0)
        nospeech = float(getattr(raw, "no_speech_prob", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    return Segment(start, end, text, avg, nospeech, lang)


def transcribe_pass(model: object, audio_path: str, lang: str | None) -> tuple[list[Segment], str]:
    segments, info = model.transcribe(
        audio_path,
        language=lang,
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
    )
    detected = str(getattr(info, "language", "") or lang or "").strip().lower()[:2]
    out: list[Segment] = []
    tag = detected or (lang or "und")
    for raw in segments:
        item = _as_segment(raw, tag)
        if item is not None:
            out.append(item)
    return out, detected


def load_model(name: str) -> object:
    os.environ.setdefault("HF_HOME", "/var/lib/hermes/.cache/huggingface")
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8")


def format_transcript(text: str, detected: str = "") -> str:
    body = text.strip()
    if detected and body:
        return f"[lang:{detected}] {body}"
    return body


def transcribe_file(audio_path: str, languages: tuple[str, ...] | None = None) -> str:
    langs = list(languages) if languages is not None else list(profile_languages())
    model = load_model(MODEL_NAME)
    if not langs:
        segs, detected = transcribe_pass(model, audio_path, None)
        text = " ".join(s.text.strip() for s in segs if s.text.strip())
        return format_transcript(text, detected)
    passes = {}
    for lang in langs:
        segs, _detected = transcribe_pass(model, audio_path, lang)
        passes[lang] = segs
    return merge_segments(passes)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: stt_bilingual.py <input_audio> [output_transcript]", file=sys.stderr)
        return 2
    audio = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        text = transcribe_file(audio)
    except Exception as exc:  # noqa: BLE001 — command STT must not raise
        print(f"stt_bilingual failed: {exc}", file=sys.stderr)
        return 1
    if dest:
        with open(dest, "w", encoding="utf-8") as handle:
            handle.write(text)
            if text:
                handle.write("\n")
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if text.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
