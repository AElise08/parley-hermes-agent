# Outbound messages

Never use `hermes cron --deliver plow_chat` or `hermes send --to plow_chat`
outside the live gateway. They do not reach the owner.

- Now: `python3 /var/lib/hermes/scripts/send_chat.py "text"` or `--file`.
- Voice: `python3 /var/lib/hermes/scripts/send_chat.py --voice /path/to/note.m4a`
  (native iMessage memo: declare/upload, then `POST .../voicememo`).
- Later: `python3 /var/lib/hermes/scripts/outbox.py add --at "2026-09-15T09:00:00" --text "..." --reason "..."`
- Later: `python3 /var/lib/hermes/scripts/outbox.py add --at "2026-09-15T09:00:00" --text "..." --reason "..."`
  Timestamps without an offset are read in the owner's timezone from
  `tutor-settings.json`.
- The drain runs every five minutes from the image copy at
  `/opt/parley/scripts/outbox.py`, which also fires the daily practice nudge.

`send_chat.py` reads PLOW_API_BASE / PLOW_AGENT_TOKEN from the environment or
`/var/lib/hermes/.parley/plow.env`, and the chat id from the container
environment or `config.yaml`. Never print the token.
