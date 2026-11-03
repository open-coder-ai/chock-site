#!/usr/bin/env bash
# Print the last 7 days' counts per site event from the Cloudflare Analytics Engine.
#   CF_ACCOUNT_ID=<account id> CF_API_TOKEN=<token with Account Analytics: Read> bash scripts/stats.sh [dataset]
# The dataset defaults to chock_site_events. The token is read from the environment only:
# it is never written to a file, printed, or put on a command line.
set -euo pipefail

dataset="${1:-chock_site_events}"
case "$dataset" in
    '' | *[!a-z0-9_]*) echo "error: dataset must be lowercase letters, digits and underscores" >&2; exit 1 ;;
esac
: "${CF_ACCOUNT_ID:?set CF_ACCOUNT_ID to your Cloudflare account id}"
: "${CF_API_TOKEN:?set CF_API_TOKEN to an API token with Account Analytics: Read}"
case "$CF_ACCOUNT_ID" in
    *[!A-Za-z0-9]*) echo "error: CF_ACCOUNT_ID must be letters and digits only" >&2; exit 1 ;;
esac

query="SELECT blob1 AS event, SUM(_sample_interval) AS count FROM ${dataset} WHERE timestamp > NOW() - INTERVAL '7' DAY GROUP BY event ORDER BY count DESC FORMAT TabSeparatedWithNames"
url="https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/analytics_engine/sql"

# The header goes to curl on stdin (printf is a shell builtin), so the token is not in any process list.
printf 'header = "Authorization: Bearer %s"\n' "$CF_API_TOKEN" \
    | curl --silent --show-error --fail-with-body --config - --data "$query" "$url"
