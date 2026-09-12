# PostgreSQL backup and restore

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

After restore, run migrations, compare row counts for accounts/couples/questions/profile-photo rows without viewing relationship content or image bytes, verify one test account login, and record date, backup filename, restore duration, and outcome. Profile photos live in PostgreSQL and are therefore covered by the encrypted database-backup policy; never extract them as a routine validation step. The latest local drill on 2026-09-11 restored migration `0007` into `little_orbit_restore_check` and compared privacy-safe table counts. Test monthly and before schema upgrades. Never restore a production backup into an environment with weaker access controls.
