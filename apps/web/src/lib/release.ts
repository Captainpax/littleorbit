export interface ReleaseMetadata {
  version: string;
  versionCode?: number;
  minimumAndroid: string;
  sha256: string;
  releaseNotes: readonly string[];
  githubUrl: string;
  apkUrl?: string;
  wear?: {
    apkUrl: string;
    sha256: string;
    sizeBytes: number;
    versionCode: number;
    minimumAndroid: number;
  };
  published: boolean;
}

export interface ReleaseHistoryItem {
  version: string;
  versionCode: number;
  githubUrl: string;
  sha256: string;
  minimumAndroid: number;
  releaseNotes: readonly string[];
  publishedAt: string;
}

export function hostedApkPath(version: string): string {
  return `/api/v1/releases/${encodeURIComponent(version)}/apk`;
}

export function hostedWearApkPath(version: string): string {
  return `/api/v1/releases/${encodeURIComponent(version)}/wear-apk`;
}

// Keep this verified fallback synchronized with every signed release so a brief API
// outage never removes the public APK download from the statically rendered page.
export const currentRelease: ReleaseMetadata = {
  version: "1.0.0-rc.11.2",
  versionCode: 14,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "3faa50028016260de50fe59f8c5e7bfa381660df92d67e879d0634e6a410f44a",
  releaseNotes: [
    "Adds the RC11 Our Space, cursor-stable Markdown, private attachments, and dedicated Smooch tab.",
    "Keeps update actions visible even when a release has longer notes.",
    "Closes the verified APK stream before Android commits its installation session.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.11.2",
  apkUrl: hostedApkPath("1.0.0-rc.11.2"),
  wear: {
    apkUrl: hostedWearApkPath("1.0.0-rc.11.2"),
    sha256: "3431664f1466f2241b3962c7da7d9b568bdaa04a0fd6213f14fda1c46c90d307",
    sizeBytes: 14133462,
    versionCode: 13,
    minimumAndroid: 30,
  },
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
  wear_apk_url?: string | null;
  wear_sha256?: string | null;
  wear_size_bytes?: number | null;
  wear_version_code?: number | null;
  wear_minimum_android?: number | null;
}

interface ApiReleaseHistoryItem {
  version: string;
  version_code: number;
  github_release_url: string;
  sha256: string;
  minimum_android: number;
  release_notes: string;
  published_at: string;
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
      wear: mapWearRelease(release),
      published: true,
    };
  } catch {
    return currentRelease;
  }
}

export async function getReleaseHistory(): Promise<readonly ReleaseHistoryItem[]> {
  const baseUrl = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${baseUrl}/v1/releases/history?limit=20`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return fallbackHistory();
    const releases = await response.json() as ApiReleaseHistoryItem[];
    return releases.map((release) => ({
      version: release.version,
      versionCode: release.version_code,
      githubUrl: release.github_release_url,
      sha256: release.sha256,
      minimumAndroid: release.minimum_android,
      releaseNotes: release.release_notes.split("\n").filter(Boolean),
      publishedAt: release.published_at,
    }));
  } catch {
    return fallbackHistory();
  }
}

function fallbackHistory(): readonly ReleaseHistoryItem[] {
  return [{
    version: currentRelease.version,
    versionCode: currentRelease.versionCode ?? 0,
    githubUrl: currentRelease.githubUrl,
    sha256: currentRelease.sha256,
    minimumAndroid: 29,
    releaseNotes: currentRelease.releaseNotes,
    publishedAt: "2026-09-13T04:42:00Z",
  }];
}

function mapWearRelease(release: ApiRelease): ReleaseMetadata["wear"] {
  if (
    !release.wear_apk_url
    || !release.wear_sha256
    || !release.wear_size_bytes
    || !release.wear_version_code
    || !release.wear_minimum_android
  ) return undefined;
  return {
    apkUrl: hostedWearApkPath(release.version),
    sha256: release.wear_sha256,
    sizeBytes: release.wear_size_bytes,
    versionCode: release.wear_version_code,
    minimumAndroid: release.wear_minimum_android,
  };
}
