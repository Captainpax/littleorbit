# ADR 0015: Pair instant and continuous proximity collection

Status: Accepted for RC10

## Context

Asking couples to negotiate a separate relationship date added friction and allowed the phone, widget, and watch to disagree. Fifteen-minute opportunistic jobs also produced very sparse samples under Android background limits, even while both partners had consented.

## Decision

Relationship age derives from the immutable UTC instant written when pair confirmation creates the couple. RC10 clients do not expose the older date-proposal UI. Consented location uses a visible high-accuracy foreground service at roughly five-minute intervals, with a 15-minute WorkManager recovery path that can queue samples offline. Either permission removal or consent revocation stops collection and clears queued samples immediately.

Server proximity rules remain conservative: match pairs within ten minutes, require two consecutive confident pairs within 100 metres, reject intervals over twenty minutes, deduplicate samples, prevent overlapping buckets, and purge raw coordinates within 24 hours.

## Consequences

Pair age is deterministic and requires no extra sensitive date. Android shows a persistent system notification while active and uses more battery than opportunistic work. Sparse evidence should decrease, but zero remains the correct result when accepted samples are distant or insufficient. Older API fields remain until a later contract removes them deliberately.
