import Image from "next/image";
import { PageIntro } from "@/components/page-intro";

export const metadata = { title: "Showcase" };

export default function ShowcasePage() {
  return (
    <main id="main">
      <PageIntro eyebrow="A calm shared space" title="Designed around the two of you">
        Little Orbit keeps daily rituals close without turning a relationship into a scoreboard.
      </PageIntro>
      <section className="shell showcase-stack">
        <figure>
          <Image
            src="/concepts/android-shell-rc12-concept.png"
            width={1312}
            height={1199}
            alt="RC12 concept showing the Little Orbit navigation drawer, Home dashboard, and contextual activity panel"
            priority
          />
          <figcaption>
            RC12 app shell: one calm destination drawer on the left and screen-specific tools on
            the right.
          </figcaption>
        </figure>
        <figure>
          <Image
            src="/concepts/android-space-editor-rc12-concept.png"
            width={1222}
            height={1287}
            alt="RC12 concept showing the Our Space document library, Markdown keyboard dock, attachment cards, and document tools panel"
          />
          <figcaption>
            Our Space keeps Markdown tools beside the keyboard and makes every attachment state
            explicit.
          </figcaption>
        </figure>
        <figure>
          <Image
            src="/concepts/android-wear-concept.png"
            width={1536}
            height={1024}
            alt="Concept showing Little Orbit phone dashboard, quiz, notes, home widget and watch views"
          />
          <figcaption>Phone, home widget, and Wear OS visual direction.</figcaption>
        </figure>
        <figure>
          <Image
            src="/concepts/android-update-more-concept.png"
            width={1536}
            height={1024}
            alt="Concept showing pairing, update confirmation, secure download progress, and the More screen"
          />
          <figcaption>
            RC3 updater and More screen study. Android always asks before installing verified bytes.
          </figcaption>
        </figure>
        <figure>
          <Image
            src="/concepts/android-our-space-rc11-concept.png"
            width={1254}
            height={1254}
            alt="RC11 concept showing the Our Space note library, Markdown editor, attachment tray, preview, and conflict choices"
          />
          <figcaption>
            RC11 Our Space direction: a library first, then a focused Markdown editor with
            private attachments and explicit conflict recovery.
          </figcaption>
        </figure>
        <figure>
          <Image
            src="/concepts/android-smooches-rc11-concept.png"
            width={1672}
            height={941}
            alt="RC11 concept showing the centered Smooch tab, emoji picker, orbit pulse, weekly totals, and history"
          />
          <figcaption>
            RC11 Smooch direction: one warm action, clear hourly availability, and shared
            weekly memories without rankings.
          </figcaption>
        </figure>
        <div className="walkthrough-grid">
          <article><span>01</span><h2>Answer in your own time</h2><p>Each answer stays hidden until both people submit. There is no pressure to match.</p></article>
          <article><span>02</span><h2>Keep useful things close</h2><p>Countdowns and editable notes support ordinary planning as well as meaningful dates.</p></article>
          <article><span>03</span><h2>Update with confidence</h2><p>The phone verifies the APK package, version, size, hash, and pinned signer before Android asks to install it.</p></article>
        </div>
      </section>
    </main>
  );
}
