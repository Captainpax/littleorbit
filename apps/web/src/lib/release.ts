export interface ReleaseMetadata {
  version: string;
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
  version: "1.0.0-rc.1",
  minimumAndroid: "Android 10 (API 29)",
  sha256: "bafcbe67ab140edafc57300555c60c131be5fe6c346769df15fb8bee473bc0f1",
  releaseNotes: [
    "Signed release candidate for Android 10 and newer.",
    "The Wear OS companion APK and checksum files are included in the GitHub Release.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.1",
  apkUrl: "https://github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.1/little-orbit-1.0.0-rc.1.apk",
  published: true,
};

interface ApiRelease {
  version: string;
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
