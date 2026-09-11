import Link from "next/link";
import { PageIntro } from "@/components/page-intro";
import { getCurrentRelease } from "@/lib/release";

export const metadata = { title: "Download" };

export default async function DownloadPage() {
  const release = await getCurrentRelease();
  return <main id="main"><PageIntro eyebrow="Android download" title="Get Little Orbit">GitHub Releases is the canonical host for signed APK files, checksums, and source for each release.</PageIntro><section className="shell release-card"><div className="release-top"><div><span className="eyebrow">Current channel</span><h2>{release.version}</h2></div><span className={`release-state ${release.published ? "ready" : "pending"}`}>{release.published ? "Available" : "Development build"}</span></div><dl><div><dt>Minimum version</dt><dd>{release.minimumAndroid}</dd></div><div><dt>SHA-256</dt><dd><code>{release.sha256}</code></dd></div></dl><h3>Release notes</h3><ul>{release.releaseNotes.map((note) => <li key={note}>{note}</li>)}</ul><Link className={`button ${release.published ? "" : "button-disabled"}`} href={release.githubUrl} aria-disabled={!release.published}>View GitHub Releases</Link><p className="fine-print">Never install an APK whose checksum does not match the value shown here and in the matching GitHub Release.</p></section></main>;
}
