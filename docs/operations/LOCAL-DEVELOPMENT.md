# Local development

## Requirements

- Docker Desktop with Compose 5+
- Node.js 24+ and npm 11+
- Python 3.12 or 3.13 (the pinned native dependencies do not yet support 3.14)
- Java 17, Android SDK 36, and an Android emulator for client work

Copy `.env.example` to `.env` and replace every `change-me`, `replace-`, and placeholder repository URL. Development may use localhost URLs and Mailpit. Never reuse these values publicly.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
Invoke-WebRequest http://localhost:8180/api/v1/health/ready
```

Open `http://localhost:8180` for the website and `http://localhost:8025` for development email. Stop containers with `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml stop`; do not delete volumes during routine work.

The first model initialization downloads roughly 2.5 GB. Add `-f infra/compose.gpu.yaml` only after NVIDIA container support works in Docker Desktop. CPU fallback is slower but retains curated-question coverage.
