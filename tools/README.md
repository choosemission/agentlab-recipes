# Tools

Shared helpers used by more than one recipe. A recipe that needs one refers to
it from here rather than keeping its own copy.

## `lab-login.sh` — sign in to the Lab from a terminal

Several recipes put your own Agent Gateway in front of a resource and have the
gateway check who is calling. That check wants a signed token proving you are a
Lab member, so you need one in your hand before the recipe will work.

```bash
./tools/lab-login.sh
```

A short code and a web page appear. Open the page — the script tries to do it
for you — sign in the way you normally sign in to the Lab, and approve. Your
terminal picks the token up on its own.

**You do this once**, and after that the script refreshes quietly in the
background. You will see the browser again only when your Lab session itself
lapses — leave it alone over a weekend and expect to sign in once more.

```bash
./tools/lab-login.sh --status              # who am I, and for how long
./tools/lab-login.sh --claims              # what the token actually says
./tools/lab-login.sh --header              # an Authorization: line to paste
./tools/lab-login.sh --token               # just the token
./tools/lab-login.sh --consent URL         # approve what a surface reaches upstream
./tools/lab-login.sh --mcp NAME URL        # point Claude Code at a surface
./tools/lab-login.sh --logout              # forget it
```

`--mcp` is the only one tied to a particular client: it shells out to
`claude mcp add`, registering the surface at user scope so it works from any
directory. Everything else is client-agnostic.

### Connecting a client that is not Claude Code

There is no magic in `--mcp`. Any MCP client needs the same three things:

| | |
| --- | --- |
| Transport | HTTP — streamable HTTP, not SSE and not stdio |
| URL | your surface's **access point**, from the canvas header |
| Header | `Authorization: Bearer <token>` |

Get the header with `./tools/lab-login.sh --header` and paste it wherever your
client keeps headers. Most clients take a variant of this shape:

```json
{
  "mcpServers": {
    "github-gw": {
      "type": "http",
      "url": "https://your-gateway/your/route",
      "headers": { "Authorization": "Bearer eyJhbGciOi..." }
    }
  }
}
```

To try it without configuring anything, the MCP Inspector takes a URL and
headers in its own UI:

```bash
npx @modelcontextprotocol/inspector
```

Whatever you use, the token is a fixed string in that configuration and does
not refresh itself — see below.

Tokens live in `~/.lab/token.json`, readable only by you. `--logout` deletes
them; so does deleting the file.

### There is no password here

`lab-cli`, the name this script gives when it asks for a code, is a **public
client**. It has no secret, which is why it can be written down in a script
that anybody can read. It cannot do anything at all until you personally
approve it in a browser, signed in as yourself. Your password — if you even
have one, rather than signing in with Google — never comes near this script.

### One token, every Lab resource

The token says *you are a signed-in Lab member*, and nothing narrower. Any
resource that trusts the Lab's sign-in will accept it, including surfaces built
by other participants. That is deliberate: it is what lets you protect
something you built without asking anyone to register it first.

It does **not** say what you are allowed to do once you are in. That is the
job of the policy on each surface, which can read your email address and decide
for itself. Being able to prove who you are, and being allowed to do a
particular thing, are two different questions — the recipes that use this come
back to that distinction, because most access-control mistakes live in the gap
between them.

### Why you re-run it

Your sign-in refreshes on its own — that part is automatic and you will not be
asked for the browser again.

What does not refresh is the **copy** your MCP client was given. Most clients
hold a fixed `Authorization` header, set once when the server was added, so
when your token rotates the client carries on sending the old one and starts
failing. Nothing reaches into its configuration to update it.

Re-run `--mcp` with the same arguments and it repoints the client in one step.

### If it will not sign you in

- **`'lab-cli' does not exist, or the device flow is off for it`** — the client
  is missing from the realm, or was created without the device grant enabled.
  That is a Lab-side fix; say so in Slack.
- **Nothing happens after you approve** — the script polls every few seconds
  and can wait up to ten minutes. If it times out, run it again.
- **It signs you in but a surface still refuses you** — the token is fine and
  the surface is the problem. Check that its issuer is exactly
  `https://idp.agentlab.choosemission.com/realms/mission-agent-lab`, including
  the absence of a trailing slash, and that it extracts caller identity rather
  than only verifying the signature.
