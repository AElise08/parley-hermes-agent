# Parley

Text it in the language you're learning. Parley texts back — as a conversation
partner first, then with a few gentle corrections — and keeps your own mistakes
on a spaced-review ladder so yesterday's error comes back as next week's
question. Once a day it starts a conversation you can answer in two sentences.

Language tutors are built on WhatsApp by the dozen. Parley lives where your
messages already are: your Plow Chat line, over iMessage or SMS.

First question, in the language you wrote in:

**Quer praticar qual idioma?**

## Use cases

- **Practice by texting.** Chat in the language you're learning. Parley
  replies at your level, then corrects at most three things — what you wrote,
  the better version, one line of why. Every correction is logged, shown or
  not.
- **One question a day.** Every day at your local practice hour it texts a
  starter on your topics — answer it in two sentences and you're practicing.
  A due mistake rides along as a quick review.
- **Your mistakes, reviewed.** Review asks how you'd say your own past errors
  better. Right answers climb 1, 3, 7, 14, 30 days until they graduate; wrong
  ones come back tomorrow.
- **A level that moves.** CEFR A1–C2, set from a placement chat and adjusted
  on evidence from your sessions — never silently.

## Install

You need Git, Docker Compose, and **Python 3.10+** (the helper scripts use
3.10 syntax; the agent itself runs inside Docker).

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/AElise08/news-hermes-agent.git
cd news-hermes-agent

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

Text the line you minted.

1. **Pick your pair** (first messages). Parley asks which language you want
   to practice and your rough level. It sets up a local profile on this
   machine — languages, goal, your interest topics, level history. No Notion,
   no external account.
2. **Practice.** Text in the target language. Parley replies as a partner,
   then corrects a little. Explanations come in your native language; practice
   stays in the target one.
3. **Review.** Say "review" or answer the daily nudge's review item. Grade by
   answering; Parley schedules the next round.
4. **Daily nudge** (default 18:00 in your timezone, UTC until you set one):
   one starter, one due mistake, your streak.

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
reply's dominant language — `pt-BR-FranciscaNeural` for Portuguese,
`en-US-AriaNeural` for English — so a Portuguese explanation with an embedded
English practice phrase sounds right. Voices are one-line changes at the top
of the script.

Setup (once, after the first boot): copy `scripts/tts_bilingual.py` to
`/var/lib/hermes/scripts/`, then run `patches/apply-live-patches.py` — it
prints the exact `config.yaml` block (STT auto-detect + whisper small,
`voice.auto_tts`, the bilingual TTS provider) and suppresses the gateway's
restart broadcast into the chat. On sandboxes where `/tmp` is outside
`HERMES_WRITE_SAFE_ROOT`, also export `TMPDIR=/var/lib/hermes/tmp` in the
gateway environment, or voice-note generation is silently denied.
