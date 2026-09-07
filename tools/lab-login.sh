#!/usr/bin/env bash
# Sign in to the Agent Lab from a terminal and hold on to the token.
#
#   ./lab-login.sh                     # sign in, or quietly refresh
#   ./lab-login.sh --status            # who am I, and for how long
#   ./lab-login.sh --claims            # show what the token actually says
#   ./lab-login.sh --header            # print an Authorization header line
#   ./lab-login.sh --token             # print the raw access token
#   ./lab-login.sh --mcp NAME URL      # point Claude Code at a surface
#   ./lab-login.sh --consent URL       # approve a surface's upstream credential
#   ./lab-login.sh --logout            # forget the stored tokens
#
# You sign in **once**, in a browser, the same way you signed in to the
# website. After that this script refreshes in the background and you should
# not see the browser again for days.
#
# There is no password and no secret here. `lab-cli` is a public client: its
# name is published, and it is safe to publish, because it cannot do anything
# until you personally approve it in a browser.

set -euo pipefail

ISSUER="${LAB_ISSUER:-https://idp.agentlab.choosemission.com/realms/mission-agent-lab}"
CLIENT="${LAB_CLIENT:-lab-cli}"
SCOPES="openid email offline_access"

STORE_DIR="${LAB_HOME:-$HOME/.lab}"
STORE="$STORE_DIR/token.json"

# Ask for a new access token this many seconds before the old one dies, so a
# long-running command does not expire halfway through.
SKEW=60

for dep in curl jq; do
    command -v "$dep" >/dev/null || { echo "missing dependency: $dep" >&2; exit 1; }
done

now() { date +%s; }

save() {
    # $1 is the token endpoint's JSON response.
    mkdir -p "$STORE_DIR"; chmod 700 "$STORE_DIR"
    local expires_at
    expires_at=$(( $(now) + $(jq -r '.expires_in // 300' <<<"$1") ))
    umask 077
    jq --argjson at "$expires_at" \
       '{access_token, refresh_token, expires_at: $at}' <<<"$1" > "$STORE"
}

stored() { [ -f "$STORE" ] && jq -er ".$1 // empty" < "$STORE" 2>/dev/null; }

# base64url is base64 with two characters swapped and the padding removed.
claims() {
    local seg="${1}" pad
    pad=$(( ${#seg} % 4 ))
    [ "$pad" -ne 0 ] && seg="${seg}$(printf '=%.0s' $(seq $((4 - pad))))"
    printf '%s' "$seg" | tr '_-' '/+' | base64 -d 2>/dev/null
}

open_browser() {
    if command -v open >/dev/null; then open "$1" 2>/dev/null && return 0
    elif command -v xdg-open >/dev/null; then xdg-open "$1" 2>/dev/null && return 0
    fi
    return 1
}

# Trade the refresh token for a new access token. Silent, no browser. Fails
# quietly when the refresh token has itself expired, and the caller falls
# through to a full sign-in.
try_refresh() {
    local rt response
    rt=$(stored refresh_token) || return 1
    [ -n "$rt" ] || return 1
    response=$(curl -sS -X POST "$ISSUER/protocol/openid-connect/token" \
        -d grant_type=refresh_token \
        -d client_id="$CLIENT" \
        -d refresh_token="$rt" 2>/dev/null) || return 1
    jq -e '.access_token' >/dev/null 2>&1 <<<"$response" || return 1
    save "$response"
}

device_login() {
    local start response device_code interval expires_in verification user_code

    start=$(curl -sS -X POST "$ISSUER/protocol/openid-connect/auth/device" \
        -d client_id="$CLIENT" -d scope="$SCOPES")

    if ! jq -e '.device_code' >/dev/null 2>&1 <<<"$start"; then
        echo "Could not start sign-in. The Lab IdP said:" >&2
        jq . <<<"$start" >&2
        # These two look alike and mean different things. Keycloak says
        # invalid_client when it cannot find the client at all, and
        # unauthorized_client when it found it but the grant is not enabled —
        # both under the same generic description.
        case "$(jq -r '.error // empty' <<<"$start")" in
            invalid_client)
                echo "-> '$CLIENT' does not exist in this realm" >&2 ;;
            unauthorized_client)
                echo "-> '$CLIENT' exists, but is not allowed this grant. Either" >&2
                echo "   'OAuth 2.0 Device Authorization Grant' is unticked, or" >&2
                echo "   client authentication is on and it wants a secret." >&2 ;;
        esac
        exit 1
    fi

    device_code=$(jq -r .device_code <<<"$start")
    user_code=$(jq -r .user_code <<<"$start")
    interval=$(jq -r '.interval // 5' <<<"$start")
    expires_in=$(jq -r '.expires_in // 600' <<<"$start")
    verification=$(jq -r '.verification_uri_complete // .verification_uri' <<<"$start")

    echo
    if open_browser "$verification"; then
        echo "  Opened your browser. Sign in and approve."
        echo
        echo "  If nothing opened, go to $(jq -r .verification_uri <<<"$start")"
        echo "  and enter the code $user_code"
    else
        # No browser here — a remote shell, or a machine without one. The code
        # is the point of this flow: approve on any other device you like.
        echo "  Go to:            $(jq -r .verification_uri <<<"$start")"
        echo "  Enter this code:  $user_code"
        echo
        echo "  Any device will do — this machine does not need a browser."
    fi
    echo
    echo "  Waiting..."

    local deadline=$(( $(now) + expires_in ))
    while [ "$(now)" -lt "$deadline" ]; do
        sleep "$interval"
        response=$(curl -sS -X POST "$ISSUER/protocol/openid-connect/token" \
            -d grant_type=urn:ietf:params:oauth:grant-type:device_code \
            -d device_code="$device_code" \
            -d client_id="$CLIENT")

        case "$(jq -r '.error // "ok"' <<<"$response")" in
            ok)
                save "$response"
                echo "  Signed in as $(whoami_from_token). Token saved to $STORE."
                echo
                return 0 ;;
            authorization_pending) ;;
            slow_down) interval=$(( interval + 5 )) ;;
            access_denied) echo "  You declined the sign-in." >&2; exit 1 ;;
            expired_token) echo "  The code expired. Run this again." >&2; exit 1 ;;
            *) echo "  Sign-in failed:" >&2; jq . <<<"$response" >&2; exit 1 ;;
        esac
    done

    echo "  Timed out waiting for sign-in. Run this again." >&2
    exit 1
}

whoami_from_token() {
    local tok payload
    tok=$(stored access_token) || { echo "(unknown)"; return; }
    payload=$(claims "$(cut -d. -f2 <<<"$tok")")
    jq -r '.email // .preferred_username // .sub // "(unknown)"' <<<"$payload"
}

# The one entry point everything else goes through: hand back a token that is
# good right now, doing the least work needed to get one.
ensure_token() {
    local expires_at
    expires_at=$(stored expires_at || echo 0)
    if [ -n "$expires_at" ] && [ "$expires_at" -gt $(( $(now) + SKEW )) ] 2>/dev/null; then
        return 0
    fi
    try_refresh && return 0
    device_login
}

# Ask a surface to do something, and if it says it needs your permission to
# reach whatever is upstream, send you there to give it.
#
# The gateway returns that permission request as the body of a 401, which most
# MCP clients discard — Claude Code reports "detail withheld" and you never see
# the link. So this makes the call itself and reads the reply.
consent() {
    local url="$1" tok body
    tok=$(stored access_token)
    body=$(curl -sS -m 45 -X POST "$url" \
        -H "Authorization: Bearer $tok" \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json, text/event-stream' \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"lab-login","version":"1"}}}' \
        | sed -n 's/^data: //p;/^[[:space:]]*[{[]/p' | head -1)

    if ! jq -e '.consent_required' >/dev/null 2>&1 <<<"$body"; then
        if jq -e '.result' >/dev/null 2>&1 <<<"$body"; then
            echo "Nothing to approve — the surface already has what it needs."
            return 0
        fi
        echo "The surface did not ask for consent. It said:" >&2
        jq . <<<"$body" 2>/dev/null | head -20 >&2 || head -c 400 <<<"$body" >&2
        return 1
    fi

    local n
    n=$(jq -r '.consent_required | length' <<<"$body")
    echo "This surface needs your permission to reach $n upstream service(s)."
    echo

    local i provider auth
    for i in $(seq 0 $(( n - 1 ))); do
        provider=$(jq -r ".consent_required[$i].provider_name" <<<"$body")
        auth=$(jq -r ".consent_required[$i].authorization_url" <<<"$body")
        echo "  $provider"
        if open_browser "$auth"; then
            echo "  -> opened in your browser. Approve it there."
        else
            echo "  -> open this to approve:"
            echo "     $auth"
        fi
        echo
    done

    echo "Once approved, run your original request again."
}

update_mcp() {
    local name="$1" url="$2" tok

    # Mint a fresh one rather than handing over whatever is left of the
    # current token. The client keeps a *copy* and cannot refresh it, so a
    # token with four minutes left becomes four minutes of working MCP.
    try_refresh || true

    # This shells out to Claude Code. Every other client is configured by hand,
    # and there are only three things to know, so say them rather than fail.
    command -v claude >/dev/null || {
        echo "This shortcut drives Claude Code, and 'claude' is not on your PATH." >&2
        echo >&2
        echo "Any MCP client needs the same three things:" >&2
        echo "  transport  HTTP (streamable)" >&2
        echo "  url        $url" >&2
        echo "  header     Authorization: Bearer <token>" >&2
        echo >&2
        echo "Print the header with:  $0 --header" >&2
        exit 1
    }
    tok=$(stored access_token)

    # User scope, not the default local scope. A surface you reach with your
    # Lab identity is not a property of whichever directory you happened to be
    # standing in, and registering it per-directory means re-running this in
    # each one — with the failure showing up as a stale token that never
    # updates, because the copy being refreshed is in a config your client is
    # not reading. Remove from any scope, add back to this one.
    claude mcp remove "$name" >/dev/null 2>&1 || true
    claude mcp add --transport http --scope user "$name" "$url" -H "Authorization: Bearer $tok"
    echo "Pointed '$name' at $url, for every project."
    echo "Re-run this when it stops working."
}

case "${1:-}" in
--logout)
    rm -f "$STORE"
    echo "Signed out. Run this again to sign back in."
    ;;
--status)
    if [ ! -f "$STORE" ]; then
        echo "Not signed in. Run $0 to sign in."
        exit 1
    fi
    left=$(( $(stored expires_at) - $(now) ))
    echo "Signed in as $(whoami_from_token)."
    if [ "$left" -gt 0 ]; then
        echo "Access token good for another ${left}s."
    else
        echo "Access token expired — the next command will refresh it silently."
    fi
    ;;
--claims)
    ensure_token
    tok=$(stored access_token)
    payload=$(claims "$(cut -d. -f2 <<<"$tok")")
    echo "Your token is a JWT: three base64 parts, signed by the Lab IdP."
    echo "Anyone can read it. Only the Lab can have produced it."
    echo
    jq '{iss, sub, email, email_verified, aud, exp, azp}' <<<"$payload"
    echo
    echo "  iss    who issued it — a surface checks this string exactly"
    echo "  sub    you, permanently, whatever your email later becomes"
    echo "  email  you, legibly — what a surface files your credentials under"
    echo "  exp    when it stops working ($(( $(jq -r .exp <<<"$payload") - $(now) ))s from now)"
    ;;
--header)
    ensure_token
    echo "Authorization: Bearer $(stored access_token)"
    ;;
--token)
    ensure_token
    stored access_token
    ;;
--mcp)
    [ $# -eq 3 ] || { echo "usage: $0 --mcp NAME URL" >&2; exit 2; }
    ensure_token
    update_mcp "$2" "$3"
    ;;
--consent)
    [ $# -eq 2 ] || { echo "usage: $0 --consent URL" >&2; exit 2; }
    ensure_token
    consent "$2"
    ;;
"")
    ensure_token
    echo "Signed in as $(whoami_from_token)."
    ;;
*)
    echo "unknown option: $1" >&2
    sed -n '2,12p' "$0" >&2
    exit 2
    ;;
esac
