#!/usr/bin/env python3
"""Format the daily practice nudge for Plow Chat delivery.

One conversation starter in the target language, sized to the owner's level,
plus one review question when a mistake is due. The starter topic comes from
the owner's profile; the review item comes from their own mistakes log.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from send_chat import send
from tutor_config import locale

SCRIPT = Path(__file__).with_name("tutor.py")

LANG_NAMES = {
    "en": {"en": "English", "pt": "inglês", "de": "Englisch", "es": "inglés", "fr": "anglais"},
    "pt": {"en": "Portuguese", "pt": "português", "de": "Portugiesisch", "es": "portugués"},
    "es": {"en": "Spanish", "pt": "espanhol", "de": "Spanisch", "es": "español"},
    "fr": {"en": "French", "pt": "francês", "de": "Französisch", "es": "francés"},
    "de": {"en": "German", "pt": "alemão", "de": "Deutsch", "es": "alemán"},
    "it": {"en": "Italian", "pt": "italiano", "de": "Italienisch"},
    "ja": {"en": "Japanese", "pt": "japonês", "de": "Japanisch"},
    "ko": {"en": "Korean", "pt": "coreano", "de": "Koreanisch"},
    "zh": {"en": "Chinese", "pt": "chinês", "de": "Chinesisch"},
    "nl": {"en": "Dutch", "pt": "holandês", "de": "Niederländisch"},
    "ru": {"en": "Russian", "pt": "russo", "de": "Russisch"},
}


def lang_name(code: str, scaffolding: str) -> str:
    return (LANG_NAMES.get(code) or {}).get(scaffolding) or code


COPY = {
    "en": {
        "title": "Parley — today's practice",
        "no_setup": "Parley is not set up yet — pick a language first.",
        "starter_fallback": "Tell me about your day.",
        "review_intro": "Quick review first — how would you say this better?",
        "reply_hint": "Answer in {target} — a couple of sentences is enough.",
        "streak": "{n} day(s) in a row.",
    },
    "pt": {
        "title": "Parley — treino de hoje",
        "no_setup": "O Parley ainda não tá configurado — escolhe um idioma primeiro.",
        "starter_fallback": "Me conta como foi o seu dia.",
        "review_intro": "Revisão rápida antes — como você diria isso melhor?",
        "reply_hint": "Responde em {target} — duas frases já tá ótimo.",
        "streak": "{n} dia(s) seguido(s).",
    },
}

STARTERS = {
    "en": {
        "A1": "What did you eat today?",
        "A2": "What was the best part of your day today?",
        "B1": "What did you work on today, and how did it go?",
        "B2": "What took most of your attention today? Was it worth it?",
        "C1": "What did you change your mind about today, if anything?",
        "C2": "What idea from today deserves more of your time this week?",
    },
    "pt": {
        "A1": "O que você comeu hoje?",
        "A2": "Qual foi a melhor parte do seu dia?",
        "B1": "No que você trabalhou hoje? Como foi?",
        "B2": "O que tomou mais da sua atenção hoje? Valeu a pena?",
        "C1": "Você mudou de ideia sobre alguma coisa hoje?",
        "C2": "Que ideia de hoje merece mais tempo seu essa semana?",
    },
}

TOPIC_STARTERS = {
    "writing": "If today were the first paragraph of an essay, what would it say?",
    "faith": "What are you grateful for today, and why that thing?",
    "tech": "What did you build or debug today?",
    "music": "What song is stuck in your head today? What is it about?",
    "films": "Seen anything good lately? Sell it to me in two sentences.",
    "books": "What are you reading now? Would you recommend it?",
}


def main() -> int:
    scaffolding = locale()
    text = COPY.get(scaffolding, COPY["en"])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "digest-prompt"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return proc.returncode
    data = json.loads(proc.stdout)
    if not data.get("ready"):
        print(text["no_setup"])
        print("[SILENT]")
        return 0

    target = data.get("target_language") or "en"
    level = data.get("level") or "B1"
    topic = (data.get("topic") or "").lower()
    starter = TOPIC_STARTERS.get(topic) or STARTERS.get(target, STARTERS["en"]).get(level) or text["starter_fallback"]

    lines = [text["title"]]
    streak = int((data.get("streak") or {}).get("streak_days") or 0)
    if streak > 1:
        lines.append(text["streak"].format(n=streak))
    lines.append("")
    review_item = data.get("review_item")
    if review_item:
        lines.append(text["review_intro"])
        lines.append(f"\"{review_item['prompt']}\"")
        lines.append("")
    lines.append(starter)
    lines.append("")
    lines.append(text["reply_hint"].format(target=lang_name(target, scaffolding)))
    message = "\n".join(lines).rstrip()
    send(message)
    print(f"sent {len(message)} chars to plow chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
