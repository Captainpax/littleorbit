import { AccountForm } from "@/components/account-form";
export const metadata = { title: "Reset password" };
export default function ResetPage() { return <main id="main" className="centered-form"><AccountForm mode="reset" /></main>; }
