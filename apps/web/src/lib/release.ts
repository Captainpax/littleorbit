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
  version: "1.2.0",
  versionCode: 28,
  minimumSupportedVersionCode: 23,
  minimumAndroid: "Android 10 (API 29)",
  sha256: "aaa8c98d452db6d87c687f25cd2630432b64481ab6753c2bdb7bdb5baa7dc04f",
  releaseNotes: [
    "Adds shared partner-assigned names across authorized Little Orbit surfaces.",
    "Adds private post-reveal quiz ratings, tags, and optional consented reviews.",
    "Adds thresholded Saturday learning and Sunday generation for the next quiz week.",
    "Uses semantic concept memory to prevent repeated questions with different formatting.",
    "Moves administration to the separate device-bound Big Orbit Android app.",
  ],
  githubUrl: "https://github.com/Captainpax/littleorbit/releases/tag/v1.2.0",
  apkUrl: hostedApkPath("1.2.0"),
  wear: {
    apkUrl: hostedWearApkPath("1.2.0"),
    sha256: "b5f2af70402b6c8c5ff6feae91b5f23a32bd7c0ccea91b032ab705f8013d7f2b",
    sizeBytes: 14737940,
    versionCode: 20,
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
    publishedAt: "2026-09-21T12:10:32.956306Z",
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
