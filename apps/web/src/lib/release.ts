export interface ReleaseMetadata {
  version: string;
  versionCode?: number;
  minimumAndroid: string;
  sha256: string;
  releaseNotes: readonly string[];
  githubUrl: string;
  apkUrl?: string;
  published: boolean;
}

// Keep this verified fallback synchronized with every signed release so a brief API
// outage never removes the public APK download from the statically rendered page.
export const currentRelease: ReleaseMetadata = {
  version: "1.0.0-rc.3",
  versionCode: 3,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "1ecf525d2c2d682dd2a361118c14c0153b58aee80e2ba151de62029d90379647",
  releaseNotes: [
    "Adds user-approved phone updates with package, version, size, hash, and signer verification.",
    "Keeps interrupted update progress safe across activity and process restarts.",
    "Introduces the cosmic phone, widget, and Wear OS visual system.",
    "Keeps routine releases optional; compatibility enforcement requires a separately scheduled UTC time.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.3",
  apkUrl: "https://github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/little-orbit-1.0.0-rc.3.apk",
  published: true,
};

interface ApiRelease {
  version: string;
  version_code: number;
  apk_url: string;
  github_release_url: string;
  sha256: string;
  minimum_android: number;
  release_notes: string;
}

export async function getCurrentRelease(): Promise<ReleaseMetadata> {
  const baseUrl = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${baseUrl}/v1/releases/current`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return currentRelease;
    const release = await response.json() as ApiRelease;
    return {
      version: release.version,
      versionCode: release.version_code,
      minimumAndroid: `Android API ${release.minimum_android} or newer`,
      sha256: release.sha256,
      releaseNotes: release.release_notes.split("\n").filter(Boolean),
      githubUrl: release.github_release_url,
      apkUrl: release.apk_url,
      published: true,
    };
  } catch {
    return currentRelease;
  }
}
