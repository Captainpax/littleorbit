import { redirect } from "next/navigation";
export default function GitHubPage() { redirect(process.env.GITHUB_REPOSITORY_URL ?? "https://github.com/Captainpax/littleorbit"); }
