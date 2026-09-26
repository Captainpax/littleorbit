import { describe, expect, it } from "vitest";
import { escapeXml, releaseRss } from "./rss";

describe("release RSS", () => {
  it("escapes untrusted release text and emits RSS 2.0", () => {
    expect(escapeXml('<tag a="b">&')).toBe("&lt;tag a=&quot;b&quot;&gt;&amp;");
    const xml = releaseRss([{
      version: "1.0 & next",
      versionCode: 8,
      githubUrl: "https://example.test",
      sha256: "a".repeat(64),
      minimumAndroid: 29,
      releaseNotes: ["Safer <updates>"],
      publishedAt: "2026-09-12T00:00:00Z",
    }]);
    expect(xml).toContain('<rss version="2.0">');
    expect(xml).toContain("1.0 &amp; next");
    expect(xml).not.toContain("Safer <updates>");
    expect(xml).toContain("Safer &amp;lt;updates&amp;gt;");
  });
});
