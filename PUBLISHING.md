# Publish and register

Do these steps only after adding the final screenshot, YouTube demo, GitHub
owner, and public install tutorial URL.

## 1. Final assets

Repository owner is `AElise08`. Verify no placeholders remain:

```bash
grep -R "OWNER" -n README.md docs app
```

Commit a public screenshot, or host it at a stable public HTTPS URL. Upload the
demo to YouTube and keep the video id from the URL, not the full URL.

## 2. Push the public repository

Create an empty public repository named `news-hermes-agent` in GitHub.
From this directory, initialize and push the package:

```bash
git init
git add .
git commit -m "Initial The News Hermes agent"
git branch -M main
git push -u https://github.com/AElise08/news-hermes-agent.git main
```

If the GitHub CLI is already authenticated, it can create and push in one step:

```bash
gh repo create AElise08/news-hermes-agent --public --source=. --push
```

## 3. Register on Agent Index

Make sure the running container has `PLOW_AGENT_TOKEN`, then run the bundled
client in that same container. Replace all angle-bracket placeholders:

```bash
docker compose exec agent /opt/hermes/.venv/bin/python3 /opt/plow/agent-index-client.py \
  --register \
  --agent news \
  --name "The News" \
  --blurb "Turns live public feeds into a calm daily newspaper in PDF and EPUB." \
  --repo "https://github.com/AElise08/news-hermes-agent" \
  --runtime "Hermes" \
  --video "<youtube-video-id>" \
  --image "<public-screenshot-https-url>" \
  --install-url "https://github.com/AElise08/news-hermes-agent/blob/main/docs/INSTALL.md"
```

`--video` accepts the YouTube id only. `--install-url` and `--image` must be
public HTTPS URLs.

## 4. Turn on recurring usage reports

Append the same Agent Index id to the credential file and restart:

```bash
printf '\nAGENT_ID=news\n' >> plow-credentials
docker compose up -d --force-recreate agent
docker compose logs -f agent
```

Check registration and preview a report without sending:

```bash
docker compose exec agent /opt/hermes/.venv/bin/python3 /opt/plow/agent-index-client.py status
docker compose exec agent /opt/hermes/.venv/bin/python3 /opt/plow/agent-index-client.py --agent news --dry-run
```
