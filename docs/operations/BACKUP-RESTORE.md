# Encrypted state backup and restore

Little Orbit has two coordinated mutable stores: PostgreSQL metadata and the private attachment volume. Signed APKs under `data/releases/` are immutable deployment artifacts and must be copied with their checksum sidecars separately.

## Protect the age identity

Set `BACKUP_AGE_RECIPIENT` in the ignored `.env` file to the public recipient printed by `age-keygen`. Keep the corresponding private identity outside Git and Docker. Restore scripts default to:

```text
%LOCALAPPDATA%\LittleOrbit\backup-age-identity.txt
```

Keep an offline recovery copy. Do not place the identity beside off-host backup files. A same-drive encrypted backup helps with logical recovery but does not survive loss of the computer or disk.

## Create one coordinated snapshot

Use the coordinator so the API, worker, and media worker stop accepting mutations at one clear consistency point. The scripts stream directly through `age`; they do not write a plaintext database dump or attachment archive.

```powershell
powershell -File infra/scripts/backup-all.ps1
```

The command creates:

- `backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump.age`
- `backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.tar.age`
- JSON sidecars containing encrypted size, SHA-256, and content-free backup facts

PostgreSQL uses the dedicated read-only backup role and explicitly excludes all `location_samples` and `together_device_health` table data. The JSON sidecar records both exclusions; 1.0.1 repair commands reject an older or ambiguous sidecar before changing rows. The attachment archive includes a relative-path, byte-count, and SHA-256 manifest. Both scripts retain 14 days by default and restart the exact mutation containers that were running before the snapshot.

Individual scripts remain available for investigation, but a database-only or attachment-only file is not a complete application backup:

```powershell
powershell -File infra/scripts/backup-postgres.ps1
powershell -File infra/scripts/backup-attachments.ps1
```

Copy the encrypted pair and sidecars to protected storage on another physical device. Attachment names and bytes remain relationship content even while encrypted; do not index them in a public backup service or include them in routine reports.

## Restore PostgreSQL safely

A backup is unverified until restored. Prefer a disposable database so active application data remains untouched. The restore streams decrypted bytes directly into `pg_restore` and cleans matching objects in the target database.

```powershell
powershell -File infra/scripts/restore-postgres.ps1 `
  -BackupPath backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump.age `
  -TargetDatabase little_orbit_restore_check
```

Restoring the active database requires an explicit maintenance decision and `-ConfirmDestructive`:

```powershell
powershell -File infra/scripts/restore-postgres.ps1 `
  -BackupPath backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump.age `
  -ConfirmDestructive
```

After restore, run migrations and compare privacy-safe row counts for accounts, couples, questions, countdown reminders, and relationship avatars. Confirm that `location_samples` and `together_device_health` contain zero restored rows. Never open notes, answers, precise locations, diagnostics, or image bytes as routine validation.

## Restore attachment bytes

Restore only the attachment file paired with the restored database snapshot. The command validates every manifest member, exact size, and SHA-256 before replacing the volume. It stops the currently running gateway, API, worker, and media-worker containers by exact container ID, then restarts those same containers.

```powershell
powershell -File infra/scripts/restore-attachments.ps1 `
  -BackupPath backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.tar.age `
  -ConfirmDestructive
```

Run attachment restore only in an isolated Compose project or an approved maintenance window. Afterward, confirm API and media-worker health, fetch one synthetic clean attachment through an authorized test account, compare its sanitized SHA-256, and remove the disposable database and volume.

## RC14 restore evidence

On 2026-09-14, an isolated drill decrypted and restored the coordinated snapshot, recovered six attachment files, preserved existing account and couple metadata, and restored zero raw coordinate rows. The synthetic source marker deliberately placed in `location_samples` was absent. The disposable database, attachment marker, and restore debris were removed after verification. This proves the local restore path; it does not replace an off-host disaster-recovery copy or a production maintenance rehearsal.
