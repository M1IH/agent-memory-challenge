# Project Instructions

## Deploy Configuration (configured by /setup-deploy)

- Platform: Railway
- Production URL: https://api-production-40d75.up.railway.app
- Deploy workflow: automatic deploy from the public GitHub `main` branch
- Deploy status command: `railway service status --service api --json`
- Merge method: direct commits to `main` for the individual competition entry
- Project type: FastAPI Add/Search API
- Post-deploy health check: https://api-production-40d75.up.railway.app/health

### Custom deploy hooks

- Pre-merge: `python -m unittest discover -s tests -q`
- Deploy trigger: automatic on push to `main`; manual recovery uses `railway redeploy --service api --from-source --yes`
- Deploy status: `railway deployment list --service api --json`
- Health check: `Invoke-WebRequest -UseBasicParsing https://api-production-40d75.up.railway.app/health`
- Full verification: set `AML_BASE_URL` and `AML_API_KEY`, then run `python scripts\smoke_remote.py`

Do not print, commit, or paste `AML_API_KEY`. Keep the service at one replica while it uses SQLite.
Do not deploy during an official Full evaluation.
