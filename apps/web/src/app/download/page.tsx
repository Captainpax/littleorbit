import Link from "next/link";
import { PageIntro } from "@/components/page-intro";
import { getCurrentRelease } from "@/lib/release";

export const metadata = { title: "Download" };

export default async function DownloadPage() {
  const release = await getCurrentRelease();
  return <main id="main"><PageIntro eyebrow="Android download" title="Get Little Orbit">Download the signed APK directly from Little Orbit. Interrupted transfers can resume from the same server; GitHub keeps the matching source and release history.</PageIntro><section className="shell release-card"><div className="release-top"><div><span className="eyebrow">Current channel</span><h2>{release.version}</h2></div><span className={`release-state ${release.published ? "ready" : "pending"}`}>{release.published ? "Available" : "Metadata unavailable"}</span></div><dl><div><dt>Minimum version</dt><dd>{release.minimumAndroid}</dd></div><div><dt>SHA-256</dt><dd><code>{release.sha256}</code></dd></div></dl><h3>Release notes</h3><ul>{release.releaseNotes.map((note) => <li key={note}>{note}</li>)}</ul><div className="release-actions">{release.published && release.apkUrl && <Link className="button" href={release.apkUrl}>Download signed APK</Link>}<Link className="button button-secondary" href={release.githubUrl}>View source release</Link></div><p className="fine-print">Little Orbit verifies the exact file size, checksum, package, version, and signing certificate before Android opens its installer.</p></section></main>;
}
