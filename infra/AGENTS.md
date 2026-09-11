# Infrastructure agent guide

## Role

Own reproducible local/production containers, the gateway, GPU override, firewall guidance, secrets, health checks, backups, and restore procedures.

## Boundaries

Nginx Proxy Manager terminates public TLS. The Little Orbit gateway accepts its upstream HTTP/WSS traffic. Every application and data service remains on an internal Compose network.

## Hard rules and invariants

- Expose only gateway port `8180`. Never publish API, web, PostgreSQL, Ollama, or production Mailpit ports.
- Keep application callers off Ollama's model-download egress bridge; only Ollama joins it, and only the worker plus one-shot initializer join the internal AI network.
- Pin image versions and the validated Ollama model digest. Never use `latest`.
- Keep secrets in environment/secret files outside Git and redact diagnostic output.
- Permit forwarded headers only from `192.168.50.6` and restrict Windows Firewall port 8180 to that source for production.
- Use bounded container logs, health checks, restart policies, automated database backups, retention, and a tested restore path.
- Do not enable HSTS until HTTPS, certificate renewal, rollback, and direct recovery access are verified.
- Never run destructive Compose, volume, database, firewall, DHCP, DNS, or proxy actions without inspecting the target state.

## Start here

- Deployment: [`../docs/operations/DEPLOYMENT.md`](../docs/operations/DEPLOYMENT.md)
- Backup/restore: [`../docs/operations/BACKUP-RESTORE.md`](../docs/operations/BACKUP-RESTORE.md)
- Network flow: [`../docs/NETWORK-FLOW.md`](../docs/NETWORK-FLOW.md)

## Commands and required tests

```bash
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
curl --fail http://localhost:8180/api/v1/health/live
docker compose --env-file .env -f infra/compose.yaml exec postgres pg_isready -U little_orbit
```

Test WSS upgrade, TLS renewal, forwarding trust, blocked internal ports, host reboot, Ollama timeout/CPU fallback, backup retention, and restore into an empty database.

## Documentation impact

Update deployment and recovery guides with every network, image, volume, port, secret, or health-check change. Record durable topology changes in an ADR.

## Common mistakes

- Publishing a debug service to all interfaces.
- Assuming a dynamic DHCP lease remains at `192.168.50.182`.
- Enabling HSTS before recovery is tested.
- Using `docker compose down -v` during routine work.
- Calling a backup successful without a restore drill.
