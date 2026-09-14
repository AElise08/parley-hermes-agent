# Install The News

## Requirements

- macOS or Linux with Docker Desktop / Docker Engine and Docker Compose
- Git
- A Plow account and a Plow line for this agent
- The `plow-agents` CLI from https://github.com/plow-pbc/plow-agents

## 1. Clone

```bash
git clone https://github.com/AElise08/news-hermes-agent.git
cd news-hermes-agent
```

## 2. Create the Plow credential

For a first Plow setup:

```bash
plow-agents login --new-line
```

Then mint the credential for the line selected for this agent:

```bash
plow-agents mint <line-uid>
chmod 600 plow-credentials
```

`plow-agents mint` writes `./plow-credentials`. Never commit this file.

Before the Agent Index page has been registered, leave `AGENT_ID` out. After
registration, append its public id so the reporting service starts:

```bash
printf '\nAGENT_ID=news\n' >> plow-credentials
```

## 3. Build and start

```bash
docker compose up --build -d
docker compose logs -f agent
```

The named `agent-home` volume preserves Hermes sessions, the editable newspaper
config, generated editions, and the Agent Index install identity.

## 4. Generate an edition

Ask the agent in Plow Chat for today's edition, or run:

```bash
docker compose exec agent /opt/news/bin/generate-news
```

Outputs are written inside the persistent volume at:

```text
/var/lib/hermes/news/output/
```

Copy one to the host if needed:

```bash
docker compose cp agent:/var/lib/hermes/news/output/news-YYYY-MM-DD.pdf .
docker compose cp agent:/var/lib/hermes/news/output/news-YYYY-MM-DD.epub .
```

## 5. Customize

The first boot copies the default config to:

```text
/var/lib/hermes/news/config.json
```

Edit that persistent copy through the agent or with `docker compose exec`.
Rebuilding the image does not overwrite it. Validate edits with:

```bash
docker compose exec agent python3 -m json.tool /var/lib/hermes/news/config.json >/dev/null
```

## Stop or reset

```bash
docker compose down
```

To delete all persistent agent state and generated editions as well:

```bash
docker compose down -v
```
