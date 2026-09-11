import Image from "next/image";
import { PageIntro } from "@/components/page-intro";

export const metadata = { title: "Showcase" };

export default function ShowcasePage() {
  return <main id="main"><PageIntro eyebrow="A calm shared space" title="Designed around the two of you">Little Orbit keeps daily rituals close without turning a relationship into a scoreboard.</PageIntro><section className="shell showcase-stack"><figure><Image src="/concepts/android-wear-concept.png" width={1536} height={1024} alt="Concept showing Little Orbit phone dashboard, quiz, notes, home widget and watch views" priority /><figcaption>Android, home widget, and Wear OS concept. Real product screenshots will be added as release gates pass.</figcaption></figure><div className="walkthrough-grid"><article><span>01</span><h2>Answer in your own time</h2><p>Each answer stays hidden until both people submit. There is no pressure to match.</p></article><article><span>02</span><h2>Keep useful things close</h2><p>Countdowns and editable notes support ordinary planning as well as meaningful dates.</p></article><article><span>03</span><h2>See an honest estimate</h2><p>Together-time includes accuracy and last-updated context. Raw coordinates expire within 24 hours.</p></article></div></section></main>;
}
