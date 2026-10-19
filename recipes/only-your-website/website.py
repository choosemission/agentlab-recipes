"""A starter website: Lab sign-in, a chat box, and a backend that calls your access point.

    python3 website.py       # then open http://localhost:5317

Standard library only. The browser never sees the token: it stays in this
process, keyed by a session cookie, and the backend adds it to each call to
your gateway. That is the shape of a real site with a support chat, where the
company owns both the chat box and the agent behind it.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def load_env(path: Path) -> None:
    """Read KEY=value lines into the environment, without overriding it."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, val = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key, val.strip().strip("'\""))


load_env(Path(__file__).with_name(".env"))

ISSUER = os.environ.get(
    "LAB_ISSUER", "https://idp.agentlab.choosemission.com/realms/mission-agent-lab"
)
CLIENT_ID = os.environ.get("SITE_CLIENT_ID", "lab-starter-site")
ACCESS_POINT = os.environ.get("A2A_ACCESS_POINT", "")
AGENT_NAME = os.environ.get("A2A_AGENT_NAME", "Suggestions Website")
PORT = int(os.environ.get("PORT", "5317"))
REDIRECT_URI = f"http://localhost:{PORT}/callback"

IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"
WAITING_STATES = ("input-required", "auth-required")

# ponytail: sessions live in memory, so a restart signs everyone out.
SESSIONS: dict[str, dict] = {}


def get_json(url: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict | str]:
    body = None
    headers = dict(headers or {})
    if data is not None:
        if headers.get("Content-Type") == "application/json":
            body = json.dumps(data).encode()
        else:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, raw = resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read().decode()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


_, OIDC = get_json(f"{ISSUER}/.well-known/openid-configuration")


def claims(token: str) -> dict:
    """Read a JWT's payload for display. Not verified: your gateway does that."""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def message(text: str, session: dict) -> dict:
    msg = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
        "messageId": uuid.uuid4().hex,
        "extensions": [IDENTITY_EXT_URI],
        "metadata": {IDENTITY_EXT_URI: {"agentIdentity": {"name": AGENT_NAME, "version": "1.0.0"}}},
    }
    # Send the task back while the agent is waiting on us, or every turn starts a new task.
    if session.get("context_id"):
        msg["contextId"] = session["context_id"]
    if session.get("task_id"):
        msg["taskId"] = session["task_id"]
    return {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "message/send", "params": {"message": msg}}


def reply_text(result: dict) -> str:
    parts = (result.get("status", {}).get("message") or result).get("parts", [])
    return "\n".join(p.get("text", "") for p in parts) or json.dumps(result)


# The Agent Lab's palette and type, from web/agentlab/src/styles/global.css.
PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Lab Suggestions Box</title>
<style>
:root{{--ink:#14171c;--muted:#575d68;--paper:#f5f7f9;--raised:#fff;--rule:#e0e3e8;
--signal:#2456c8;--soft:#dbe4f7;--danger:#9b2c2c;
--display:'Helvetica Neue',Helvetica,Inter,'Segoe UI',system-ui,sans-serif;
--body:'Avenir Next',Avenir,'Segoe UI',sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e6ebf4;--muted:#9aa5b8;--paper:#0c1220;
--raised:#131a2b;--rule:#202a3e;--signal:#7da2ff;--soft:#1a2b4d;--danger:#fc8181}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--body)}}
header{{border-bottom:1px solid var(--rule);background:var(--raised)}}
header div,main{{max-width:40rem;margin:0 auto;padding:1rem}}
header div{{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap}}
.mark{{font:600 1.05rem var(--display);letter-spacing:-.01em}} .mark span{{color:var(--muted);font-weight:400}}
.who{{color:var(--muted);font-size:.8125rem}} code{{font-family:var(--mono);font-size:.8125rem}}
a{{color:var(--signal)}}
h1{{font:600 1.6rem/1.2 var(--display);letter-spacing:-.02em;margin:1.5rem 0 .5rem}}
p{{color:var(--muted)}}
.msg{{white-space:pre-wrap;margin:.6rem 0;padding:.7rem .9rem;border-radius:8px;width:fit-content;max-width:85%;font:inherit}}
.me{{margin-left:auto;background:var(--signal);color:var(--raised)}}
.agent{{background:var(--raised);border:1px solid var(--rule)}}
.err{{background:var(--raised);border:1px solid var(--danger);color:var(--danger);font-family:var(--mono);font-size:.8125rem}}
form{{display:flex;gap:.5rem;margin-top:1rem}}
input{{flex:1;min-width:0;padding:.65rem .8rem;border:1px solid var(--rule);border-radius:6px;background:var(--raised);color:var(--ink);font:inherit}}
input:focus{{outline:2px solid var(--soft);border-color:var(--signal)}}
button,.button{{display:inline-block;padding:.65rem 1.1rem;border:0;border-radius:6px;background:var(--ink);color:var(--paper);font:600 .95rem var(--display);text-decoration:none;cursor:pointer}}
</style>
<header><div><span class="mark">Agent Lab <span>Suggestions Box</span></span><span class="who">{who}</span></div></header>
<main>{body}</main>"""


def page(body: str, who: str = "") -> str:
    return PAGE.format(body=body, who=who)


class Handler(BaseHTTPRequestHandler):
    def session(self) -> tuple[str, dict]:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie["sid"].value if "sid" in cookie else ""
        if sid not in SESSIONS:
            sid = secrets.token_urlsafe(24)
            SESSIONS[sid] = {"log": []}
        return sid, SESSIONS[sid]

    def send(self, status: int, body: str = "", location: str = "", sid: str = "") -> None:
        self.send_response(status)
        if sid:
            self.send_header("Set-Cookie", f"sid={sid}; HttpOnly; SameSite=Lax; Path=/")
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self) -> None:
        sid, s = self.session()
        url = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))

        if url.path == "/login":
            s["verifier"] = secrets.token_urlsafe(48)
            s["state"] = secrets.token_urlsafe(16)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(s["verifier"].encode()).digest()).rstrip(b"=")
            params = {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": "openid email",
                "state": s["state"],
                "code_challenge": challenge.decode(),
                "code_challenge_method": "S256",
            }
            return self.send(302, location=f"{OIDC['authorization_endpoint']}?{urllib.parse.urlencode(params)}", sid=sid)

        if url.path == "/callback":
            if not query.get("state") or query.get("state") != s.pop("state", None):
                return self.send(400, page("<p class='msg err'>Sign-in state did not match. <a href=/login>Try again</a>.</p>"))
            status, tokens = get_json(OIDC["token_endpoint"], {
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": query.get("code", ""),
                "redirect_uri": REDIRECT_URI,
                "code_verifier": s.pop("verifier", ""),
            })
            if status != 200:
                return self.send(400, page(f"<p class='msg err'>Sign-in failed: {html.escape(str(tokens))}</p>"))
            s["token"] = tokens["access_token"]
            return self.send(302, location="/", sid=sid)

        if url.path == "/logout":
            SESSIONS.pop(sid, None)
            return self.send(302, location="/")

        if url.path != "/":
            return self.send(404, "not found")

        if "token" not in s:
            return self.send(200, page("""<h1>Tell the Lab what to improve</h1>
<p>Something broken, unclear or missing? The suggestions agent asks a few questions and passes your answers to the Lab team.</p>
<a class=button href=/login>Sign in with your Lab account</a>"""), sid=sid)

        c = claims(s["token"])
        who = (f"{html.escape(c.get('email', '?'))} · azp <code>{html.escape(c.get('azp', '?'))}</code>"
               " · <a href=/logout>Sign out</a>")
        log = "".join(f"<div class='msg {cls}'>{html.escape(text)}</div>" for cls, text in s["log"])
        body = f"""<h1>Tell the Lab what to improve</h1>
{log or "<p>Say you have a suggestion, and the agent will take it from there.</p>"}
<form method=post action=/send><input name=text autofocus autocomplete=off placeholder="I have a suggestion">
<button>Send</button></form>"""
        self.send(200, page(body, who), sid=sid)

    def do_POST(self) -> None:
        sid, s = self.session()
        if self.path != "/send" or "token" not in s:
            return self.send(302, location="/", sid=sid)
        if claims(s["token"]).get("exp", 0) < time.time():
            # ponytail: no refresh token; the IdP session makes signing in again a redirect.
            return self.send(302, location="/login", sid=sid)

        length = int(self.headers.get("Content-Length", 0))
        text = urllib.parse.parse_qs(self.rfile.read(length).decode()).get("text", [""])[0].strip()
        if not text:
            return self.send(302, location="/", sid=sid)

        s["log"].append(("me", text))
        status, resp = get_json(
            ACCESS_POINT,
            message(text, s),
            {"Content-Type": "application/json", "Authorization": f"Bearer {s['token']}"},
        )
        result = resp.get("result") if isinstance(resp, dict) else None
        if status != 200 or not result:
            s["log"].append(("err", f"{status}: {resp if isinstance(resp, str) else json.dumps(resp)}"))
        else:
            state = result.get("status", {}).get("state")
            s["context_id"] = result.get("contextId")
            s["task_id"] = result.get("id") if state in WAITING_STATES else None
            s["log"].append(("agent", reply_text(result)))
        self.send(302, location="/", sid=sid)


if __name__ == "__main__":
    if not ACCESS_POINT:
        raise SystemExit("Set A2A_ACCESS_POINT in .env to your surface's access point.")
    print(f"Open http://localhost:{PORT}")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()
