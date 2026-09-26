import Image from "next/image";
import Link from "next/link";

const navigation = [
  ["Showcase", "/showcase"],
  ["Download", "/download"],
  ["Patch notes", "/patch-notes"],
  ["Privacy", "/privacy"],
  ["Roadmap", "/roadmap"],
] as const;

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell nav-row">
        <Link className="brand" href="/" aria-label="Little Orbit home">
          <Image src="/logo.svg" width={42} height={42} alt="" priority />
          <span>Little Orbit</span>
        </Link>
        <nav aria-label="Main navigation">
          <ul className="nav-links">
            {navigation.map(([label, href]) => (
              <li key={href}><Link href={href}>{label}</Link></li>
            ))}
          </ul>
        </nav>
        <div className="nav-actions">
          <Link className="text-link" href="/signup">Create account</Link>
          <Link className="button button-small" href="/download">Get the app</Link>
        </div>
        <details className="mobile-menu">
          <summary aria-label="Open navigation menu">Menu</summary>
          <nav aria-label="Mobile navigation">
            {navigation.map(([label, href]) => <Link href={href} key={href}>{label}</Link>)}
            <Link href="/signup">Create account</Link>
          </nav>
        </details>
      </div>
    </header>
  );
}
