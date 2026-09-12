import Link from "next/link";
import { PageIntro } from "@/components/page-intro";

export const metadata = { title: "Return to Little Orbit" };

export default function AppSignInPage() {
  return <main id="main">
    <PageIntro eyebrow="Email verified" title="Return to your little orbit">
      Android should open the verified Little Orbit app link. If the app is not installed,
      download the signed release directly from Little Orbit.
    </PageIntro>
    <section className="shell release-card">
      <h2>Your account is ready</h2>
      <p>Open Little Orbit and sign in with the password you created.</p>
      <Link className="button" href="/download">Go to downloads</Link>
    </section>
  </main>;
}
