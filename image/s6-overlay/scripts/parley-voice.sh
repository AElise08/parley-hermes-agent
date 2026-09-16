#!/bin/sh
# After plow-init has written provider keys, turn on native iMessage voice.
# hermes-gateway depends on this oneshot so the first turn already auto-TTS.
set -eu
HOME=/var/lib/hermes
install -d -o 10000 -g 10000 -m 0755 "$HOME/tmp"
/command/s6-setuidgid hermes \
  env HOME="$HOME" HERMES_HOME="$HOME" TMPDIR="$HOME/tmp" \
  /opt/hermes/.venv/bin/python3 /opt/parley/scripts/voice_config.py
