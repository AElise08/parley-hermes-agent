# Daily practice and review

Two scheduled behaviors, both driven by `outbox.py drain` every five minutes:

- Due outbox items send when their time passes.
- The daily nudge fires once inside the local window: the hour in
  `tutor-settings.json` (`practice_hour`, default 18) plus
  `practice_window_minutes` (default 10). A stamp file prevents a second send
  the same day. `daily_practice.py` builds the message from
  `tutor.py digest-prompt`: a starter rotated across the owner's topics at
  their level, plus the oldest due mistake as a quick review, plus their
  practice streak when it is past one day.

Force a test send with `outbox.py daily`.

## Review mechanics

`tutor.py review due` returns mistakes whose `next_due` has passed, oldest
first. Ask one as a question, wait for the answer, then
`tutor.py review grade --id ... --result good|bad`:

- good: streak + 1, next due after 1, 3, 7, 14, 30 days by rung; at the top
  rung the item graduates and leaves `error list`.
- bad: streak resets, it comes back tomorrow.

Show the better version after grading. When a daily nudge carries a review
item, grade their reply against `expected` — close is good at A1–B1, exact
register only counts at C1+.

## Session notes

At the end of a real exchange, `tutor.py session note --summary "..."` with
what they practiced and how it went. These notes are the evidence behind level
changes; a level set without evidence is a guess.
