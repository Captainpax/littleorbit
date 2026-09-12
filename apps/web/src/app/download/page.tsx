import { PageIntro } from "@/components/page-intro";
import { getCurrentRelease } from "@/lib/release";

export const metadata = { title: "Download" };

export default async function DownloadPage() {
  const release = await getCurrentRelease();
  return <main id="main">
    <PageIntro eyebrow="Android download" title="Get Little Orbit">
      Download the signed APK directly from Little Orbit. Interrupted transfers can resume
      from the same server; GitHub keeps the matching source and release history.
    </PageIntro>
    <section className="shell release-card">
      <div className="release-top"><div><span className="eyebrow">Current channel</span>
        <h2>{release.version}</h2></div>
        <span className={`release-state ${release.published ? "ready" : "pending"}`}>
          {release.published ? "Available" : "Metadata unavailable"}
        </span>
      </div>
      <dl><div><dt>Minimum version</dt><dd>{release.minimumAndroid}</dd></div>
        <div><dt>SHA-256</dt><dd><code>{release.sha256}</code></dd></div></dl>
      <h3>Release notes</h3>
      <ul>{release.releaseNotes.map((note) => <li key={note}>{note}</li>)}</ul>
      <div className="release-actions">
        {release.published && release.apkUrl
          ? <a className="button" href={release.apkUrl}>Download signed APK</a>
          : null}
        <a className="button button-secondary" href={release.githubUrl}>View source release</a>
      </div>
      <p className="fine-print">Little Orbit verifies the exact file size, checksum, package,
        version, and signing certificate before Android opens its installer.</p>
    </section>
    <section id="wear" className="shell release-card">
      <span className="eyebrow">Optional Wear OS companion</span>
      <h2>Install Little Orbit on your watch</h2>
      <p>The watch build is free and self-hosted. The phone app verifies its exact bytes,
        package, version, watch requirement, and signing certificate before sending it over
        your private Wi-Fi.</p>
      {release.wear ? <dl>
        <div><dt>Wear OS minimum</dt><dd>API {release.wear.minimumAndroid}</dd></div>
        <div><dt>Wear APK SHA-256</dt><dd><code>{release.wear.sha256}</code></dd></div>
      </dl> : <p className="fine-print">Wear metadata is unavailable for this release.</p>}
      <ol><li>Install or update the Little Orbit phone app.</li>
        <li>Open More → Install on watch.</li>
        <li>Follow the one-time Wireless debugging pairing guide on your phone.</li></ol>
      <div className="release-actions">
        <a className="button" href="/app/install-wear">Open phone installer guide</a>
        {release.wear
          ? <a className="button button-secondary" href={release.wear.apkUrl}>Wear APK only</a>
          : null}
      </div>
      <p className="fine-print">The encrypted authorization stays on the phone for future
        watch updates. Older security patches show a clear warning before continuing.</p>
    </section>
  </main>;
}
