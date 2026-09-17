# Setup

First run decides whose pair this is. Nothing is assumed.

1. `tutor.py setup-status`. If `ready` is true, tutor normally.
2. If languages are empty, notice the language they used (typed, or
   `[lang:xx]` from a voice memo). Ask in **that** language which one they
   want to practice, and roughly what level. One question, then wait.
   Examples: PT "Quer praticar qual idioma?"; EN "Which language do you want
   to practice?"; FR "Quelle langue veux-tu pratiquer ?". Do not assume
   Portuguese, English, or a country.
3. `tutor.py setup-local` once — it creates the profile and state files.
4. `tutor.py profile set --target en --native pt --goal "..." --topics "a, b, c"`
   with THEIR answers. Topics feed the daily starter, so use their real
   interests; three to five is plenty.
5. Level: if they stated one, `tutor.py level set --level B1 --reason "their
   estimate"`. If not, run a three-exchange placement (easy, medium, hard)
   and set it from that evidence. Placement is a chat, not a quiz form.
6. `tutor_config.py set-locale pt` or `en` — the native language, used for
   scaffolding and the daily nudge copy.

Timezone: if they mention where they live, write `timezone` (IANA name) into
`tutor-settings.json` and confirm the practice hour in their local time. The
JSON wins over container `TZ`. Do not infer a country from their languages —
a Portuguese speaker may live anywhere.
