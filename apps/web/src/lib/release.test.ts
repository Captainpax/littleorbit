import { afterEach, describe, expect, it, vi } from "vitest";
import {
  currentRelease,
  formatReleaseDate,
  getCurrentRelease,
  hostedApkPath,
  hostedWearApkPath,
  releaseNoteLines,
  releaseNoteHighlights,
} from "./release";

afterEach(() => vi.unstubAllGlobals());

describe("release metadata", () => {
  it("keeps the verified signed APK downloadable when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unavailable")));

    const release = await getCurrentRelease();

    expect(release).toEqual(currentRelease);
    expect(release.published).toBe(true);
    expect(release.sha256).toHaveLength(64);
    expect(release.apkUrl).toBe(hostedApkPath(currentRelease.version));
    expect(release.wear?.apkUrl).toBe(hostedWearApkPath(currentRelease.version));
  });

  it("maps published API metadata to the signed APK download", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        version: "1.0.0-rc.1",
        apk_url: "https://example.test/little-orbit.apk",
        github_release_url: "https://example.test/release",
        sha256: "a".repeat(64),
        minimum_android: 29,
        minimum_supported_version_code: 6,
        release_notes: "Signed release candidate",
      }),
    }));

    const release = await getCurrentRelease();

    expect(release.published).toBe(true);
    expect(release.minimumSupportedVersionCode).toBe(6);
    expect(release.apkUrl).toBe("/api/v1/releases/1.0.0-rc.1/apk");
    expect(release.sha256).toHaveLength(64);
  });

  it("escapes a release version before making a first-party path", () => {
    expect(hostedApkPath("1.0.0 rc.4")).toBe("/api/v1/releases/1.0.0%20rc.4/apk");
    expect(hostedWearApkPath("1.0.0 rc.6"))
      .toBe("/api/v1/releases/1.0.0%20rc.6/wear-apk");
  });

  it("presents stored Markdown as clean release-note rows", () => {
    expect(releaseNoteLines([
      "# Little Orbit 1.0.0-rc.13",
      "A short release summary.",
      "## Candidate status",
      "This transient publication status is omitted.",
      "## Changes",
      "- Adds **safe updates** with `exact hashes`.",
      "- [Read the guide](https://example.test/guide)",
      "## Verified so far",
      "This transient verification status is omitted.",
      "## Signed artifacts",
      "One\\nTwo",
    ].join("\n"))).toEqual([
      "A short release summary.",
      "Adds safe updates with exact hashes.",
      "Read the guide",
      "One",
      "Two",
    ]);
  });

  it("keeps download highlights bounded and release dates host-independent", () => {
    expect(releaseNoteHighlights("One\nTwo\nThree\nFour\nFive\nSix"))
      .toEqual(["One", "Two", "Three", "Four", "Five"]);
    expect(formatReleaseDate("2026-09-14T02:40:57Z")).toBe("Sep 14, 2026");
  });
});
