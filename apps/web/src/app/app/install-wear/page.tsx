import Link from "next/link";
import { PageIntro } from "@/components/page-intro";

export const metadata = { title: "Install on Wear OS" };

export default function InstallWearPage() {
  return <main id="main">
    <PageIntro eyebrow="Wear OS companion" title="Continue on your phone">
      Little Orbit’s phone app now downloads, verifies, and sends the watch app over your
      private Wi-Fi. Open More → Install on watch and follow the one-time pairing steps.
    </PageIntro>
    <section className="shell release-card">
      <h2>No computer required</h2>
      <ol><li>Put your phone and watch on the same private Wi-Fi.</li>
        <li>Open Little Orbit on the phone, then open More.</li>
        <li>Tap Install on watch. The app checks the APK signature before any connection.</li></ol>
      <div className="release-actions">
        <a className="button" href="https://lil-orb.pax-kun.com/app/install-wear">Open Little Orbit</a>
        <Link className="button button-secondary" href="/download">Download the phone app</Link>
      </div>
    </section>
  </main>;
}
