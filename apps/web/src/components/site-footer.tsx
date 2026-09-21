import Image from "next/image";
import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div>
          <div className="brand footer-brand"><Image src="/logo.svg" width={38} height={38} alt="" />Little Orbit</div>
          <p>Free, open, and made for two curious people.</p>
        </div>
        <div><strong>Project</strong><Link href="/showcase">Showcase</Link><Link href="/patch-notes">Patch notes</Link><Link href="/roadmap">Roadmap</Link><Link href="/contributors">Contributors</Link></div>
        <div><strong>Trust</strong><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/status">Status</Link></div>
        <div><strong>Build</strong><Link href="/github">GitHub</Link><Link href="/download">Android download</Link></div>
      </div>
      <div className="shell footer-bottom"><span>© 2026 Little Orbit contributors</span><span>MIT licensed · no paywalls</span></div>
    </footer>
  );
}
