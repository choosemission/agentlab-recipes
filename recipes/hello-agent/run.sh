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

if [ ! -d venv ]; then
  echo "Creating venv/ ..."
  python3 -m venv venv
  ./venv/bin/pip install --quiet --upgrade pip
  ./venv/bin/pip install --quiet -r requirements.txt
  echo "Done."
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
