# The News

A Plow Hermes agent that turns live public feeds into a quiet, designed daily
newspaper. Each run produces both a print-ready PDF and a reflowable EPUB for
Kindle or other readers.

The default edition includes Portuguese and English news, science and tech,
positive stories, weather, study cards, a word search, and a comic. Its JSON
configuration controls sources, location, sections, study material, and topic
filters without changing the generator.

## What makes it a Hermes agent

- Built on the official `plow-pbc/plow-hermes-agent` base image
- Runs through the base image's supervised Hermes gateway and Plow Chat channel
- Ships a Hermes skill that knows how to generate and customize the paper
- Keeps config, outputs, sessions, and reporting identity in the Hermes volume
- Bakes in the official standard-library Agent Index client
- Reports Hermes token totals from `$HERMES_HOME/state.db` every five minutes
  after an Agent Index id is configured

No credential is stored in the image or repository.

## Quick start

See [docs/INSTALL.md](docs/INSTALL.md) for the full tutorial.

```bash
git clone https://github.com/AElise08/news-hermes-agent.git
cd news-hermes-agent
plow-agents login --new-line   # first setup only
plow-agents mint <line-uid>
docker compose up --build -d
```

Then ask in Plow Chat: `Make today's edition.`

Manual generation:

```bash
docker compose exec agent /opt/news/bin/generate-news
```

## Agent Index reporting

The image contains the official client from:
https://github.com/plow-pbc/agent-index-client

It reads Hermes usage from `/var/lib/hermes/state.db`. The supervised service
stands down while `AGENT_ID` is absent. Register the public page first using the
commands in [PUBLISHING.md](PUBLISHING.md), then add `AGENT_ID=news` to
`plow-credentials` and restart. The report client sends day-by-model token
counts, not prompts or task text.

## Project layout

```text
app/                         Newspaper generator, config, and font
bin/generate-news            Stable command used by the Hermes skill
runtime/persona.md           Agent-specific identity
news/SKILL.md       Hermes behavior and operating instructions
image/                       First-boot seed and supervised reporter
vendor/agent_index_client.py Official pinned Agent Index client
compose.yml                  Local Docker Compose deployment
docs/INSTALL.md              Step-by-step install tutorial
```

## Development checks

```bash
python3 -m py_compile app/odiario.py
python3 -m json.tool app/config.json >/dev/null
python3 vendor/agent_index_client.py --self-check
python3 -m unittest discover -s tests -v
docker compose config -q
docker build -t news-hermes-agent .
```

A generation run fetches live feeds and therefore needs outbound network access.

## Privacy and safety

Feed and article content is treated as untrusted data. The bundled skill does
not execute instructions found in fetched content. Plow credentials are mounted
at run time and excluded from Git and Docker build context.

## License

The repository's original code is MIT licensed. Bodoni Moda is under the SIL
Open Font License 1.1. The Agent Index client and base image retain their own
licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
