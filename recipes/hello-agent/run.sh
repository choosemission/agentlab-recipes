#!/usr/bin/env bash
# Set up a virtualenv and run the A2A client.
#
#   ./run.sh                          # interactive, using A2A_ACCESS_POINT
#   ./run.sh https://your-gateway/...  # interactive, explicit access point
#   ./run.sh --card                   # print the agent card and stop
#   ./run.sh -m "hello"               # send one message and stop
#
# Anything you pass is handed to a2a_client.py unchanged; see --help.

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x venv/bin/python ]; then
  echo "Creating venv/ ..."
  python3 -m venv venv
fi

# Refresh existing clones too: keeping an old venv after git pull must not keep
# the v0.3 SDK. Write the marker only after a successful dependency install.
requirements_hash=$(./venv/bin/python -c 'import hashlib; print(hashlib.sha256(open("requirements.txt", "rb").read()).hexdigest())')
installed_hash=$(cat venv/.requirements.sha256 2>/dev/null || true)
if [ "$requirements_hash" != "$installed_hash" ]; then
  ./venv/bin/python -m pip install --quiet -r requirements.txt
  printf '%s\n' "$requirements_hash" > venv/.requirements.sha256
fi

# Read .env without sourcing it, so an unquoted value containing spaces —
# A2A_AGENT_NAME=A2A Test Client — is read as a value rather than run as a
# command. Values may be quoted or not; the .env wins over the environment,
# and a command-line argument wins over both.
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    case "$line" in *=*) ;; *) continue ;; esac
    key=${line%%=*}
    val=${line#*=}
    case "$key" in *[!A-Za-z0-9_]*) continue ;; esac
    val=${val%$'\r'}
    case "$val" in
      \"*\") val=${val#\"}; val=${val%\"} ;;
      \'*\') val=${val#\'}; val=${val%\'} ;;
    esac
    export "$key=$val"
  done < .env
fi

exec ./venv/bin/python a2a_client.py "$@"
