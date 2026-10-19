#!/usr/bin/env bash
# Send one A2A message to your access point carrying a Lab sign-in token from
# the command line, not from the website.
#
#   ./send-with-lab-token.sh             # uses A2A_ACCESS_POINT from .env
#
# The token comes from tools/lab-login.sh, which signs in as the Lab's
# command-line client. It is a real Lab token for you, just not one issued to
# the website.
set -euo pipefail
cd "$(dirname "$0")"

AP="${A2A_ACCESS_POINT:-$(grep -E '^A2A_ACCESS_POINT=' .env | cut -d= -f2- | tr -d "\"'")}"
[ -n "$AP" ] || { echo "Set A2A_ACCESS_POINT in .env" >&2; exit 1; }

TOKEN=$(../../tools/lab-login.sh --token)
BODY='{"jsonrpc":"2.0","id":"1","method":"message/send",
"params":{"message":{"role":"user","messageId":"'"$(uuidgen)"'",
"parts":[{"kind":"text","text":"I have a suggestion"}]}}}'

curl -sS -w '\nHTTP %{http_code}\n' "$AP" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "$BODY"
