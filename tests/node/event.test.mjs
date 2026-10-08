// The Pages Function for /api/event (plan AN-1): what it accepts, what it refuses, what it writes.
// Run by tests/test_event_function.py with `node --test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import { EVENTS, KEYS, MAX_BODY } from "../../functions/api/_allowlist.js";
import { dataPoint, onRequest } from "../../functions/api/event.js";

const URL_ = "https://chock.sh/api/event";

function fakeEnv() {
  const points = [];
  return { points, env: { EVENTS: { writeDataPoint: (point) => points.push(point) } } };
}

async function post(body, { env, headers = {}, method = "POST" } = {}) {
  const request = new Request(URL_, {
    method,
    body: method === "GET" || method === "HEAD" ? undefined : body,
    headers: { "Content-Type": "application/json", "CF-Connecting-IP": "203.0.113.9", ...headers },
  });
  return onRequest({ request, env });
}

const json = (value) => JSON.stringify(value);

test("a valid event writes one data point and returns 204 with no body", async () => {
  const { points, env } = fakeEnv();
  const response = await post(json({ name: "install-copied", props: { agent: "claude-code" } }), {
    env,
  });
  assert.equal(response.status, 204);
  assert.equal(await response.text(), "");
  assert.deepEqual(points, [
    { blobs: ["install-copied", "claude-code", "", "", "", ""], doubles: [1], indexes: ["install-copied"] },
  ]);
});

test("every allowlisted event is accepted with its keys", async () => {
  const { points, env } = fakeEnv();
  for (const [name, keys] of Object.entries(EVENTS)) {
    const props = Object.fromEntries(keys.map((key) => [key, "x-1.2"]));
    const response = await post(json({ name, props }), { env });
    assert.equal(response.status, 204, name);
  }
  assert.equal(points.length, Object.keys(EVENTS).length);
  for (const point of points) assert.equal(point.blobs.length, KEYS.length + 1);
});

test("the data point holds no IP, user agent or header", async () => {
  const { points, env } = fakeEnv();
  await post(json({ name: "share-copied", props: {} }), {
    env,
    headers: { "User-Agent": "secret-agent", Referer: "https://chock.sh/coding/builder/#s=abc" },
  });
  const written = JSON.stringify(points);
  for (const leak of ["203.0.113.9", "secret-agent", "#s=abc", "builder"]) {
    assert.ok(!written.includes(leak), leak);
  }
});

test("bad bodies are refused with 400 and write nothing", async () => {
  const { points, env } = fakeEnv();
  const bad = [
    "not json",
    json(null),
    json([]),
    json("install-copied"),
    json({ name: "unknown-event", props: {} }),
    json({ name: "share-copied" }),
    json({ name: "share-copied", props: [] }),
    json({ name: "share-copied", props: {}, url: "https://chock.sh/?q=1" }),
    json({ name: "share-copied", props: { agent: "claude-code" } }),
    json({ name: "install-copied", props: {} }),
    json({ name: "install-copied", props: { agent: "claude-code", text: "hi" } }),
    json({ name: "install-copied", props: { agent: "Claude Code" } }),
    json({ name: "install-copied", props: { agent: "<script>" } }),
    json({ name: "install-copied", props: { agent: "a".repeat(65) } }),
    json({ name: "install-copied", props: { agent: "" } }),
    json({ name: "install-copied", props: { agent: 7 } }),
    json({ name: "install-copied", props: { agent: "a\nb" } }),
    json({ name: "__proto__", props: {} }),
    json({ name: "toString", props: {} }),
    '{"name":"install-copied","props":{"agent":"x","__proto__":{"y":"z"}}}',
  ];
  for (const body of bad) {
    const response = await post(body, { env });
    assert.equal(response.status, 400, body);
    assert.equal(await response.text(), "");
  }
  assert.equal(points.length, 0);
});

test("an oversize body is refused with 413 and writes nothing", async () => {
  const { points, env } = fakeEnv();
  const padding = " ".repeat(MAX_BODY);
  const body = json({ name: "share-copied", props: {} }) + padding;
  assert.equal((await post(body, { env })).status, 413);
  // Without a Content-Length the stream is still cut at MAX_BODY bytes.
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  const request = new Request(URL_, { method: "POST", body: stream, duplex: "half" });
  assert.equal(request.headers.get("Content-Length"), null);
  assert.equal((await onRequest({ request, env })).status, 413);
  assert.equal(points.length, 0);
});

test("a body of exactly MAX_BODY bytes is read", async () => {
  const { points, env } = fakeEnv();
  const base = json({ name: "share-copied", props: {} });
  const response = await post(base + " ".repeat(MAX_BODY - base.length), { env });
  assert.equal(response.status, 204);
  assert.equal(points.length, 1);
});

test("other methods get 405 and write nothing", async () => {
  const { points, env } = fakeEnv();
  for (const method of ["GET", "PUT", "DELETE"]) {
    const response = await post(json({ name: "share-copied", props: {} }), { env, method });
    assert.equal(response.status, 405, method);
    assert.equal(response.headers.get("Allow"), "POST");
  }
  assert.equal(points.length, 0);
});

test("without the EVENTS binding a valid event still returns 204", async () => {
  for (const env of [undefined, {}]) {
    const response = await post(json({ name: "share-copied", props: {} }), { env });
    assert.equal(response.status, 204);
  }
});

test("a failing binding does not fail the request", async () => {
  const env = {
    EVENTS: {
      writeDataPoint() {
        throw new Error("down");
      },
    },
  };
  assert.equal((await post(json({ name: "share-copied", props: {} }), { env })).status, 204);
});

test("dataPoint orders blobs by KEYS", () => {
  const point = dataPoint(
    json({ name: "policy-build-clicked", props: { agent: "codex", policy: "block-no-verify" } }),
  );
  assert.deepEqual(point.blobs, ["policy-build-clicked", "codex", "", "", "block-no-verify", ""]);
});
