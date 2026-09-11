import Link from "next/link";
import { AccountForm } from "@/components/account-form";
export const metadata = { title: "Create account" };
export default function SignupPage() { return <main id="main" className="form-page"><section><span className="eyebrow">Adults 18+</span><h1>A small space for something big.</h1><p>Registration happens here. After email verification, return to the Android app to sign in and connect with your partner.</p><Link href="/privacy">How Little Orbit protects your data →</Link></section><AccountForm mode="signup" /></main>; }
