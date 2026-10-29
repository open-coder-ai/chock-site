// Whether every policy in a shared selection is byte-identical to the site's own copy.

// entries: the selection's policies; known: Map of policy id -> the site's policy (with its sha256 and, when no file holds a NUL byte,
// sha256_v1, the old hash saved links still carry).
// True only for a non-empty list in which each id exists here and its hash is our v2 or our v1 hash.
export function samePack(entries, known) {
  if (!Array.isArray(entries) || entries.length === 0) return false;
  return entries.every((entry) => {
    if (!entry || typeof entry.id !== "string" || typeof entry.sha256 !== "string") return false;
    const ours = known.get(entry.id);
    if (!ours) return false;
    return ours.sha256 === entry.sha256 || (typeof ours.sha256_v1 === "string" && ours.sha256_v1 === entry.sha256);
  });
}
