# Documentation agent guide

## Role

Keep public promises, architecture diagrams, operations, screenshots, and decisions accurate and useful to learners.

## Boundaries

- README and SHOWCASE explain the public product.
- NETWORK-FLOW is the editable source of truth for trust and transport flows.
- PRIVACY describes data, purpose, retention, access, export, and deletion.
- Operations guides contain repeatable commands and recovery checks.
- ADRs record accepted durable choices and their consequences.

## Hard rules and invariants

- Mermaid source stays editable even when a generated overview image is embedded.
- Number ADRs with four digits; never rewrite an accepted decision's history. Supersede it with a new ADR.
- Label concept art and simulated data. Replace screenshot checklist items only after capturing the actual implementation.
- Use repository-relative links and alt text. Never embed production secrets, private IP details beyond the documented topology, or personal data.
- Report tests and device checks honestly. Distinguish configured, simulated, locally verified, and production verified.
- Release notes must record version code, signer identity, artifact hash, compatibility floor, and whether enforcement is inactive or scheduled.
- When a release reuses an unchanged companion artifact, record its original version code and exact byte identity rather than implying a new companion build.
- Verification records distinguish server receipt from inferred real-world proximity and never print precise coordinates.
- Document destructive or meaning-changing migrations before deployment. If data is deliberately cleared because its ownership semantics cannot be converted honestly, state that boundary in the ADR, privacy guide, release notes, deployment guide, and verification record.
- Inventory every repository-owned Markdown file for every update. Update or create all affected public, operations, architecture, privacy, security, release, and contributor documents. Always review and update `ROADMAP.md` when behavior, scope, milestones, or release state changes; record an explicit no-change reason only when the roadmap remains exactly accurate.

## Start here

- [`../README.md`](../README.md)
- [`NETWORK-FLOW.md`](NETWORK-FLOW.md)
- [`PRIVACY.md`](PRIVACY.md)
- [`adr/`](adr/)
- [`operations/`](operations/)

## Commands and required checks

```bash
npx --yes markdownlint-cli2 "**/*.md"
python infra/scripts/check_docs.py
npm --prefix apps/web run capture:showcase
```

Render every changed Mermaid diagram, validate local links, inspect images at mobile and desktop widths, and run every command changed in an operations guide when the environment permits it.

## Documentation impact

Each code change should point to the document it affects. Changes with no documentation impact should say why in the pull request.

## Common mistakes

- Describing planned behavior as released.
- Copying a diagram PNG without updating its Mermaid source.
- Hiding a failed or skipped validation.
- Allowing docs to become a second, incompatible protocol definition.
