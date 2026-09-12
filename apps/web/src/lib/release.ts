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

export function hostedApkPath(version: string): string {
  return `/api/v1/releases/${encodeURIComponent(version)}/apk`;
}

// Keep this verified fallback synchronized with every signed release so a brief API
// outage never removes the public APK download from the statically rendered page.
export const currentRelease: ReleaseMetadata = {
  version: "1.0.0-rc.5",
  versionCode: 5,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "044c7c068fde480407ed3f1d29ec7df4bdf19d1b855e334f4e30a769732848ed",
  releaseNotes: [
    "Introduces a focused five-question flow with drafts, review, waiting, and shared reveal.",
    "Adds playful partner guesses, weighted choices, history, catch-up, and a guided custom-question composer.",
    "Polls only completion status in the background and keeps answer content inside the open app.",
    "Uses validated global Ollama questions with curated fallback and owner review evidence.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.5",
  apkUrl: hostedApkPath("1.0.0-rc.5"),
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
      apkUrl: hostedApkPath(release.version),
      published: true,
    };
  } catch {
    return currentRelease;
  }
}
