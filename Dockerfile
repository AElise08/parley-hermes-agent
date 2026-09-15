# Parley: a Plow Chat Hermes agent that tutors a language over iMessage —
# daily practice, gentle corrections, spaced review of your own mistakes.
#
# Pinned by digest, same pattern as plow-pbc/life-assistant-hermes-agent:
# a moving tag would substitute unreviewed code under a live credential.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-db182f335c727469d7de4eaf25b5d333670b3069@sha256:bb2308bc96acd564b9ea0e9b8b577f19f39d6bb96173f29761f24297817d38ed

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
RUN chmod 0755 /etc/cont-init.d/20-parley-seed
