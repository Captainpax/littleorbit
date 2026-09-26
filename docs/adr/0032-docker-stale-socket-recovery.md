# ADR 0032: Docker stale-socket recovery

- **Status:** Accepted for local operations
- **Date:** 2026-09-14

## Context

After an ungraceful Docker Desktop shutdown, version 4.90 repeatedly failed while renaming `sailor-ingest.sock` to its `.stale` name. Factory reset, data cleanup, or deleting Docker's WSL disk would also erase local images, containers, and named volumes that hold Little Orbit state.

## Decision

Recovery is evidence-first and targets only the runtime socket named by Docker's error. Record Desktop and Engine versions, process and WSL state, disk/VHD metadata, free space, logs, container/image/volume inventory, and a copy of the ephemeral runtime directory. Fully stop Docker Desktop and its backends, shut down Docker's WSL environment, and move only the conflicting socket and matching `.stale` entry out of the live `run` directory. Never remove the directory, settings, data VHD, named volumes, images, or application data.

After the engine starts, verify volume inventory, Compose resolution, Little Orbit health, PostgreSQL and attachment state, and absence of a new stale-socket error. Upgrade only from Docker's official installer after checking the published artifact. If another named socket fails, repeat the same bounded procedure for that socket. If recovery still fails, preserve the VHD and logs and stop before reset or reinstall.

The 2026-09-14 recovery preserved `docker_data.vhdx`, restored Engine 29.8 under Docker Desktop 4.91, and passed hosted and isolated smoke-stack health checks. The screenshot offering **Reset to factory defaults** is diagnostic evidence only and is not an authorized recovery action.

## Consequences

- Runtime socket debris can be removed without treating durable Docker state as disposable.
- A copied runtime directory may contain operational metadata and stays outside Git.
- Factory reset remains an explicit data-loss procedure outside normal Little Orbit recovery.
