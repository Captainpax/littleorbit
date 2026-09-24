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
- `backups/manifests/little-orbit-pair-YYYYMMDD-HHMMSSfff.json`, written only after both encrypted files complete

The coordinator is compatible with both Windows PowerShell 5.1 and PowerShell 7. It validates that component outputs remain inside the workspace before recording relative paths in the pair manifest.

PostgreSQL uses the dedicated read-only backup role and explicitly excludes all `location_samples`, `together_device_health`, `question_feedback`, `question_feedback_operations`, and `anonymous_question_reviews` table data. The JSON sidecar records the privacy exclusions; repair commands reject an older or ambiguous sidecar before changing rows. Identity-free weekly aggregates and learned policy remain in the dump. The attachment archive includes a relative-path, byte-count, and SHA-256 manifest. Both scripts retain 14 days by default and restart the exact mutation containers that were running before the snapshot.

To copy only the encrypted artifacts and sidecars to a separately managed filesystem, set an absolute destination outside the repository:

```powershell
$env:LITTLE_ORBIT_OFFHOST_BACKUP_DIR = "E:\LittleOrbitEncrypted"
powershell -File infra/scripts/backup-all.ps1
```

The script rejects the repository and a filesystem root as the off-host target. It copies the two encrypted artifacts, their sidecars, and the pair manifest into a hidden partial directory, verifies each copied SHA-256, and only then promotes the directory to its final timestamped name. A `.partial-*` directory is incomplete and must never be restored. The operator remains responsible for mount availability, permissions, separate-device durability, retention, and monitoring; a second directory on the same disk is not disaster recovery.

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

## Automated non-destructive restore drill

The 1.2 drill selects the newest completed pair manifest, resolves only its exact workspace-contained database and attachment paths, and verifies both encrypted byte counts and SHA-256 values before decryption. It never combines independently newest files. The drill restores PostgreSQL into a unique `little_orbit_drill_YYYYMMDDHHMMSS` database, checks required schema, proves every excluded privacy table is empty, and streams the paired attachment archive through its path/size/SHA-256 manifest without writing into the live volume. Its cleanup drops only a database matching that exact generated pattern.

```powershell
powershell -File infra/scripts/test-restore-latest.ps1
```

The command requires the age identity and a running PostgreSQL container. A pass proves that the selected encrypted files can be decrypted and structurally validated now. It does not test a new host, restore DNS, validate every application workflow, or replace a periodic full disaster-recovery rehearsal.

## Schedule backups and Big Orbit requests

Review the paths and execute this once from an elevated interactive PowerShell session on the intended host:

```powershell
powershell -File infra/scripts/register-operations-tasks.ps1
```

It registers three current-user tasks:

- coordinated encrypted backup every day at 06:00 host local time;
- non-destructive restore drill every Tuesday at 07:00 host local time;
- a five-minute runner for allowlisted `backup` and `test_restore` jobs requested by an enrolled Big Orbit device.

The tasks use an interactive-token principal so the age identity remains in that operator's protected profile and no password is written into a task definition. They run only while that identity has an interactive logon. A production host that must run unattended should use a dedicated Windows service identity, grant only the Docker/off-host/age-identity access it needs, and register equivalent tasks through the owner's secret-management process.

The runner allows only fixed job kinds, takes a named single-instance lock, claims one database row atomically, and records content-free status and manifest evidence in `backup_runs`. It does not accept a shell command, SQL string, URL, path, or arbitrary argument from Big Orbit. Failed or interrupted requests stay visible and require an explicit retry with a new operation ID.

## Restore attachment bytes

Restore only the attachment file paired with the restored database snapshot. The command validates every manifest member, exact size, and SHA-256 before replacing the volume. It stops the currently running gateway, API, worker, and media-worker containers by exact container ID, then restarts those same containers.

```powershell
powershell -File infra/scripts/restore-attachments.ps1 `
  -BackupPath backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.tar.age `
  -ConfirmDestructive
```

Run attachment restore only in an isolated Compose project or an approved maintenance window. Afterward, confirm API and media-worker health, fetch one synthetic clean attachment through an authorized test account, compare its sanitized SHA-256, and remove the disposable database and volume. The automated Tuesday drill never calls this destructive path.

## RC14 restore evidence

On 2026-09-14, an isolated drill decrypted and restored the coordinated snapshot, recovered six attachment files, preserved existing account and couple metadata, and restored zero raw coordinate rows. The synthetic source marker deliberately placed in `location_samples` was absent. The disposable database, attachment marker, and restore debris were removed after verification. This proves the local restore path; it does not replace an off-host disaster-recovery copy or a production maintenance rehearsal.
