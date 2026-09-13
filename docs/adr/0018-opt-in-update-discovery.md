# ADR 0018: Opt-in update discovery

Status: Accepted for RC10

## Context

Manual checks caused release candidates to be missed, while automatic APK transfer would violate Little Orbit's explicit sideloading boundary.

## Decision

RC10 asks once whether optional automatic detection is enabled. When enabled, WorkManager fetches public metadata about every six hours. An active required compatibility floor is always checked. An available optional update prompts at most once per cold process and remains visible in More; choosing Later suppresses only the current process. The worker never downloads APK bytes. Download and installation begin only after explicit approval and keep the existing origin, size, checksum, package, newer-version, and signer checks.

A running or paused DownloadManager transfer with no progress for five minutes becomes a visible stalled state that can be retried cleanly.

## Consequences

People learn about releases without surrendering install control. Detection stores a local preference and last-check time. Required updates remain enforceable while using the same verification chain.
