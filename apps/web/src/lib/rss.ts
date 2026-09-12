import type { ReleaseHistoryItem } from "./release";

export function escapeXml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
}

export function releaseRss(
  releases: readonly ReleaseHistoryItem[], baseUrl = "https://lil-orb.pax-kun.com",
): string {
  const items = releases.map((release) => {
    const notes = release.releaseNotes.map((note) => `<li>${escapeXml(note)}</li>`).join("");
    const description = escapeXml(`<ul>${notes}</ul>`);
    const link = `${baseUrl}/patch-notes#${encodeURIComponent(release.version)}`;
    return `<item><title>Little Orbit ${escapeXml(release.version)}</title>`
      + `<link>${link}</link><guid isPermaLink="true">${link}</guid>`
      + `<pubDate>${new Date(release.publishedAt).toUTCString()}</pubDate>`
      + `<description>${description}</description></item>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>`
    + `<title>Little Orbit patch notes</title><link>${baseUrl}/patch-notes</link>`
    + `<description>Signed Android and Wear OS release notes for Little Orbit.</description>`
    + `<language>en-us</language>${items}</channel></rss>`;
}
