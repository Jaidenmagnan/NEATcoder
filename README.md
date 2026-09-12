# NEATcoder

NEATcoder is a GitHub App webhook service that reviews pull requests against repository
guidelines stored in `.github/neat.md`. It places high-confidence findings directly on
changed code and maintains a concise scorecard on the pull request.

## Local setup

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/uvicorn neatcoder.api:app --reload
```

Unit tests do not need GitHub credentials:

```bash
.venv/bin/pytest
```

## GitHub App setup

Create a GitHub App with these repository permissions: **Contents: read**, **Pull requests:
read and write**, and **Checks: write**. Subscribe to the **Pull request** webhook event.
For development, expose `POST /webhooks/github` through a secure tunnel and set its URL as
the app webhook URL. For a persistent endpoint, see [Deploy on Google Cloud](#deploy-on-google-cloud).

### Test webhooks locally

1. Start the application in one terminal:

   ```bash
   .venv/bin/uvicorn neatcoder.api:app --reload
   ```

2. In a second terminal, expose the local server:

   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

   The command prints a public URL similar to
   `https://example-name.trycloudflare.com`.

3. In the GitHub App settings, set **Webhook URL** to that public URL followed by the
   webhook path:

   ```text
   https://example-name.trycloudflare.com/webhooks/github
   ```

4. Set **Webhook secret** in GitHub to the same value as `NEATCODER_WEBHOOK_SECRET` in
   `.env`, save the app settings, and trigger a pull-request event in a sandbox repository.

Keep both terminal processes running while testing. The Quick Tunnel URL changes every time
you start `cloudflared`, so update the GitHub App webhook URL when it changes.

## Deploy on Google Cloud

Google Cloud Run provides a stable HTTPS endpoint, so a tunnel is unnecessary. This repository
includes a `Procfile` that starts Uvicorn on Cloud Run's required `PORT`.

1. Create or select a Google Cloud project with billing enabled, then open Cloud Shell or use
   a local installation of the Google Cloud CLI. Select a region near you, such as
   `us-central1`.

2. In Secret Manager, create these three secrets. Store the complete PEM file contents,
   including its BEGIN/END lines, in the private-key secret.

   - `neatcoder-github-app-id`
   - `neatcoder-github-private-key`
   - `neatcoder-webhook-secret`

3. Deploy the checked-out repository from its root directory:

   ```bash
   gcloud run deploy neatcoder \
     --source . \
     --region us-central1 \
     --allow-unauthenticated \
     --set-secrets NEATCODER_GITHUB_APP_ID=neatcoder-github-app-id:1,NEATCODER_GITHUB_PRIVATE_KEY=neatcoder-github-private-key:1,NEATCODER_WEBHOOK_SECRET=neatcoder-webhook-secret:1
   ```

   Replace `us-central1` if you selected another region. Cloud Run builds the container from
   the source; Docker is not required locally. When prompted, allow the required APIs and
   Artifact Registry repository to be created. The Cloud Run service account needs the
   **Secret Manager Secret Accessor** role for each secret.

4. The command prints a URL such as `https://neatcoder-abc123-uc.a.run.app`. In the GitHub App
   settings, set **Webhook URL** to:

   ```text
   https://neatcoder-abc123-uc.a.run.app/webhooks/github
   ```

   Set GitHub's **Webhook secret** to the same value stored in
   `neatcoder-webhook-secret`, save, and trigger a pull-request event in a sandbox repository.

Cloud Run may scale to zero between deliveries; that is expected and does not change the URL.
Keep the default request-based billing and a minimum instance count of zero while testing.
GitHub must be able to access the service, so do not require Cloud Run IAM authentication for
this webhook endpoint. Configure a Google Cloud budget alert before use.

When you are ready to receive real events, populate `.env` with:

- `NEATCODER_GITHUB_APP_ID`: GitHub App ID.
- `NEATCODER_GITHUB_PRIVATE_KEY_PATH`: path to its downloaded PEM private key.
- `NEATCODER_GITHUB_PRIVATE_KEY`: PEM contents, used instead of the path for managed hosting.
- `NEATCODER_WEBHOOK_SECRET`: the webhook secret entered in the GitHub App settings.

Never commit `.env` or the PEM key. Use a dedicated sandbox repository for the first live
installation.

## Repository guidance

Copy [`.github/neat.md.example`](.github/neat.md.example) to `.github/neat.md` in a
repository being reviewed. Rules use a small YAML-like format, with ordinary Markdown
available for additional guidance.
