# Encrypted state backup and restore

Little Orbit has two coordinated mutable stores: PostgreSQL metadata and private attachment bytes. Signed APKs in `/mnt/cache/little-orbit-live/releases/` are immutable deployment artifacts and must be copied and verified separately. The live Unraid production profile keeps state on direct cache-pool paths and writes only encrypted, privacy-filtered backup pairs to the parity array; the migration verification record captures the 2026-09-27 cutover and first target restore drill.

## Protect the age identity

Set `BACKUP_AGE_RECIPIENT` in the root-only `/mnt/cache/little-orbit-secrets/runtime.env` to the public recipient printed by the checksum-pinned `age-keygen`. Keep the corresponding private identity outside Git and production containers. The Unraid restore drill defaults to:

```text
/mnt/cache/little-orbit-secrets/backup-age-identity.txt
```

Use mode `0600` for the identity and retain a protected offline recovery copy. Do not place the identity in `/mnt/user/little-orbit-backups` or beside an off-host backup. The initial array copy shares the same Unraid failure domain as live cache state: it supports local logical/cache recovery but does not survive loss of the server. Off-host encrypted recovery remains an explicit open requirement.

## Create one coordinated snapshot

Run the fixed host operation so the API, worker, and media worker stop accepting mutations at one clear consistency point. The scripts stream directly through `age`; they do not write a plaintext database dump or attachment archive.

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh backup
```

The command creates:

- `/mnt/user/little-orbit-backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump.age`
- `/mnt/user/little-orbit-backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.tar.age`
- JSON sidecars containing encrypted size, SHA-256, and content-free backup facts
- `/mnt/user/little-orbit-backups/manifests/little-orbit-pair-YYYYMMDD-HHMMSS.json`, written only after both encrypted files complete

The Unraid coordinator requires the dedicated array-backed root exactly; it refuses a different backup path. Bootstrap keeps a root-owned mode-`0600` `.array-placement` sentinel in that root so even an otherwise empty share has a physical array-disk location that can be audited. The sentinel is content-free, is not part of a backup pair, and must not be removed. The coordinator writes schema-3 manifests with paths relative to that root plus content-free counts for every retained public table, promotes each encrypted component and sidecar from a partial name, and writes the pair manifest last. The default retention is 14 days.

PostgreSQL uses the dedicated read-only backup role and explicitly excludes all `location_samples`, `together_device_health`, `question_feedback`, `question_feedback_operations`, and `anonymous_question_reviews` table data. The JSON sidecar and pair manifest record every privacy exclusion; restore tooling rejects an older or ambiguous manifest. Identity-free weekly aggregates and learned policy remain in the dump. The attachment archive includes a relative-path, byte-count, and SHA-256 manifest. The coordinator refuses to begin unless it identifies exactly one running container for each required service: API, worker, and media worker, and all three real process/dependency health checks pass. It stops and restarts those three exact container IDs, waits up to five minutes for every container to run and become healthy, and writes the selectable pair manifest only after that recovery succeeds. Restart or readiness failure makes the backup fail nonzero.

The Unraid job currently records `off_host_copy:false`; no off-host destination is enabled by this migration. When one is added, copy only a completed encrypted pair, both sidecars, and its pair manifest into partial staging on a physically separate failure domain, recheck encrypted size and SHA-256, promote atomically, and prove a restore from that copy. A database-only or attachment-only file is not a complete application backup. Attachment names and bytes remain relationship content even while encrypted; do not index them in a public service or include them in routine reports.

## Automated non-destructive restore drill

A backup is unverified until restored. The Unraid drill selects the newest completed pair manifest, resolves only paths contained by `/mnt/user/little-orbit-backups`, and verifies both encrypted byte counts and SHA-256 values before decryption. It never combines independently newest files.

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh test_restore
```

The drill starts a networkless, nonroot, read-only PostgreSQL container whose only database storage is a bounded tmpfs. It streams the dump directly into that isolated process, requires the exact Alembic `0032` head, proves every excluded privacy table is empty, and requires every retained table count to match the frozen backup manifest. It streams the paired attachment archive through a separate networkless, nonroot, read-only verifier with no live attachment mount. Direct backup, restore-drill, and pending invocations share the fixed `/var/lock/little-orbit-operations.lock` inode; child dispatch retains one inherited lock descriptor rather than attempting a second lock. Only pending may skip successfully. Its success record is emitted only after the plaintext tmpfs container has been destroyed and is no longer inspectable; a cleanup failure makes the run fail. The command requires the root-only age identity but never connects the restored database to the production network or cluster.

A pass proves that the selected local encrypted files can be decrypted and structurally validated now. It does not test a new host, recover the live database, restore public routing, validate every workflow, or establish off-host disaster recovery. After a separately approved live restore, run migrations and compare privacy-safe row counts for accounts, couples, questions, countdown reminders, and relationship avatars; confirm every excluded table has zero restored rows. Never open notes, answers, precise locations, diagnostics, filenames, or image bytes as routine validation.

## Schedule backups and Big Orbit requests

Unraid User Scripts invokes fixed modes only:

- `backup` daily at 08:00 Pacific;
- `test_restore` Tuesday at 07:00 Pacific;
- `pending` every five minutes for allowlisted `backup` and `test_restore` requests from an enrolled Big Orbit device.

The schedule installer and the direct `backup`/`test_restore` dispatcher require Unraid to be configured for the exact
`America/Los_Angeles` IANA timezone and require `/etc/localtime` to match that zoneinfo file. Installation or a
wall-clock run fails nonzero on missing or mismatched evidence. Configure the host through Unraid's Date and Time
settings; a process-only `TZ` override does not satisfy this boundary. The installer's default `install` mode creates
the fixed wrappers but leaves startup and all cron entries inactive; run `activate-after-cutover` only after `.14` is
the authoritative writer. The five-minute pending runner is interval-based.

The runner takes one host `flock`, atomically claims at most five pending rows, and records content-free status and pair-manifest evidence in `backup_runs`. Its psql client is quiet so an empty `UPDATE ... RETURNING` produces no command tag that could be mistaken for a UUID; a real claim emits only its allowlisted `id|kind` row. It does not accept a shell command, SQL string, URL, path, or arbitrary argument from Big Orbit. Only the frequent `pending` mode may return successful `already_running`. An explicit backup or restore drill waits up to 300 seconds for the lock, then fails with a nonzero status so scheduling cannot report a skipped protection job as successful. Stale two-hour run records become failed evidence and are not silently adopted.

The Windows Scheduled Task registration and PowerShell coordinator remain available only for `.182` recovery. Do not enable both host schedulers against the same production database. The recovery registration now schedules its daily backup at 08:00 local time, its Tuesday drill at 07:00, and its pending runner every five minutes with the same collision distinction. Database commands travel through quiet `psql` stdin so Windows native-argument parsing cannot remove JSON quotes and DML command tags cannot contaminate a claimed job row. Binary child stdin is created with a BOM-free encoding before any PostgreSQL or attachment byte is copied; this avoids the UTF-8 preamble emitted by Windows PowerShell 5.1's .NET Framework writer. A drill arms exact-name cleanup before invoking restore, so an invalid archive cannot leave a plaintext disposable database behind.

## Exact host migration is not a backup

The `.182` to `.14` move must preserve rows that sanctioned backups intentionally omit, including existing feedback and feedback-operation rows. Explicit `--direction forward` streams a full logical PostgreSQL dump directly through host-key-pinned SSH into an empty `.14` target after freezing every writer. Attachments and releases are verified in sibling cache-pool directories and promoted only as complete directory trees. The command emits exact source/destination public-table counts, Alembic heads, aggregate attachment evidence without paths, and public release size/hash evidence; it exposes no output/archive option. Do not redirect, intercept, or retain either private stream.

After `.14` accepts a write, explicit `--direction rollback` is the only sanctioned reverse path. It requires the stale `.182` production project to be completely stopped, restores into the separate `little-orbit-rollback` project with a fresh PostgreSQL volume and an explicit empty bind root, and never transfers or overwrites `.182` secrets. It freezes `.14`, repeats the direct-stream/inventory checks, and leaves `.14` frozen only on success. A failure restarts the exact target writers and removes the dedicated failed recovery state. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the confirmation phrases and commands.

This exception exists only for the application-cold host move or its post-write reversal. It does not change ordinary exclusions, create reusable recovery media, or authorize content inspection. Before the transfer, create and restore-drill a normal privacy-filtered pair. After cutover, create another normal target pair and repeat the drill. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for preflight, exact commands, rollback boundary, and deletion approval.

## Legacy `.182` attachment recovery

For a disposable PostgreSQL check on the recovery host:

```powershell
powershell -File infra/scripts/restore-postgres.ps1 `
  -BackupPath backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump.age `
  -TargetDatabase little_orbit_restore_check
```

Restoring its active database remains destructive and requires `-ConfirmDestructive`. Never use it as post-cutover rollback without first reverse-streaming current `.14` state as described in the deployment runbook.

Restore only the attachment file paired with the restored database snapshot. The command validates every manifest member, exact size, and SHA-256 before replacing the volume. It stops the currently running gateway, API, worker, and media-worker containers by exact container ID, then restarts those same containers.

```powershell
powershell -File infra/scripts/restore-attachments.ps1 `
  -BackupPath backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.tar.age `
  -ConfirmDestructive
```

This PowerShell command is retained for `.182` recovery only. Run attachment restore only in an isolated Compose project or an approved maintenance window. Afterward, confirm API and media-worker health, fetch one synthetic clean attachment through an authorized test account, compare its sanitized SHA-256, and remove the disposable database and volume. The automated Tuesday drill never calls this destructive path.

## RC14 restore evidence

On 2026-09-14, an isolated drill decrypted and restored the coordinated snapshot, recovered six attachment files, preserved existing account and couple metadata, and restored zero raw coordinate rows. The synthetic source marker deliberately placed in `location_samples` was absent. The disposable database, attachment marker, and restore debris were removed after verification. This proves the local restore path; it does not replace an off-host disaster-recovery copy or a production maintenance rehearsal.
