# Official Plow Hermes base, pinned to the inspected public image release.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-ef4b30e00e74b4f2c47832acecfacb5eba717468@sha256:693ac5520ec0a2cabe8fc9de6a0c4827b79a7a0556228345aaf63664a001d7b4

USER root
COPY --chmod=0644 runtime/persona.md /opt/hermes/plow-seed/persona.md
COPY --chmod=0644 LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/news/
COPY --chmod=0644 requirements.txt /opt/news/requirements.txt
RUN /opt/hermes/.venv/bin/pip install --no-cache-dir -r /opt/news/requirements.txt
COPY --chmod=0644 app/ /opt/news/app/
COPY --chmod=0755 bin/generate-news /opt/news/bin/generate-news
COPY news/ /opt/hermes/skills/news/
RUN find /opt/hermes/skills/news -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills/news -type f -exec chmod 0644 {} +

# The reporter is vendored from plow-pbc/agent-index-client at the commit and
# checksum recorded in THIRD_PARTY_NOTICES.md. Tokens are supplied only at run time.
COPY --chmod=0644 vendor/agent_index_client.py /opt/plow/agent-index-client.py
COPY image/s6-overlay/ /etc/s6-overlay/
COPY --chmod=0755 image/cont-init.d/10-news /etc/cont-init.d/10-news

ENTRYPOINT []
CMD ["/init"]
