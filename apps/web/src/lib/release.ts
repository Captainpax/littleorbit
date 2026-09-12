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

export function hostedApkPath(version: string): string {
  return `/api/v1/releases/${encodeURIComponent(version)}/apk`;
}

export function hostedWearApkPath(version: string): string {
  return `/api/v1/releases/${encodeURIComponent(version)}/wear-apk`;
}

// Keep this verified fallback synchronized with every signed release so a brief API
// outage never removes the public APK download from the statically rendered page.
export const currentRelease: ReleaseMetadata = {
  version: "1.0.0-rc.6",
  versionCode: 6,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "71093232e3d3dc5c0523a785ad9314de2fa14a0338ef5c9ae336962caa9033fc",
  releaseNotes: [
    "Keeps every phone screen clear of status bars, navigation bars, display cutouts, and the keyboard.",
    "Separates a mutually confirmed relationship start date from the location-derived nearby-time estimate.",
    "Adds guided notification and precise background-location setup with live consent status.",
    "Refreshes the home widget and Wear OS surfaces with honest stale states and a verified watch installer.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.6",
  apkUrl: hostedApkPath("1.0.0-rc.6"),
  wear: {
    apkUrl: hostedWearApkPath("1.0.0-rc.6"),
    sha256: "857197277ac5da7c23db816ae8dd04f95defa137c4870a0cb1ef2abbac086027",
    sizeBytes: 14124686,
    versionCode: 6,
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
