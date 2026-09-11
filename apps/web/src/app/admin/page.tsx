import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  publishRelease,
  regenerateBatch,
  replaceCuratedBank,
  resolveReport,
  revokeSessions,
  setRegistration,
  updateAccount,
} from "./actions";

export const metadata = { title: "Owner console" };
export const dynamic = "force-dynamic";

interface AdminSession {
  token: string;
  config: Record<string, unknown>;
}

interface Collection {
  items: Array<Record<string, unknown>>;
}

async function requireAdminSession(): Promise<AdminSession> {
  const token = (await cookies()).get("little_orbit_admin")?.value;
  if (!token) redirect("/admin/login");
  const baseUrl = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/v1/admin/configuration`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    redirect("/admin/login");
  }
  if (!response.ok) redirect("/admin/login");
  const result = await response.json() as { values: Record<string, unknown> };
  return { token, config: result.values };
}

async function adminGet<T>(path: string, token: string, fallback: T): Promise<T> {
  const baseUrl = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${baseUrl}/v1/admin/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    return response.ok ? await response.json() as T : fallback;
  } catch {
    return fallback;
  }
}

function count(values: Record<string, unknown>, key: string): number {
  const value = values[key];
  return typeof value === "number" ? value : 0;
}

export default async function AdminPage() {
  const session = await requireAdminSession();
  const [overview, batches, reports, accounts, couples, events, bank] = await Promise.all([
    adminGet<{ values: Record<string, unknown> }>("overview", session.token, { values: {} }),
    adminGet<Collection>("question-batches", session.token, { items: [] }),
    adminGet<Collection>("question-reports", session.token, { items: [] }),
    adminGet<Collection>("accounts", session.token, { items: [] }),
    adminGet<Collection>("couples", session.token, { items: [] }),
    adminGet<Collection>("security-events", session.token, { items: [] }),
    adminGet<Array<Record<string, unknown>>>("curated-bank", session.token, []),
  ]);
  const serviceValues = overview.values.services;
  const services = typeof serviceValues === "object" && serviceValues
    ? serviceValues as Record<string, unknown>
    : {};

  return <main id="main" className="admin-shell">
    <aside className="admin-sidebar">
      <b>Little Orbit</b><span>Owner console</span>
      <nav>
        <a className="active" href="#overview">Overview</a>
        <a href="#questions">Question pipeline</a>
        <a href="#reports">Reports</a>
        <a href="#accounts">Accounts</a>
        <a href="#content">Content & release</a>
        <a href="#security">Security</a>
      </nav>
      <small>Relationship content access is disabled</small>
    </aside>
    <div className="admin-main">
      <div className="admin-heading">
        <div><span className="eyebrow">Privacy-safe operations</span><h1>Owner console</h1>
          <p>Live service state and metadata from the authenticated API.</p></div>
        <span className="admin-avatar" aria-label="Owner account">LO</span>
      </div>
      <section id="overview" className="health-grid">
        {Object.entries(services).filter(([name]) => name !== "scheduler_days_covered").map(([name, value]) =>
          <article key={name}><span className="health-orb healthy" /><div>
            <small>{name.replaceAll("_", " ")}</small><b>{String(value)}</b>
          </div></article>)}
      </section>
      <div className="admin-content">
        <section id="questions" className="panel pipeline">
          <div className="panel-heading"><div><span className="eyebrow">Daily question pipeline</span>
            <h2>{count(services, "scheduler_days_covered")} days covered</h2></div>
            <span className="release-state ready">Live</span></div>
          <div className="pipeline-metrics">
            <div><b>{count(overview.values, "accounts")}</b><span>accounts</span></div>
            <div><b>{count(overview.values, "active_couples")}</b><span>active couples</span></div>
            <div><b>{count(overview.values, "deletion_jobs")}</b><span>deletion jobs</span></div>
          </div>
          {batches.items.slice(0, 4).map((batch) =>
            <div className="batch-row" key={String(batch.id)}>
              <span>{String(batch.publish_date)}</span>
              <div className="progress"><i style={{ width: "100%" }} /></div>
              <b>{String(batch.selected_count)} selected</b>
              <small>{batch.fallback_reason ? `fallback: ${String(batch.fallback_reason)}` : String(batch.model)}</small>
              <form action={regenerateBatch}>
                <input type="hidden" name="publish_date" value={String(batch.publish_date)} />
                <button className="text-button" type="submit">Regenerate</button>
              </form>
            </div>)}
          {!batches.items.length && <p>No generation batch has been stored yet.</p>}
        </section>
        <section id="reports" className="panel attention">
          <span className="eyebrow">Needs attention</span>
          {reports.items.map((report) => <article key={String(report.report_id)}>
            <b>!</b><div><strong>{String(report.prompt)}</strong><span>{String(report.reason)}</span>
              <form action={resolveReport} className="inline-actions">
                <input type="hidden" name="report_id" value={String(report.report_id)} />
                <label><input type="checkbox" name="disable_question" /> Disable globally</label>
                <button className="text-button" type="submit">Resolve</button>
              </form></div></article>)}
          {!reports.items.length && <p>No pending question reports.</p>}
          <article><b>{count(overview.values, "deletion_jobs")}</b><div><strong>Deletion jobs</strong>
            <span>Scheduled privacy erasures</span></div></article>
          <article><b>{count(services, "email_pending")}</b><div><strong>Email queue</strong>
            <span>Encrypted messages waiting for SMTP</span></div></article>
        </section>
      </div>
      <section id="accounts" className="panel admin-table-panel">
        <span className="eyebrow">Account metadata</span><h2>Users and couples</h2>
        <div className="admin-records">
          {accounts.items.map((account) => <article key={String(account.id)}>
            <div><strong>{String(account.display_name)}</strong><span>{String(account.email)}</span>
              <small>{account.verified_at ? "verified" : "unverified"} · {account.suspended_at ? "suspended" : "active"}</small></div>
            {!account.is_admin && <div className="inline-actions">
              <form action={updateAccount}>
                <input type="hidden" name="account_id" value={String(account.id)} />
                <input type="hidden" name="suspended" value={account.suspended_at ? "false" : "true"} />
                <button className="text-button" type="submit">{account.suspended_at ? "Restore" : "Suspend"}</button>
              </form>
              <form action={revokeSessions}>
                <input type="hidden" name="account_id" value={String(account.id)} />
                <button className="text-button" type="submit">Revoke sessions</button>
              </form>
            </div>}
          </article>)}
        </div>
        <p className="admin-privacy">{couples.items.length} relationship containers. Only IDs, dates, and member counts are available here.</p>
      </section>
      <section id="content" className="panel admin-forms">
        <div><span className="eyebrow">Operations</span><h2>Registration and releases</h2></div>
        <div className="inline-actions">
          <form action={setRegistration}><input type="hidden" name="enabled" value="true" /><button type="submit">Open registration</button></form>
          <form action={setRegistration}><input type="hidden" name="enabled" value="false" /><button type="submit">Pause registration</button></form>
        </div>
        <form action={publishRelease} className="admin-form-grid">
          <label>Version<input name="version" required placeholder="1.0.0" /></label>
          <label>Minimum Android<input name="minimum_android" type="number" min="29" max="36" defaultValue="29" required /></label>
          <label>Signed APK URL<input name="apk_url" type="url" required /></label>
          <label>GitHub Release URL<input name="github_release_url" type="url" required /></label>
          <label>SHA-256<input name="sha256" pattern="[a-f0-9]{64}" required /></label>
          <label>Release notes<textarea name="release_notes" required /></label>
          <label><input name="publish" type="checkbox" /> Publish on download page</label>
          <button type="submit">Save release metadata</button>
        </form>
        <details><summary>Curated question bank ({bank.length})</summary>
          <form action={replaceCuratedBank} className="admin-bank-form">
            <label>Validated JSON<textarea name="questions" defaultValue={JSON.stringify(bank, null, 2)} required /></label>
            <button type="submit">Validate and replace bank</button>
          </form>
        </details>
      </section>
      <section id="security" className="panel registration-panel">
        <div><span className="eyebrow">Security events</span><h2>Secrets are redacted</h2>
          <p>Environment: {String(session.config.environment ?? "configured")} · {events.items.length} recent audit events</p>
          <ul>{events.items.slice(0, 5).map((event) => <li key={String(event.id)}>
            {String(event.event_type)} — {String(event.outcome)}</li>)}</ul></div>
        <span className="release-state ready">MFA verified</span>
      </section>
      <p className="admin-privacy">The API excludes notes, quiz answers, coordinates, and couple exports from every console response.</p>
    </div>
  </main>;
}
