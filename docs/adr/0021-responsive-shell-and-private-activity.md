# ADR 0021: Responsive application shell and private couple activity

- Status: accepted for RC12
- Date: 2026-09-13

## Context

Five fixed bottom destinations made the growing 1.0 feature set difficult to find and left settings scattered behind a generic More page. Our Space also needed document actions without adding another permanent row of controls. A conventional drawer is appropriate on a phone, but leaving a `DrawerLayout` drawer locked open on a tablet consumes touches outside the drawer even when the main content is visibly offset.

Couples also lacked a small answer to “what changed?” after opening the app. Reusing note bodies, quiz answers, locations, or attachment names for a feed would create a second sensitive-content store and an inappropriate owner-console surface.

## Decision

Every top-level Android destination uses one shell. Phones open the full navigation from the left. At 840dp and wider, the same navigation becomes a static view beside the main content rather than a locked-open drawer. The end drawer is available only through a dedicated toolbar control and contains actions for the current destination. It remains locked against edge gestures so it does not compete with predictive back.

Home's end panel includes a current-couple activity page. Feature services append an event only while holding the couple lock that protects the underlying mutation. Each event has a couple-local monotonic sequence and retry-safe dedupe key. Stored fields are limited to the fixed event kind, actor, time, navigation target, optional target title, and optional approved Smooch emoji. The feed excludes note bodies, attachment names or bytes, quiz prompts and answers, coordinates, account email, and custom prose.

The API authorizes current active membership before event lookup. Each member owns a monotonic seen watermark. Unpairing deletes the active feed, account deletion follows foreign-key cleanup, and the worker deletes events older than 30 days. Administrators have no activity-list endpoint or viewer.

## Consequences

All top-level screens share navigation and inset behavior, destination discovery no longer depends on bottom-tab capacity, and wide screens remain interactive. Screen-specific actions can evolve without crowding primary content. Activities outside the shell remain focused system flows.

The activity panel is useful for orientation without becoming a relationship-history archive. Optional note or countdown titles are still couple-visible metadata and therefore remain outside logs and administrator tools. Adding a new event type requires a privacy review, a stable dedupe source, transaction coverage, Android wording/navigation, retention verification, and updates to the public data inventory.
