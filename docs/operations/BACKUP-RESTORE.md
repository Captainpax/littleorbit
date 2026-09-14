# State backup and restore

Signed APKs in `data/releases/` are immutable deployment artifacts rather than database state. Keep their checksum sidecars and GitHub release mirrors so the directory can be restored exactly without placing binaries or signing secrets in Git. Restore these files before republishing or serving their existing metadata.

Run `infra/scripts/backup-postgres.ps1` from Windows Task Scheduler using a dedicated local account and a protected destination. The default keeps 14 days. Copy encrypted backups to a second device or storage location outside the application disk.

```powershell
powershell -File infra/scripts/backup-postgres.ps1
```

A backup is unverified until restored. Use a disposable Compose project or an explicitly empty maintenance database; the restore command cleans matching objects. Pass `-TargetDatabase` for a drill so the active application database is untouched.

```powershell
powershell -File infra/scripts/restore-postgres.ps1 -BackupPath backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump
powershell -File infra/scripts/restore-postgres.ps1 -BackupPath backups/postgres/little-orbit-YYYYMMDD-HHMMSS.dump -TargetDatabase little_orbit_restore_check
```

After restore, run migrations, compare row counts for accounts, couples, questions, countdown reminders, and relationship-avatar rows without viewing relationship content or image bytes, verify one test account login, and record date, backup filename, restore duration, and outcome. Relationship avatars live in PostgreSQL and are therefore covered by the encrypted database-backup policy; never extract them as a routine validation step. Migration `0016` intentionally clears legacy account-owned photos, so a pre-RC13 restore followed by upgrade must reproduce that documented reset. The latest local drill on 2026-09-11 restored migration `0007` into `little_orbit_restore_check` and compared privacy-safe table counts. Test monthly and before schema upgrades. Never restore a production backup into an environment with weaker access controls.

## Private attachment volume

RC11 stores attachment metadata in PostgreSQL and staged/sanitized bytes in the `attachment-data` volume. Back up both during the same maintenance window. The attachment script copies the volume through the API container, creates a relative-path, byte-count, and SHA-256 manifest, publishes only the completed directory, and keeps 14 days by default.

```powershell
powershell -File infra/scripts/backup-postgres.ps1
powershell -File infra/scripts/backup-attachments.ps1
```

Encrypt both outputs together off-host. Filenames and file bytes are relationship content: do not inspect, index, upload to a public service, or include them in ordinary backup reports. A database dump without its matching attachment directory restores note text and attachment metadata but cannot restore file content.

Verify an attachment restore only in a disposable Compose project or an approved maintenance window. The script validates every manifest entry before stopping the worker, media worker, and gateway; it then replaces the volume and restarts those services. Restore the matching database dump before reopening the gateway.

```powershell
powershell -File infra/scripts/restore-attachments.ps1 `
  -BackupPath backups/attachments/little-orbit-attachments-YYYYMMDD-HHMMSS.files `
  -ConfirmDestructive
```

After a drill, run migration `head`, confirm the API and media worker are healthy, fetch one synthetic attachment through an authorized test account, compare its sanitized SHA-256, and delete the disposable project. Record only counts, hashes of synthetic fixtures, duration, and outcome. The RC11 physical attachment-volume restore drill remains open until the new storage has been deployed with synthetic data.
