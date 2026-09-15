import { PageIntro } from "@/components/page-intro";
import { formatReleaseDate, getReleaseHistory } from "@/lib/release";

export const metadata = { title: "Patch notes" };

export default async function PatchNotesPage() {
  const releases = await getReleaseHistory();
  return <main id="main">
    <PageIntro eyebrow="Signed releases" title="Patch notes">
      Follow every public Android and Wear OS release. The RSS feed uses the same immutable
      publication records as the in-app updater.
    </PageIntro>
    <section className="shell patch-notes-list" aria-label="Release history">
      {releases.map((release) => <article id={release.version} className="release-card" key={release.version}>
        <div className="release-top"><div><span className="eyebrow">Version code {release.versionCode}</span>
          <h2>{release.version}</h2></div><time dateTime={release.publishedAt}>
            {formatReleaseDate(release.publishedAt)}
          </time></div>
        <ul>{release.releaseNotes.map((note) => <li key={note}>{note}</li>)}</ul>
        <p className="fine-print">Android API {release.minimumAndroid}+ · SHA-256 <code>{release.sha256}</code></p>
        <a className="text-link" href={release.githubUrl}>Source and tag</a>
      </article>)}
      <a className="button button-secondary" href="/patch-notes.xml">Subscribe with RSS</a>
    </section>
  </main>;
}
