import { afterEach, describe, expect, it, vi } from "vitest";
import { currentRelease, getCurrentRelease } from "./release";

afterEach(() => vi.unstubAllGlobals());

describe("release metadata", () => {
  it("does not present fallback metadata as a downloadable release", () => {
    expect(currentRelease.published).toBe(false);
    expect(currentRelease.sha256).toContain("unavailable");
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
        release_notes: "Signed release candidate",
      }),
    }));

    const release = await getCurrentRelease();

    expect(release.published).toBe(true);
    expect(release.apkUrl).toBe("https://example.test/little-orbit.apk");
    expect(release.sha256).toHaveLength(64);
  });
});
