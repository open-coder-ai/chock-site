// Cloudflare Pages Function for /api/event (plan AN-1): count one allowlisted site event.
// It re-checks the body against the same allowlist as the browser and writes one Analytics Engine
// data point (binding EVENTS). It stores no IP, user agent or other header.
import { EVENTS, KEYS, MAX_BODY, VALUE } from "./_allowlist.js";

const reply = (status, headers = {}) =>
  new Response(null, { status, headers: { "Cache-Control": "no-store", ...headers } });

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

// The body as text, or null when it is longer than MAX_BODY bytes or not UTF-8.
async function readCapped(request) {
  if (Number(request.headers.get("Content-Length")) > MAX_BODY) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const bytes = new Uint8Array(MAX_BODY);
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (size + value.byteLength > MAX_BODY) {
      await reader.cancel();
      return null;
    }
    bytes.set(value, size);
    size += value.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(0, size));
  } catch {
    return null;
  }
}

// The Analytics Engine data point for a valid body, or null. A valid body is exactly
// {"name": <allowlisted event>, "props": {<each of that event's keys>: <value matching VALUE>}}.
export function dataPoint(text) {
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isObject(body) || Object.keys(body).some((key) => key !== "name" && key !== "props")) {
    return null;
  }
  const { name, props } = body;
  if (typeof name !== "string" || !Object.hasOwn(EVENTS, name) || !isObject(props)) return null;
  const allowed = EVENTS[name];
  const keys = Object.keys(props);
  if (keys.length !== allowed.length || !allowed.every((key) => Object.hasOwn(props, key))) {
    return null;
  }
  if (!keys.every((key) => typeof props[key] === "string" && VALUE.test(props[key]))) return null;
  return {
    blobs: [name, ...KEYS.map((key) => (Object.hasOwn(props, key) ? props[key] : ""))],
    doubles: [1],
    indexes: [name],
  };
}

export async function onRequest({ request, env }) {
  if (request.method !== "POST") return reply(405, { Allow: "POST" });
  const text = await readCapped(request);
  if (text === null) return reply(413);
  const point = dataPoint(text);
  if (!point) return reply(400);
  if (env && env.EVENTS) {
    try {
      env.EVENTS.writeDataPoint(point);
    } catch {
      // A failed count is not the visitor's problem.
    }
  }
  return reply(204);
}
