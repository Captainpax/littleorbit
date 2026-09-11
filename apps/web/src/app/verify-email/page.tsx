import { AccountForm } from "@/components/account-form";
export const metadata = { title: "Verify email" };
export default function VerifyPage() { return <main id="main" className="verification-forms shell"><AccountForm mode="verify" /><AccountForm mode="resend" /></main>; }
