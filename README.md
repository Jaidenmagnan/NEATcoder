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
For deployment and live webhook testing, follow [Deploy on Google Cloud](#deploy-on-google-cloud).

## Deploy on Google Cloud

Google Cloud Run provides a stable HTTPS endpoint, so a tunnel is unnecessary. This repository
includes a `Procfile` that starts Uvicorn on Cloud Run's required `PORT`.

1. Create or select a Google Cloud project with billing enabled, then open Cloud Shell or use
   a local installation of the Google Cloud CLI. Select a region near you, such as
   `us-east1`.

2. In Secret Manager, create these five secrets. Store the complete PEM file contents,
   including its BEGIN/END lines, in the private-key secret.
   - `neatcoder-github-app-id`
   - `neatcoder-github-private-key`
   - `neatcoder-webhook-secret`
   - `neatcoder-openai-api-key`
   - `neatcoder-task-secret` — a separate long random value that protects the internal review
     task endpoint.

   Create the durable review queue and allow the Cloud Run runtime service account to enqueue
   jobs. This project uses its default Compute Engine runtime service account:

   ```bash
   gcloud services enable cloudtasks.googleapis.com --project neatcoder-508419

   gcloud tasks queues create neatcoder-reviews \
     --location us-east1 \
     --project neatcoder-508419

   gcloud projects add-iam-policy-binding neatcoder-508419 \
     --member="serviceAccount:735836629222-compute@developer.gserviceaccount.com" \
     --role="roles/cloudtasks.enqueuer"
   ```

3. Deploy the checked-out repository from its root directory:

   ```bash
   gcloud run deploy neatcoder \
     --source . \
     --region us-east1 \
     --allow-unauthenticated \
     --set-secrets NEATCODER_GITHUB_APP_ID=neatcoder-github-app-id:latest,NEATCODER_GITHUB_PRIVATE_KEY=neatcoder-github-private-key:latest,NEATCODER_WEBHOOK_SECRET=neatcoder-webhook-secret:latest,OPENAI_API_KEY=neatcoder-openai-api-key:latest,NEATCODER_TASK_SECRET=neatcoder-task-secret:latest \
     --set-env-vars NEATCODER_GCP_PROJECT=neatcoder-508419,NEATCODER_TASK_LOCATION=us-east1,NEATCODER_TASK_QUEUE=neatcoder-reviews,NEATCODER_TASK_TARGET_URL=https://neatcoder-735836629222.us-east1.run.app/tasks/review
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

Each verified webhook creates a Cloud Tasks job, and the job calls `/tasks/review` to perform
the potentially long GitHub and AI work. Cloud Tasks retries a failed job automatically; the
task endpoint is protected by `NEATCODER_TASK_SECRET` even though the service is public for
GitHub webhooks.

### Automatic deployments from GitHub

The included [deployment workflow](.github/workflows/deploy-cloud-run.yml) deploys every push
to `main` (and can be run manually from the Actions tab). It uses GitHub OIDC and Google Cloud
Workload Identity Federation, so no long-lived Google credential is stored in GitHub.

Complete this one-time setup from an account with permission to administer IAM in
`neatcoder-508419`. The repository name in the commands deliberately restricts authentication
to this repository.

```bash
gcloud iam service-accounts create github-deployer \
  --project=neatcoder-508419 \
  --display-name="GitHub Actions Cloud Run deployer"

gcloud iam workload-identity-pools create github-actions \
  --project=neatcoder-508419 \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --project=neatcoder-508419 \
  --location=global \
  --workload-identity-pool=github-actions \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='Jaidenmagnan/NEATcoder'"
```

Grant the deployer permission to deploy and start source builds. The final command lets it attach
the Cloud Run runtime service account; this is the default account currently used by this service.

```bash
gcloud projects add-iam-policy-binding neatcoder-508419 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding neatcoder-508419 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/run.sourceDeveloper

gcloud projects add-iam-policy-binding neatcoder-508419 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/serviceusage.serviceUsageConsumer

gcloud projects add-iam-policy-binding neatcoder-508419 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/cloudbuild.builds.editor

gcloud artifacts repositories add-iam-policy-binding cloud-run-source-deploy \
  --project=neatcoder-508419 \
  --location=us-east1 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.reader

gcloud iam service-accounts add-iam-policy-binding \
  735836629222-compute@developer.gserviceaccount.com \
  --project=neatcoder-508419 \
  --member="serviceAccount:github-deployer@neatcoder-508419.iam.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser

gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@neatcoder-508419.iam.gserviceaccount.com \
  --project=neatcoder-508419 \
  --member="principalSet://iam.googleapis.com/projects/735836629222/locations/global/workloadIdentityPools/github-actions/attribute.repository/Jaidenmagnan/NEATcoder" \
  --role=roles/iam.workloadIdentityUser
```

In GitHub, open **Settings → Secrets and variables → Actions → Variables** and add:

- `GCP_WIF_PROVIDER`: `projects/735836629222/locations/global/workloadIdentityPools/github-actions/providers/github`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`: `github-deployer@neatcoder-508419.iam.gserviceaccount.com`

Then commit and push the workflow. GitHub’s OIDC token is exchanged for short-lived Google Cloud
credentials, and the deployment reads its application credentials only from Secret Manager.

### AI review and cost controls

When `OPENAI_API_KEY` is configured, NEATcoder sends changed patches and repository guidance
to OpenAI for an additional AI review. The default model is `gpt-5.4-nano`. Each review is
capped by `NEATCODER_MAX_DIFF_BYTES` (500,000 bytes by default) and
`NEATCODER_MAX_AI_OUTPUT_TOKENS` (1,200 by default); lower either setting to reduce spend.
OpenAI API usage is not included with a ChatGPT subscription, so set an OpenAI usage limit and
budget alert before enabling the key.

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
