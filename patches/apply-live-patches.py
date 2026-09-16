#!/usr/bin/env python3
"""Parley live patches, applied INSIDE a running install (not shipped baked in).

Voice (STT auto-detect, auto_tts, bilingual m4a) is baked into the image via
`voice_config.py` / the parley-voice oneshot. Do not copy those keys from here.
Native iMessage voice bubbles go through Hermes send_voice →
POST /v1/chats/{uid}/voicememo; no filename workaround.

This script only suppresses the gateway's "Gateway shutting down" broadcast
into user chats (log-only instead). A phone-chat tutor must not announce
restarts. NOTE: a Hermes upgrade overwrites this; re-apply afterwards.

Usage: python3 patches/apply-live-patches.py [path-to-run.py]
"""
import sys

RUN_PY = sys.argv[1] if len(sys.argv) > 1 else "/opt/hermes/gateway/run.py"

OLD = """        active = self._snapshot_running_agents()
        restart_source = self._restart_command_source if self._restart_requested else None"""
NEW = """        active = self._snapshot_running_agents()
        restart_source = self._restart_command_source if self._restart_requested else None

        # Parley deployment: lifecycle notices are log-only. A phone-chat
        # tutor must not broadcast gateway restarts into the user's chat.
        logger.info("shutdown notice suppressed for %d active session(s)", len(active))
        return"""

src = open(RUN_PY).read()
if NEW in src:
    print("run.py: already patched")
else:
    assert OLD in src, "run.py anchor not found - Hermes version changed?"
    open(RUN_PY, "w").write(src.replace(OLD, NEW, 1))
    print("run.py: lifecycle notices set to log-only")
