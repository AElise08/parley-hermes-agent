# Parley

**A language tutor that lives in your iMessage thread.**

Install Parley, mint a Plow Chat line, and you get a phone number. Text it
from your iPhone like you'd text a friend — over **iMessage or SMS**. No app to
open, no browser tab, no Duolingo streak screen. The lesson is the
conversation.

Parley asks which language you want to practice, sets your level, and from then
on **every message you send is practice**. You write in the language you're
learning; Parley replies in-thread as a conversation partner, then shows a few
gentle corrections. Your mistakes are logged and come back on a spaced-review
schedule — yesterday's error becomes next week's question. Once a day, at your
practice hour, your phone buzzes with a starter you can answer in two
sentences.

First question, in the language you wrote in:

**Quer praticar qual idioma?**

## What a session looks like (iMessage)

```
You:    Yesterday I go to the market and buy some fruits.
Parley: Good topic! Small fixes:
        • "go" → went (past tense)
        • "buy" → bought
        Better: Yesterday I went to the market and bought some fruits.
        What did you pick up?
You:    I bought apples and bananas.
Parley: Perfect tense. 🍎 One note: "some fruits" → "some fruit" (uncountable).
        ...
```

You never leave Messages. Explanations can come in your native language;
practice stays in the target language. Optional: send a voice memo, get a voice
reply back as a native iMessage voice bubble.

## Use cases

- **Practice by texting on iMessage.** Open Messages, text your Plow line in
  the language you're learning. Parley replies at your CEFR level, on your
  topics (work, travel, faith — whatever you set). After each exchange it
  corrects at most three things: what you wrote, the better version, one line
  of why. Every correction is logged for review, whether or not it all fits on
  screen.
- **A daily nudge on your phone.** At your local practice hour (default 18:00),
  Parley texts you first — a starter question on your topics. Reply in two
  sentences from the couch, the bus, anywhere you already text. If a past
  mistake is due, it rides along as a quick review.
- **Your mistakes, reviewed in chat.** Text "review" or answer the nudge's
  review item. Parley asks how you'd say *your own* past error better — not
  generic drills. Right answers climb 1 → 3 → 7 → 14 → 30 days until they
  graduate; wrong ones come back tomorrow.
- **A level that moves with you.** CEFR A1–C2, set in a short placement chat
  over iMessage and adjusted when your sessions show real progress — never
  silently.

## Install

You need Git, Docker Compose, and **Python 3.10+** (the helper scripts use
3.10 syntax; the agent itself runs inside Docker).

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/AElise08/parley-hermes-agent.git
cd parley-hermes-agent

plow-agents login                 # text the printed “Plow Activate: …” code
plow-agents lines                 # pick a line whose STATUS is free
plow-agents mint ln_xxx           # writes ./plow-credentials — do this before the first up
docker compose up --build -d
docker compose logs -f agent      # wait for: plow-init: configured ... as cht_
```

If you have no assistant line yet: `plow-agents login --new-line`, then `lines`
and `mint`.

`plow-credentials` and `.env` are gitignored. Do not commit them.

## How to use it

After `plow-agents mint`, open **Messages** on your iPhone and text the number
on that line. That thread is your classroom.

1. **Setup (first texts).** Parley asks which language to practice and your
   rough level — all in iMessage. It saves a local profile on this machine
   (languages, goal, topics, level history). No Notion, no separate login.
2. **Practice (any time).** Send a message in the target language — about your
   day, a question, anything. Parley partners, then corrects. Keep the thread
   going like a chat with a tutor who texts back.
3. **Review (when you want).** Text `review` or answer the review line in the
   daily nudge. Parley quizzes you on your logged mistakes; your answer sets
   the next review date.
4. **Daily nudge** (default 18:00 in your timezone, UTC until you set one):
   Parley texts *you* first — one starter, one due mistake, your streak.

Set timezone in `tutor-settings.json` (`timezone`, IANA name) or with `TZ` in
`compose.override.yml`. The JSON value wins if both are set. Practice hour is
`practice_hour` in the same file, or `PARLEY_PRACTICE_HOUR` in the override.
Scaffolding language follows your native language (`locale`, or
`PARLEY_LOCALE`).

```sh
docker compose down          # stop, keep memory
docker compose down -v       # wipe local memory (new setup)
plow-agents revoke           # retire the line in plow-credentials
```

Your profile, sessions, and mistakes log live in the agent home volume
(`tutor-profile.json`, `.parley/`). Only on this install; `down -v` wipes them.

## Usage reporting

This image reports token usage to the [Agent Index](https://aiworthusing.com/agent-index)
once an hour: day × model counts, nothing else. The listing page (name, repo,
video) is **not** published by this boot — that is a separate step.

`AGENT_ID` defaults to `parley`.

## Tests

```sh
python3 -m unittest discover -s tests -q
```

## License

MIT. See [LICENSE](LICENSE). Built on the same architecture as
[Saved](https://github.com/AElise08/saved-hermes-agent) (MIT).

## Voice (optional, recommended)

Parley can answer voice memos in kind: your memo is transcribed locally
(faster-whisper, per-audio language auto-detect — never pin a language) and
the reply carries a synthesized voice note that renders as a native iMessage
voice bubble (AAC/m4a). `scripts/tts_bilingual.py` picks the voice by the
language being practiced — the profile's `target_language` — not by whichever
language dominates the reply: `pt-BR-ThalitaMultilingualNeural` for Portuguese,
`en-US-AvaMultilingualNeural` for English. Both are Microsoft *multilingual*
neural voices, so the other language's phrases are read with native
pronunciation and a Portuguese reply never comes out in an English accent just
because the surrounding explanation is in English. Voices are one-line changes
at the top of the script.

Setup (once, after the first boot): copy `scripts/tts_bilingual.py` to
`/var/lib/hermes/scripts/`, then run `patches/apply-live-patches.py` — it
prints the exact `config.yaml` block (STT auto-detect + whisper small,
`voice.auto_tts`, the bilingual TTS provider) and suppresses the gateway's
restart broadcast into the chat. On sandboxes where `/tmp` is outside
`HERMES_WRITE_SAFE_ROOT`, also export `TMPDIR=/var/lib/hermes/tmp` in the
gateway environment, or voice-note generation is silently denied.
