import { afterEach, describe, expect, it, vi } from "vitest";
import { currentRelease, getCurrentRelease, hostedApkPath } from "./release";

afterEach(() => vi.unstubAllGlobals());

describe("release metadata", () => {
  it("keeps the verified signed APK downloadable when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unavailable")));

    const release = await getCurrentRelease();

    expect(release).toEqual(currentRelease);
    expect(release.published).toBe(true);
    expect(release.sha256).toHaveLength(64);
    expect(release.apkUrl).toBe("/api/v1/releases/1.0.0-rc.5/apk");
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
    expect(release.apkUrl).toBe("/api/v1/releases/1.0.0-rc.1/apk");
    expect(release.sha256).toHaveLength(64);
  });

  it("escapes a release version before making a first-party path", () => {
    expect(hostedApkPath("1.0.0 rc.4")).toBe("/api/v1/releases/1.0.0%20rc.4/apk");
  });
});
