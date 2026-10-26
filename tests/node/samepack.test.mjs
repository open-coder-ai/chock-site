// The deep-link comparison: a selection is taken without a banner only when every hash matches.
import assert from "node:assert/strict";
import { test } from "node:test";

import { samePack } from "../../static/js/samepack.js";

const known = new Map([
  ["a", { id: "a", sha256: "1".repeat(64) }],
  ["b", { id: "b", sha256: "2".repeat(64) }],
]);
const entry = (id, sha256) => ({ from: "catalog", id, version: "1.0.0", sha256 });

test("same ids and hashes match", () => {
  assert.equal(samePack([entry("a", "1".repeat(64)), entry("b", "2".repeat(64))], known), true);
});

test("one differing hash does not match", () => {
  assert.equal(samePack([entry("a", "1".repeat(64)), entry("b", "3".repeat(64))], known), false);
});

test("a policy missing here does not match", () => {
  assert.equal(samePack([entry("a", "1".repeat(64)), entry("c", "2".repeat(64))], known), false);
});

test("an entry without a hash does not match", () => {
  assert.equal(samePack([{ id: "a" }], known), false);
  assert.equal(samePack([entry("a", null)], known), false);
});

test("an empty or malformed list does not match", () => {
  assert.equal(samePack([], known), false);
  assert.equal(samePack(null, known), false);
  assert.equal(samePack([null], known), false);
});

test("inherited names are not policies", () => {
  assert.equal(samePack([entry("constructor", "1".repeat(64))], known), false);
});
