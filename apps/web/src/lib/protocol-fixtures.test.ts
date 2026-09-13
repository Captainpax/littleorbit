import fs from "node:fs";
import path from "node:path";
import Ajv2020 from "ajv/dist/2020";
import type { AnySchema } from "ajv";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";

const protocol = path.resolve(process.cwd(), "../../protocol");
const contracts = [
  ["v1", "location-batch"], ["v1", "note-operation"],
  ["v1", "pairing"], ["v1", "question-batch"],
  ["v1", "orbit-profile"], ["v1", "release-history"],
  ["v1", "smooch"],
  ["v2", "question-batch"], ["v2", "quiz-day"],
  ["v3", "together-time"],
] as const;

function readJson(file: string): unknown {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "")) as unknown;
}

function validator(version: string, name: string) {
  const ajv = new Ajv2020({ allErrors: true });
  addFormats(ajv);
  const schema = readJson(path.join(protocol, "schemas", version, `${name}.schema.json`));
  return ajv.compile(schema as AnySchema);
}

describe("versioned protocol fixtures", () => {
  for (const [version, name] of contracts) {
    it(`${version}/${name} accepts the valid fixture`, () => {
      expect(validator(version, name)(readJson(
        path.join(protocol, "fixtures", version, `${name}.valid.json`),
      ))).toBe(true);
    });

    it(`${version}/${name} rejects the invalid fixture`, () => {
      expect(validator(version, name)(readJson(
        path.join(protocol, "fixtures", version, `${name}.invalid.json`),
      ))).toBe(false);
    });
  }
});
