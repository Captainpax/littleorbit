import Image from "next/image";
import Link from "next/link";
import { Icon } from "@/components/icon";

const features = [
  { icon: "spark" as const, title: "Daily questions", text: "Five thoughtful prompts each day. Answers stay private until you both submit." },
  { icon: "note" as const, title: "A space you share", text: "Write notes together, keep drafts offline, and return to the moments you want to remember." },
  { icon: "clock" as const, title: "Time that matters", text: "Count down to what is next and gently estimate the time you spend together." },
];

export default function HomePage() {
  return (
    <main id="main">
      <section className="hero shell">
        <div className="hero-copy">
          <span className="eyebrow"><span className="status-dot" />Free and open source</span>
          <h1>Closer,<br /><em>every day.</em></h1>
          <p>A private place for two — daily questions, shared notes, countdowns, and time together.</p>
          <div className="button-row">
            <Link className="button" href="/download">Download for Android</Link>
            <Link className="button button-secondary" href="/signup">Create account</Link>
          </div>
          <small>Android 10+ · no subscriptions · source available</small>
        </div>
        <div className="hero-art" aria-label="Little Orbit phone and watch preview">
          <div className="orbit-ring orbit-one" /><div className="orbit-ring orbit-two" />
          <div className="phone-card">
            <div className="phone-top"><span>9:41</span><span>● ●</span></div>
            <div className="couple-orbit"><Image src="/logo.svg" width={84} height={84} alt="" /></div>
            <span className="phone-kicker">Together for</span><strong className="day-count">642 days</strong>
            <div className="question-card"><span>Today&apos;s orbit</span><b>What made you smile today?</b><i>Answer privately →</i></div>
            <div className="mini-row"><div><span>Next adventure</span><b>18 days</b></div><div><span>Shared note</span><b>Groceries</b></div></div>
          </div>
          <div className="watch-card"><Image src="/logo.svg" width={44} height={44} alt="" /><b>642</b><span>days together</span><small>fresh now</small></div>
          <span className="star star-a">✦</span><span className="star star-b">✦</span><span className="star star-c">·</span>
        </div>
      </section>

      <section className="feature-strip shell" aria-labelledby="features-title">
        <div className="section-heading"><span className="eyebrow">Made for two</span><h2 id="features-title">Small rituals. Real connection.</h2></div>
        <div className="feature-grid">
          {features.map((feature) => (
            <article key={feature.title}><span className="icon-box"><Icon name={feature.icon} /></span><h3>{feature.title}</h3><p>{feature.text}</p></article>
          ))}
        </div>
      </section>

      <section className="promise shell">
        <div className="promise-copy"><span className="eyebrow">A simple promise</span><h2>Free for everyone.<br /><em>Open for good.</em></h2><p>Connection should not sit behind a paywall. Little Orbit has no premium tier, no ads, and no sale of your personal data.</p><Link className="arrow-link" href="/privacy">Read our privacy design <span>→</span></Link></div>
        <div className="promise-cards"><div><Icon name="shield" /><strong>Private by design</strong><span>Your relationship content stays between the two of you.</span></div><div><Icon name="code" /><strong>Open source</strong><span>Read the code, learn from it, or help make it better.</span></div><div><Icon name="heart" /><strong>Always complete</strong><span>Donations may support hosting; features remain free.</span></div></div>
      </section>

      <section className="final-cta shell"><div><span className="eyebrow">Your shared space is waiting</span><h2>Start your little orbit.</h2><p>Create an account on the web, then connect privately in the Android app.</p></div><div className="button-row"><Link className="button" href="/signup">Join Little Orbit</Link><Link className="button button-secondary" href="/showcase">Explore the app</Link></div></section>
    </main>
  );
}
