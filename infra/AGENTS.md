# Infrastructure agent guide

## Role

Own reproducible local/production containers, the gateway, GPU override, firewall guidance, secrets, health checks, backups, and restore procedures.

## Boundaries

Nginx Proxy Manager terminates public TLS. The Little Orbit gateway accepts its upstream HTTP/WSS traffic. Every application and data service remains on an internal Compose network.

## Hard rules and invariants

- Expose only gateway port `8180`. Never publish API, web, PostgreSQL, Ollama, or production Mailpit ports.
- Keep application callers off Ollama's model-download egress bridge; only Ollama joins it, and only the worker plus one-shot initializer join the internal AI network.
- Keep notifications first-party: no Firebase credentials, hosted push overlay, provider SDK, or notification-worker egress is permitted.
- Keep ClamAV and the media worker on an internal-only network. Share attachment bytes only through the private volume; pair its encrypted backup with the matching PostgreSQL dump and verify manifests before restore.
- Exclude raw coordinate rows and opt-in device-health snapshots from PostgreSQL backup data. Backup sidecars must state both exclusions before migration or repair tooling accepts the artifact.
- Pin image versions and the validated Ollama model digest. Never use `latest`.
- Keep secrets in environment/secret files outside Git and redact diagnostic output.
- Permit forwarded headers only from `192.168.50.6` and restrict Windows Firewall port 8180 to that source for production.
- Reserve `172.30.14.2` for Caddy and `172.30.14.3` for the API on the private gateway link; otherwise update-time start order can let the API claim the trusted-proxy address.
- Use bounded container logs, health checks, restart policies, automated database backups, retention, and a tested restore path.
- Start migration-aware workers only after the API health check proves Alembic reached head; a healthy database alone does not prove the current schema exists.
- Keep the RC smoke stack in its own Compose project, volumes, network, host ports, and disposable `@example.com` accounts. Its Mailpit override must clear production SMTP credentials and TLS settings rather than inherit them.
- Keep attachment staging, sanitized bytes, the media worker, and ClamAV private. A one-shot root init may assign fresh-volume ownership; every long-running app container stays unprivileged. Back up the attachment volume beside PostgreSQL and verify its manifest before a restore.
- Do not enable HSTS until HTTPS, certificate renewal, rollback, and direct recovery access are verified.
- Never run destructive Compose, volume, database, firewall, DHCP, DNS, or proxy actions without inspecting the target state.
- Copy immutable signed APK bytes into the ignored release directory and publish phone/Wear codes, sizes, hashes, and signer only from the generated `release-manifest.json`. Independently inspect both APK manifests, then verify API range responses. Keep GitHub as a release mirror. Run migrations and health checks before a version floor can be scheduled.
- A phone-only release may reuse a previously signed Wear APK only when its bytes, hash, signer, package, and version code are unchanged and release notes say so explicitly.
- Inventory every repository-owned Markdown file for each infrastructure update. Update or create all affected deployment, backup, security, architecture, release, and contributor documents, and always review and update `ROADMAP.md` for behavior, scope, milestone, or release changes.

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
.\infra\scripts\smoke-stack.ps1 up
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
