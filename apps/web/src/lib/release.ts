export interface ReleaseMetadata {
  version: string;
  versionCode?: number;
  minimumSupportedVersionCode?: number;
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

/** Turns stored Markdown release prose into clean text rows for public cards and RSS. */
export function releaseNoteLines(markdown: string): readonly string[] {
  let omitSection = false;
  return markdown.replaceAll("\\n", "\n").split(/\r?\n/u).flatMap((rawLine) => {
    const line = rawLine.trim();
    const section = /^#{2,6}\s+(.+)$/u.exec(line);
    if (section) {
      omitSection = /^(?:candidate status|verified so far)$/iu.test(section[1] ?? "");
      return [];
    }
    if (!line || omitSection || /^#\s/u.test(line)) return [];
    const withoutBullet = line.replace(/^(?:[-*+]\s+|\d+[.)]\s+)/u, "");
    return [withoutBullet
      .replace(/!\[([^\]]*)\]\([^)]*\)/gu, "$1")
      .replace(/\[([^\]]+)\]\([^)]*\)/gu, "$1")
      .replace(/`([^`]+)`/gu, "$1")
      .replace(/\*\*([^*]+)\*\*/gu, "$1")
      .replace(/__([^_]+)__/gu, "$1")];
  });
}

/** Keeps the download card concise while the patch-notes route retains full history. */
export function releaseNoteHighlights(markdown: string): readonly string[] {
  return releaseNoteLines(markdown).slice(0, 5);
}

/** Formats immutable publication instants consistently on every deployment host. */
export function formatReleaseDate(publishedAt: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" })
    .format(new Date(publishedAt));
}

// Keep this verified fallback synchronized with every signed release so a brief API
// outage never removes the public APK download from the statically rendered page.
export const currentRelease: ReleaseMetadata = {
  version: "1.1.0",
  versionCode: 25,
  minimumSupportedVersionCode: 23,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "9b205633c004d4681413cc10592bb1ebc628dde8f3822754387552b2a09b101f",
  releaseNotes: [
    "Adds a dedicated Watch settings page with one explicitly managed watch and private content controls.",
    "Adds an explicit five-step install, update, repair, and private-removal wizard.",
    "Adds vertically scrolling Together, Countdown, and confirmed Smooch destinations on Wear OS.",
    "Protects watch actions with target and relationship generations plus a five-item, 15-minute encrypted queue.",
    "Adds an improved tile and separate Nearby and Countdown watch-face complications.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.1.0",
  apkUrl: hostedApkPath("1.1.0"),
  wear: {
    apkUrl: hostedWearApkPath("1.1.0"),
    sha256: "357b176ba4d6d07b7eae40601aa8595806a1c0aad32b6a1dcbed41271e000950",
    sizeBytes: 14730416,
    versionCode: 19,
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
  minimum_supported_version_code: number;
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
      minimumSupportedVersionCode: release.minimum_supported_version_code,
      minimumAndroid: `Android API ${release.minimum_android} or newer`,
      sha256: release.sha256,
      releaseNotes: releaseNoteHighlights(release.release_notes),
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
      releaseNotes: releaseNoteLines(release.release_notes),
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
    publishedAt: "2026-09-19T20:27:09.9055481Z",
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
