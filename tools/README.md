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
./tools/lab-login.sh --header              # an Authorization: line to paste
./tools/lab-login.sh --token               # just the token
./tools/lab-login.sh --mcp lab-github URL  # point an MCP client at a surface
./tools/lab-login.sh --logout              # forget it
```

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

### Why the token has to be pasted at all

Most MCP clients hold a fixed `Authorization` header, so when the access token
is rotated the client keeps sending the old one and starts failing. Re-run
`--mcp` with the same arguments and it repoints the client in one step.

This is friction we would rather not have. It exists because an Agent Gateway
surface cannot yet tell an MCP client where to sign in — so the client cannot
run the sign-in itself, and something has to hand it a token. When that gap
closes, clients will sign in and refresh on their own, and this script stops
being part of any recipe.

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
