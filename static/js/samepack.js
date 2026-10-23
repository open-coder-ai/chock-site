// Whether every policy in a shared selection is byte-identical to the site's own copy.

// entries: the selection's policies; known: Map of policy id -> the site's policy (with its sha256).
// True only for a non-empty list in which each id exists here with the same sha256.
export function samePack(entries, known) {
  if (!Array.isArray(entries) || entries.length === 0) return false;
  return entries.every((entry) => {
    if (!entry || typeof entry.id !== "string" || typeof entry.sha256 !== "string") return false;
    const ours = known.get(entry.id);
    return Boolean(ours) && typeof ours.sha256 === "string" && ours.sha256 === entry.sha256;
  });
}
