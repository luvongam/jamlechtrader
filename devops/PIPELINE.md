# DevOps Pipeline

This repository now includes a GitHub Actions DevOps pipeline aligned with the README development workflow:

- `uv run ruff check .`
- `uv run mypy jamlechtrader/`
- `uv run pytest tests/ -v`
- `uv run alembic upgrade head`
- Docker image build from `Dockerfile`

## Workflows

1. CI: `.github/workflows/ci.yml`
- Triggers on push to `main`, `master`, and `develop`, plus all pull requests.
- Runs lint (`ruff`), type checks (`mypy`), test matrix (`pytest` on Python 3.10/3.11/3.12), DB migration checks against PostgreSQL 15, and Docker build validation.

2. CD: `.github/workflows/cd.yml`
- Triggers on version tags (`v*`) and manual runs (`workflow_dispatch`).
- Builds and publishes container images to GHCR (`ghcr.io/<owner>/<repo>`).
- Supports optional manual deploy over SSH using Docker Compose.

3. Dependency updates: `.github/dependabot.yml`
- Weekly updates for Python dependencies and GitHub Actions.

## Required Settings

For CI only, no additional secrets are required.

For CD publish to GHCR (tag pushes), `GITHUB_TOKEN` is used automatically.

For manual deployment in `cd.yml`, add these repository or environment secrets:

- `SSH_HOST`: deployment host
- `SSH_USER`: SSH username
- `SSH_KEY`: private key for SSH auth
- `SSH_PORT`: SSH port (optional; defaults to `22`)
- `DEPLOY_PATH`: remote directory containing your deployment `docker-compose.yml`
- `GHCR_USERNAME`: username for GHCR login on the remote host
- `GHCR_TOKEN`: token with `read:packages` permission

## Release + Deploy Flow

1. Merge changes into `main`.
2. Create and push a release tag:

```bash
git tag v0.1.1
git push origin v0.1.1
```

3. CD builds and pushes image tags:
- `v0.1.1`
- `sha-<commit>`
- `latest` (for stable semver tags without prerelease suffix)

4. Optional manual deployment:
- Run `CD` workflow from GitHub UI.
- Set `deploy=true`.
- Select `staging` or `production`.
- Optionally set `image_tag` (defaults to `sha-<workflow commit>`).

## Notes

- The deploy step expects your remote `docker-compose.yml` to consume `IMAGE_REF`.
- For safer production deployments, use protected environments and required reviewers in GitHub environments.
