export interface ReleaseMetadata {
  version: string;
  minimumAndroid: string;
  sha256: string;
  releaseNotes: readonly string[];
  githubUrl: string;
  apkUrl?: string;
  published: boolean;
}

export const currentRelease: ReleaseMetadata = {
  version: "1.0.0-dev",
  minimumAndroid: "Android 10 (API 29)",
  sha256: "Pending first signed release",
  releaseNotes: ["The signed public APK has not been published yet.", "Source builds are for development and testing only."],
  githubUrl: process.env.GITHUB_RELEASE_URL ?? "https://github.com/OWNER/little-orbit/releases",
  published: false,
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
