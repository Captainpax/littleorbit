import { AdminEnrollmentForm } from "@/components/admin-enrollment-form";

export const metadata = { title: "Enroll owner MFA" };

export default function AdminEnrollPage() {
  return <main id="main" className="centered-form"><AdminEnrollmentForm /></main>;
}
