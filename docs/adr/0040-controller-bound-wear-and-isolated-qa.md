# ADR 0040: Controller-bound Wear generations and isolated QA artifacts

- Status: accepted
- Date: 2026-09-19
- Extends: ADR 0039

## Context

A selected watch can see more than one connected phone node. Target validation on the phone prevents an unselected watch from sending an action, but the watch also needs to prevent a second phone from receiving status or mutating its encrypted queue. Physical installer QA must exercise destructive install and removal paths without changing the published production package.

## Decision

The first valid managed record for an active Wear relationship generation persists its source Data Layer node as the controller. Only that node receives status and Smooch data and may acknowledge or reject queued operations. Other nodes are ignored without a relationship-state response. Relationship purge, sign-out, unpairing, and Wear expiry clear the binding. A newly authorized generation may then bind to its first valid source.

The phone and Wear `smoke` variants share the debug signer and fixed `com.littleorbit.mobile.smoke` package. The smoke phone embeds the generated current smoke Wear APK and derives its trusted metadata from the embedded archive. A lower-code smoke fixture supports upgrade QA. Production remains bound to immutable HTTPS metadata, the production package, and the pinned release signer. Installer, verifier, and Kadb operations accept only their source's fixed target. Release and ordinary debug artifacts exclude the smoke APK and identity.

## Consequences

One controller owns each Wear relationship generation even when several phones are connected. Binding survives process death but not a privacy purge or expiration. Side-by-side QA can install, replace, and remove only disposable bytes while production remains installed. Smoke artifacts are intentionally unsuitable for publication, and signed release validation remains a separate gate.
