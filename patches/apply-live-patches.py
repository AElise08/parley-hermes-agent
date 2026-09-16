#!/usr/bin/env python3
"""Parley live patches, applied INSIDE a running install (not shipped baked in).

1. Suppresses the gateway's "Gateway shutting down" broadcast into user chats
   (log-only instead). A phone-chat tutor must not announce restarts.
   NOTE: a Hermes upgrade overwrites this; re-apply afterwards.
2. Prints the two operational settings the live install needs in config.yaml
   (auto voice replies + per-audio STT language auto-detect) and the TMPDIR
   export for sandboxes whose /tmp sits outside HERMES_WRITE_SAFE_ROOT.

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

# --- Plow chat voice notes ---------------------------------------------------
# A voice memo the owner sends arrives on the Plow wire named "Audio Message.m4a"
# with content_type audio/mp4. A reply synthesized by auto-TTS goes out named
# tts_reply_<hex>.m4a, and iMessage renders that as a plain audio attachment
# instead of a voice message. send_voice now mirrors the provider's own naming
# so the reply lands as a voice bubble.
PLOW_CHAT = "/opt/hermes/plugins/plow_chat/__init__.py"
VOICE_OLD = (
    "    async def send_voice(self, chat_id, audio_path, caption=None, **_kwargs):\n"
    "        return await self._send_attachment(chat_id, audio_path, caption=caption)\n"
)
VOICE_NEW = (
    "    async def send_voice(self, chat_id, audio_path, caption=None, **_kwargs):\n"
    "        # A received voice memo arrives named \"Audio Message.m4a\" with\n"
    "        # content_type audio/mp4; a generic filename/content_type is what\n"
    "        # renders as a plain audio file on iMessage. Mirror the shape the\n"
    "        # provider itself uses so the reply lands as a voice message.\n"
    "        ext = os.path.splitext(audio_path)[1] or \".m4a\"\n"
    "        return await self._send_attachment(\n"
    "            chat_id, audio_path, caption=caption,\n"
    "            filename=f\"Audio Message{ext}\")\n"
)
try:
    src = open(PLOW_CHAT).read()
except OSError as error:
    print(f"plow_chat: skipped ({error})")
else:
    if 'filename=f"Audio Message{ext}"' in src:
        print("plow_chat: already patched")
    elif VOICE_OLD in src:
        open(PLOW_CHAT, "w").write(src.replace(VOICE_OLD, VOICE_NEW, 1))
        print("plow_chat: voice notes now send as 'Audio Message.m4a'")
    else:
        print("plow_chat: anchor not found - Hermes version changed?")

print("""
config.yaml additions (plow-init owns its own keys; these survive restarts):

stt:
  language: ""          # empty restores per-audio auto-detect; the seeded
                        # default "en" silently decodes Portuguese as English
  local:
    model: small        # whisper small: best language-ID that fits 2GB RAM
voice:
  auto_tts: true        # voice replies to voice messages (reply-in-kind)
tts:
  provider: parley-bilingual
  providers:
    parley-bilingual:
      type: command
      command: "/opt/hermes/.venv/bin/python3 /var/lib/hermes/scripts/tts_bilingual.py {input_path} {output_path}"
      output_format: m4a   # AAC/m4a renders as a native iMessage voice memo

Also copy scripts/tts_bilingual.py to /var/lib/hermes/scripts/ (0755) and, on
sandboxes where /tmp is outside HERMES_WRITE_SAFE_ROOT, export
TMPDIR=/var/lib/hermes/tmp in the gateway environment.
""")
