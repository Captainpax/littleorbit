import { describe, expect, it } from "vitest";
import { currentRelease } from "./release";
describe("release metadata", () => { it("does not present an unsigned development build as downloadable", () => { expect(currentRelease.published).toBe(false); expect(currentRelease.sha256).toContain("Pending"); }); });
