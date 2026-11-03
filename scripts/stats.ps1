# Print the last 7 days' counts per site event from the Cloudflare Analytics Engine.
#   $env:CF_ACCOUNT_ID = '<account id>'; $env:CF_API_TOKEN = '<token with Account Analytics: Read>'
#   pwsh scripts/stats.ps1 [-Dataset chock_site_events]
# The token is read from the environment only: it is never written to a file or printed.
[CmdletBinding()]
param([string]$Dataset = 'chock_site_events')
$ErrorActionPreference = 'Stop'

if ($Dataset -notmatch '^[a-z0-9_]+$') { throw 'Dataset must be lowercase letters, digits and underscores.' }
if (-not $env:CF_ACCOUNT_ID) { throw 'Set CF_ACCOUNT_ID to your Cloudflare account id.' }
if (-not $env:CF_API_TOKEN) { throw 'Set CF_API_TOKEN to an API token with Account Analytics: Read.' }
if ($env:CF_ACCOUNT_ID -notmatch '^[A-Za-z0-9]+$') { throw 'CF_ACCOUNT_ID must be letters and digits only.' }

$query = "SELECT blob1 AS event, SUM(_sample_interval) AS count FROM $Dataset WHERE timestamp > NOW() - INTERVAL '7' DAY GROUP BY event ORDER BY count DESC FORMAT TabSeparatedWithNames"
$url = "https://api.cloudflare.com/client/v4/accounts/$($env:CF_ACCOUNT_ID)/analytics_engine/sql"
Invoke-RestMethod -Method Post -Uri $url -Headers @{ Authorization = "Bearer $($env:CF_API_TOKEN)" } -Body $query
