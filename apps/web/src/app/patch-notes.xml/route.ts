import { getReleaseHistory } from "@/lib/release";
import { releaseRss } from "@/lib/rss";

export async function GET() {
  const xml = releaseRss(await getReleaseHistory());
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
    },
  });
}
