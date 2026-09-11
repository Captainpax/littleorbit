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
  version: "1.0.0-rc.2",
  minimumAndroid: "Android 10 (API 29)",
  sha256: "8cea61f20cd0da6e4144b8eedb58c14d1ea16371e10df7d8e4b8f9068b0f0d10",
  releaseNotes: [
    "Keeps verified accounts signed in while they connect with a partner.",
    "Clears account-scoped caches and queued location data when account context changes.",
    "Includes the complete widget database migration path.",
    "The Wear OS companion APK and checksum files are included in the GitHub Release.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.2",
  apkUrl: "https://github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.2/little-orbit-1.0.0-rc.2.apk",
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
