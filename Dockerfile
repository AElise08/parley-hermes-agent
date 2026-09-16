# Parley: a Plow Chat Hermes agent that tutors a language over iMessage —
# daily practice, gentle corrections, spaced review of your own mistakes.
#
# Pinned by digest, same pattern as plow-pbc/life-assistant-hermes-agent:
# a moving tag would substitute unreviewed code under a live credential.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-910b8e3ba8980e20faae9f37dcaca0ea9d8bd9ae@sha256:f4739b6e74309dcccd087792949fd613191db7f33d33109c78127684dcb5dd73

COPY runtime/SOUL.md /var/lib/hermes/SOUL.md
COPY LICENSE NOTICE /usr/share/doc/parley/

# Bundled skill: the base runtime reconciles /opt/hermes/skills into the home.
COPY skills/parley/ /opt/hermes/skills/parley/

RUN find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f ! -perm -u+x -exec chmod 0644 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f -perm -u+x -exec chmod 0755 {} + \
 && chmod 0644 /var/lib/hermes/SOUL.md

# Root-owned scripts the daily drain runs. The home copy is what the agent
# reads during a turn; scheduling that copy would run whatever a turn last
# wrote, unattended, with the chat credential.
COPY scripts/ /opt/parley/scripts/
COPY templates/ /opt/parley/templates/
RUN chown -R root:root /opt/parley \
 && find /opt/parley -type d -exec chmod 0755 {} + \
 && find /opt/parley -type f -exec chmod 0644 {} + \
 && chmod 0755 /opt/parley/scripts/*.py

# Agent Index usage reporter, fetched from the commit vendor/client.pin names
# and checked against the hash beside it. Same pin as life-assistant.
COPY vendor/client.pin /opt/plow/agent-index-client.pin
RUN set -eu; \
    sha="$(sed -n 's/^sha=//p' /opt/plow/agent-index-client.pin)"; \
    want="$(sed -n 's/^sha256=//p' /opt/plow/agent-index-client.pin)"; \
    path="$(sed -n 's/^path=//p' /opt/plow/agent-index-client.pin)"; \
    curl -fsS --max-time 60 -o /opt/plow/agent-index-client.py \
      "https://raw.githubusercontent.com/plow-pbc/agent-index-client/${sha}/${path}"; \
    got="$(sha256sum /opt/plow/agent-index-client.py | cut -d' ' -f1)"; \
    [ "$got" = "$want" ] || { echo "agent-index client is $got, pin says $want" >&2; exit 1; }; \
    chmod 0644 /opt/plow/agent-index-client.py

COPY image/s6-overlay/ /etc/s6-overlay/
COPY image/cont-init.d/20-parley-seed /etc/cont-init.d/20-parley-seed
RUN chmod 0755 /etc/cont-init.d/20-parley-seed \
 && chmod 0755 /etc/s6-overlay/scripts/parley-voice.sh

# Voice memos: bilingual TTS (edge-tts) + a tmp dir inside HERMES_WRITE_SAFE_ROOT.
# The gateway's send_voice uses POST /v1/chats/{uid}/voicememo (native iMessage).
ENV TMPDIR=/var/lib/hermes/tmp
RUN /opt/hermes/.venv/bin/python -c "import edge_tts" \
 || uv pip install --python /opt/hermes/.venv/bin/python edge-tts

# Gemini 400s the whole turn if one tool has anyOf[string,array] plus sibling
# items (plow_send_message `to`). Move items onto the array branch.
COPY patches/gemini_items.py patches/fix_gemini_schema.py /tmp/parley-patches/
RUN python3 /tmp/parley-patches/fix_gemini_schema.py /opt/hermes/agent/gemini_schema.py
