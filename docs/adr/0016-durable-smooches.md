# ADR 0016: Durable private Smooches

Status: Accepted for RC10

## Context

Couples need a tiny, low-pressure way to say they are thinking about each other without turning affection into a score, feed, or paid mechanic.

## Decision

A Smooch contains one of nine fixed emoji, one of six versioned phrase keys, the sender and couple identifiers, an operation ID, and a UTC send time. The server atomically enforces five sends per sender in a rolling hour. Android may queue at most five encrypted deliberate sends for 15 minutes. Recipients poll every five minutes while the location foreground service is active and otherwise through a 15-minute worker.

Weekly history uses Monday-to-Sunday boundaries in the couple's selected IANA home timezone. It survives unpairing in each person's private archive, never transfers to another partner, and is permanently erased when either original participant account is deleted. The default notification hides the emoji on the lock screen; the recipient may opt into full wording.

## Consequences

History is emotionally meaningful and intentionally durable, so deletion and archive authorization need dedicated tests. Limits reduce notification spam without adding rankings. Site-wide AI never receives Smooch data.
