import fs from "node:fs";
import path from "node:path";
import Ajv2020 from "ajv/dist/2020";
import type { AnySchema } from "ajv";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";

const protocol = path.resolve(process.cwd(), "../../protocol");
const names = ["location-batch", "note-operation", "pairing", "question-batch"];

function readJson(file: string): unknown {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "")) as unknown;
}

function validator(name: string) {
  const ajv = new Ajv2020({ allErrors: true });
  addFormats(ajv);
  const schema = readJson(path.join(protocol, "schemas/v1", `${name}.schema.json`));
  return ajv.compile(schema as AnySchema);
}

describe("versioned protocol fixtures", () => {
  for (const name of names) {
    it(`${name} accepts the valid fixture`, () => {
      expect(validator(name)(readJson(
        path.join(protocol, "fixtures/v1", `${name}.valid.json`),
      ))).toBe(true);
    });

    it(`${name} rejects the invalid fixture`, () => {
      expect(validator(name)(readJson(
        path.join(protocol, "fixtures/v1", `${name}.invalid.json`),
      ))).toBe(false);
    });
  }
});
