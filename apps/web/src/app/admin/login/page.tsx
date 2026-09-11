import { AdminLoginForm } from "@/components/admin-login-form";

export const metadata = { title: "Owner sign in" };

export default function AdminLoginPage() {
  return <main id="main" className="centered-form"><AdminLoginForm /></main>;
}
