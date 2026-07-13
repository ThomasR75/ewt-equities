# Deploy the read-only dashboard to Google Cloud Run (free tier)

Runs the exact container we built. Cloud Run scales to zero when idle, so at a
personal usage level it stays within the always-free tier (2M requests,
~180k vCPU-seconds, 360k GiB-seconds per month). The app is gated by the
password you set (`HOSTED_USER` / `HOSTED_PASS`); the fitter, fundamentals
refresh, and backtest are disabled in this hosted mode.

Deployment files live at the repo root: `Dockerfile`, `requirements-hosted.txt`,
`.gcloudignore` (keeps the 250 MB price CSV, the model, and all caches out of the
build).

## 1. One-time setup

- Install the Google Cloud CLI: <https://cloud.google.com/sdk/docs/install>
- Sign in and pick your project:

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

(The first deploy will offer to enable the Cloud Run and Cloud Build APIs — say
yes.)

## 2. Deploy

From the repo root (where the `Dockerfile` is):

```powershell
cd "D:\Claude\EWT test\Elliott wave theory RCT"

gcloud run deploy ewt-dashboard `
  --source . `
  --region us-central1 `
  --allow-unauthenticated `
  --memory 2Gi --cpu 1 `
  --min-instances 0 --max-instances 2 --concurrency 20 `
  --set-env-vars EWT_HOSTED=1,HOSTED_USER=thomas,HOSTED_PASS=CHANGE-ME
```

It builds the image, pushes it, and deploys. When it finishes it prints a
**Service URL** like `https://ewt-dashboard-xxxxx.us-central1.run.app` — open
it and the browser prompts for the username / password you set.

Notes on the flags:

- `--allow-unauthenticated` makes the URL reachable so *your* password (not
  Google IAM) does the gating. Without it, Cloud Run blocks everyone at the
  network layer.
- `--memory 2Gi` comfortably holds one gunicorn worker + both engine states
  (~130 MB) with headroom. Still free at personal usage: at `--cpu 1` the vCPU
  allowance (~50 active-hours/month) is the binding free-tier limit regardless
  of 1 GiB vs 2 GiB.
- `--min-instances 0` = scale to zero (free when idle). The first request after
  an idle period has a few-second cold start while it loads the state.
- `--max-instances 2` caps scaling so a traffic spike can't run up cost.
- **Region matters for free tier:** it only applies in `us-central1`, `us-east1`, or `us-west1`. Use one of those to stay free (a bit more latency from Europe, no cost difference).

## 3. Update the data later

Re-fit locally (`python -m calib.precompute`, and optionally
`python -m calib.fetch_fundamentals`), then just re-run the same
`gcloud run deploy …` command — it rebuilds with the new `calib_state.pkl`.

## 4. Rotate the password

```powershell
gcloud run services update ewt-dashboard --region us-central1 `
  --update-env-vars HOSTED_PASS=new-strong-password
```

For a bit more hygiene you can store the password in Secret Manager and pass
`--set-secrets HOSTED_PASS=ewt-pass:latest` instead of `--set-env-vars`.

---

The `deploy/README.md` (Hugging Face front-matter) and `app_port` are leftovers
from the HF plan and aren't used by Cloud Run. The same `Dockerfile` also works
on Fly.io, Render, or an Oracle/other VM if you ever switch.
