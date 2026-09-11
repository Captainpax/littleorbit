# ADR 0004: Java/XML Android with separated modules

- Status: Accepted
- Date: 2026-09-10

## Context

The project is intended to teach modern Android architecture while meeting the maintainer's Java requirement and supporting phone, widgets, and Wear OS.

## Decision

Use Java 17 and XML Views with Material 3, View Binding, ViewModels, Room, WorkManager, Hilt, Retrofit, OkHttp, and Moshi. Separate platform-free domain code, data/integration code, the phone app and widget, and Wear OS surfaces.

## Consequences

DTOs, entities, domain objects, and screen state require explicit mapping. Phone and watch share contracts and small cached values rather than UI types or database entities. Kotlin-only library APIs need Java-friendly adapters or alternatives.
