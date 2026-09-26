# Web agent guide

## Role

Own the public discovery/account website. Privileged administration belongs only to the separate Big Orbit Android application.

## Boundaries

- Public pages explain, register, recover accounts, show releases, and link to project documents.
- The website is not a browser client for quizzes, notes, countdowns, partner data, or together-time.
- `/admin` must remain absent; tests assert a 404 rather than a redirect or hidden console shell.

## Hard rules and invariants

- Use Next.js App Router, React, strict TypeScript, accessible semantic HTML, and Once UI primitives where they improve consistency.
- Prefer Server Components. Use client components only for interaction or browser state, and keep their props serializable and narrow.
- Never render secrets or relationship content. Redact configuration on the API and again in presentation code.
- Public account-recovery responses must resist account enumeration.
- Download metadata includes version, minimum Android level, SHA-256, release notes, and a GitHub Release URL; the versioned Little Orbit API endpoint hosts the APK bytes with resumable delivery.
- Keep the checked-in release fallback byte-for-byte aligned with the newest signed publication so an API restart cannot replace a valid download with stale metadata.
- Treat stored release notes as Markdown input: remove presentation syntax before text-card/RSS output, keep download highlights bounded, retain full notes on `/patch-notes`, format publication dates in UTC, and wrap immutable hashes on narrow screens.
- Meet keyboard, focus, large-text, reduced-motion, contrast, metadata, and mobile layout requirements.
- Inventory every repository-owned Markdown file for each web update. Update or create all affected public, operations, architecture, release, and contributor documents, and always review and update `ROADMAP.md` for behavior, scope, milestone, or release changes.

## Start here

- Site map: [`../../README.md`](../../README.md)
- Public visuals: [`../../SHOWCASE.md`](../../SHOWCASE.md)
- Web/API flow: [`../../docs/NETWORK-FLOW.md`](../../docs/NETWORK-FLOW.md)

## Commands and required tests

```bash
npm install
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Validate desktop and mobile layouts in a real browser. Test keyboard navigation, signup/recovery neutral responses, `/admin` absence, release checksum rendering, error states, and reduced motion.

## Documentation impact

Update README and SHOWCASE for routes and visible changes. Update PRIVACY and NETWORK-FLOW when a form or admin field changes data flow.

## Common mistakes

- Importing the entire component library into a client bundle.
- Turning a static page into a client component.
- Reintroducing an administrator page, proxy, cookie, or client bundle into the public site.
- Linking the primary download action to an unverified third-party or unversioned APK URL.
- Hiding focus styles to match a mockup.
<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
