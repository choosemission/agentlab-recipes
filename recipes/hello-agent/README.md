# Hello, agent

The recipe after `hello-gateway`. You put your own Agent Gateway in front of an
A2A agent the Lab hosts, then configure two Identity elements — and an exchange
between two parties that have never met produces a **signed record of which
agent acted for which caller**, that neither side wrote a line of code to
create.

About 75 minutes. Phase A is roughly 15 of them.

> **You are calling the Lab's hosted agent.** Its source is in this directory
> under [`agent/`](agent/) so you can read it, but running it is not a step in
> this recipe. Pointing your surface at your own localhost means a tunnel, and
> a restarted tunnel invalidates the target URL and the agent card at once.
> Read the agent; call ours.

---

## Before you start

- **Python 3.10 or newer.** `python3 --version`.
- **A gateway of your own**, from the `get-a-gateway` setup step.
- **`hello-gateway` completed.** Steps 2 and 3 below assume you have created a
  surface before and do not re-teach it.
- **The Lab's resource URL and API key** for the `hello-a2a` target. Both are
  handed to you on this recipe's page on the Lab website when you are signed
  in, or in the recipe text if you reached it through a Lab MCP client.

The key goes into your **gateway**, as target authentication. It never goes
into this client, and this client has no way to accept one.

```bash
cp .env.example .env    # then fill in A2A_ACCESS_POINT after step 2
```

Before configuring anything in front of the agent, check the agent itself is up.
Separating "is the backend reachable" from "is the trust layer working" turns a
five-layer debug into two one-layer ones. Put the resource URL from the recipe
page in a variable first, so there is no placeholder left to paste:

```bash
# The Agent URL from the recipe page. If yours differs, use yours.
RESOURCE_URL=https://agentlab.choosemission.com/hello-a2a

# The card: open to anyone. Expect JSON.
curl -s "$RESOURCE_URL/.well-known/agent-card.json"

# The message path: closed. Expect 401, because you are not a gateway.
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$RESOURCE_URL"
```

That 401 is the door your gateway holds the key to. You do not need to call the
Lab's URL directly again.

---

# Phase A — meet the protocol

You met MCP in `hello-gateway`: typed tools, and your model picking one and
filling in its arguments. A2A is a different shape, and fifteen minutes with the
artefacts is worth more than a page of theory.

## 1. Install the client

```bash
./run.sh --help
```

First run creates `venv/` and installs the two dependencies. There is no model
key, and there is no model — the client is a REPL that prints what came back.
That is deliberate: everything interesting in the output was put there by the
gateway, and a caller clever enough to interpret it would make that impossible
to see.

## 2. Create an A2A surface

Familiar ground, quickly:

1. **Secrets management** → new `APIKey` secret → paste the Lab's key. Gateway
   tier first; a surface can only reference what already exists above it.
2. New surface, from the **A2A** template.
3. Managed agent → endpoint type **Direct URL** → the Lab's resource URL,
   **including its path**.
4. Managed agent → **Target Authentication** → `API Key` → the secret from
   step 1 → header name `x-api-key`.
5. Copy the **access point** URL into `A2A_ACCESS_POINT` in your `.env`.

If any of that is unfamiliar, `hello-gateway` steps 1–5 are the long version.

## 3. Read the agent card

```bash
./run.sh --card
```

Two things to notice, and both are free.

**The skills are prose.** Not JSON Schema, not typed parameters — a sentence
saying what the agent does. Put that beside the `tools/list` output from
`hello-gateway`. MCP advertises typed functions and *your* model picks one and
fills in its arguments; A2A advertises a capability and the **callee** works out
how. You do not call `mint_code(user)`. You ask, in prose, and it decides.

**`url` points at your gateway, not at the Lab.** You fetched the card through
your access point and the gateway rewrote it on the way out. Discovery itself
now routes through the governed door, and the Lab's address for this agent never
reached you. The client prints a warning if it does not match — that is a
finding, not noise.

## 4. Send a message, and read the envelope

```bash
./run.sh
```

Say anything. What comes back is not a return value:

```
  kind        task
  state       completed
  taskId      …
  contextId   …
  history     1 message(s)
```

A **task**, with state and a history. Send a second message in the same session
and watch `contextId` stay put while `taskId` changes — a conversation with
state, where MCP had a function call. (The client carries the `contextId`
forward for you; upstream's does not, which is why upstream's second message
looks like a first one.)

Look at the identity in that envelope, too. Each side sent an unsigned
description of itself, and nothing checked either. **That is what an ungoverned
exchange looks like**, and it is the baseline the rest of this recipe moves off.

## 5. Read the agent

[`agent/`](agent/) — two minutes, and it is the whole of an A2A server. No
model, no reasoning, nothing capable of signing anything: `read_caller_identity`
and `describe` are dictionary reading, end to end.

Read it for two things. One is what is on the other side of an A2A call, which
you have been making since step 3 without seeing. The other is what is *not*
there: nothing in an agent this size could mint a credential, so everything that
arrives signed in Phase B has to have come from the gateway.

### Optional experiment: run the example agent locally

**You can skip this and still complete the recipe.** Everything from step 6 on
calls the Lab's hosted agent through your surface, never this local copy.

If you have a spare minute, run it in one terminal and call it from another:

```bash
./venv/bin/python agent/                    # terminal 1: listens on port 8080
./run.sh -m "hello" http://localhost:8080/   # terminal 2
```

Called directly it answers **CASE 3 — NOTHING SIGNED**, every time, because
there is no gateway in the path to sign anything. Same code, no gateway, no
identity. In step 7 you will send a message through your surface and get a
signed presentation, and the difference will be entirely the gateway's doing.

> **`agent/` is example code, and intentionally not the agent you are calling.**
> The Lab hosts that one. This is the smallest server that still speaks the
> protocol — same card, same extension URIs, same identity reading, with the
> deployment furniture left out — so it can be read in a sitting and built on.
> [`agent/README.md`](agent/README.md) has the two places to change if you want
> your own.

---

# Phase B — make the exchange accountable

The agent's declared skill is issuing your completion code, and it issues one
only to a caller whose gateway vouches for them. So you are not configuring
identity because a recipe told you to. You are configuring it because the agent
will not answer otherwise.

You add two Identity elements, one on each leg of the same surface, and each
takes a different schema from the [`identity/`](identity/) folder in this
recipe's directory, `agentlab-recipes/recipes/hello-agent/identity/`.

![The Hello A2A Agent Surface. A Human uses a Caller, labelled External Agent, which calls the Access Point. Inside the surface, the inbound leg runs from the Access Point to the Managed Agent with an Identity element on it, and the response leg runs back from the Managed Agent to the Access Point with a second Identity element on it. The Managed Agent forwards to the External Target, the Lab's agent endpoint, drawn outside the surface.](images/surface.png)

A message travels from your client to the Access Point, along the **inbound
leg** to the Managed Agent and on to the Lab's agent. The reply comes back along
the **response leg** to the Access Point and your client.

| Step | Leg | Direction | Schema for its Identity element |
| --- | --- | --- | --- |
| 6 | Inbound | Access Point → Managed Agent | `caller-inbound.schema.json` |
| 8 | Response | Managed Agent → Access Point | `agent-response.schema.json` |

> **Do not use `agent-response.schema.json` on the inbound leg.** It describes
> the agent's flat descriptor, which your client does not send, so every message
> through the surface is refused with
> `422 identity_validation_failed: Identity field 'name' not found in payload`.

## 6. Identify the caller — an Identity element on the inbound leg

On the **Access Point → Managed Agent** leg, drag on an **Identity** element:

- Extraction type: **Payload**
- Schema: [`identity/caller-inbound.schema.json`](identity/caller-inbound.schema.json)

A caller self-attests by putting a descriptor in its **message metadata**, under
the extension URI `https://fabric.affinidi.io/extensions/agent-identity/v1`. The
identity element is only ever about the fields under that key, and the schema is
what that object has to look like.

The schema describes the descriptor **exactly as this client sends it** — nested
under `agentIdentity`, because that is how the client writes it — and marks
`name` with `"x-identity": true` while leaving `version` alone. That marker is
the entire mechanism: a schema that describes the payload and marks nothing is
rejected on save. [`identity/README.md`](identity/README.md) has the why, and
the reason `version` is deliberately left out.

The field it extracts is therefore `agentIdentity.name`, and that is the key you
will see come back in the credential. A dotted key is what a nested descriptor
looks like, not a fault.

## 7. Run again, and let the agent tell you what it saw

From here the agent asks you a question before it hands over a code, so use the
interactive prompt rather than a one-shot command. Start it and leave it open
until step 10:

```
./run.sh

you > I would like my completion code.
```

Your message now reaches the agent carrying a gateway-signed Verifiable
Presentation under
`https://fabric.affinidi.io/extensions/agent-identity-binding/v1`. The agent
reports what arrived, and names your caller DID. **Write that DID down.**

You did not send it. Your gateway minted it, from fields you were already
sending about yourself.

Instead of a code, the agent asks what name your gateway signed for you. Leave
the question open while you do steps 8 and 9; you answer it at the same prompt
in step 10.

> **`./run.sh -m "…"` sends one message and exits.** It suits steps where
> nothing comes back asking for an answer. When the agent asks a question, stay
> in `./run.sh` and type the answer at the next `you >` prompt.

## 8. Identify the agent — a second Identity element on the response leg

This is the step nobody finds unaided, so read it twice.

It goes on the **Managed Agent → Access Point** leg. Not on the Managed Agent
node. The Managed Agent carries only an *Identity Binding VP* toggle, which
decides whether something already resolved gets stamped into the forwarded
request; it is a switch, not a place to define an identity. Looking for identity
configuration there and concluding the feature is missing costs an hour.

Mind the vocabulary while you are there: this is the **response leg**. On this
gateway, *outbound* means Transit Points, and the canvas invites the other
reading.

- Extraction type: **Payload**
- Schema: [`identity/agent-response.schema.json`](identity/agent-response.schema.json)

A different schema from step 6, because the two ends of this exchange write
their descriptors differently: you nest yours under `agentIdentity`, the agent
sends its own flat. Each schema describes what its own sender actually puts on
the wire. Two ends, two schemas.

## 9. Send again, and read the workload binding

At the prompt you left open in step 7:

```
you > I would like my completion code.
```

The agent asks its question again — that is expected. The reply now carries
`https://fabric.affinidi.io/extensions/agent-identity-credential/v1`, and its
subject is not a description of the agent. It is a **workload binding**:

```json
{
  "agentIdentity": { "name": "…", "model": "…", "role": "…" },
  "userIdentity":  { "id": "did:webvh:…:surface:…" },
  "delegated": true,
  "traceId": "…"
}
```

`userIdentity.id` is the DID from step 7 — **yours**, minted on the inbound leg.
The gateway stitched the two legs of one request together and signed the result.
One exchange, and a signed record of which agent acted for which caller, tied to
a trace ID you can find in Payload Capture.

Neither you nor the Lab wrote a line of code to produce any of it.

If you want to see the shape before you have earned it:

```bash
./run.sh --replay fixtures/example-response.json
```

## 10. Answer the question, and take your code

At the same prompt, reply with the name your gateway signed:

```
you > <the name your gateway signed for you>
```

Everything you need to answer is in your own client and your own surface. If you
cannot see where, reply `hint` and the agent traces the name for you. Answer in
prose if you like — it matches loosely. What it checks is what you *say* against
what your gateway *signed* on the message carrying your answer, which is the
pattern worth taking away.

A correct answer gets six digits back. Codes are anonymous, last an hour, and
can be spent once.

## 11. Submit the code to the Lab catalogue

**`submit_completion_code` is an MCP tool, not a shell command. Do not type it
into a terminal.** You call it through an MCP client connected to the Lab
catalogue — the one you set up in the *Connect your agent to the Lab* setup
step — at:

```
https://agentlab.choosemission.com/gw/lab-catalog-mcp
```

The tool takes two arguments:

| Argument | Value |
| --- | --- |
| `recipe` | `hello-agent` |
| `code` | the six digits the agent gave you |

In practice you ask your agent to do it, and it makes the call:

> Use the lab-catalog tool `submit_completion_code` with recipe `hello-agent`
> and code `123456`.

Expect two things along the way. If the client is not yet signed in to the Lab,
a browser opens for you to sign in with your Lab account. And most clients ask
you to approve a tool call before it runs — this is the only catalogue tool that
writes anything, so approve it.

The catalogue verified your Lab token, so it knows who you are; the code says a
properly configured gateway got through. Neither is worth much alone.

### In VS Code

This repository ships [`.vscode/mcp.json`](../../.vscode/mcp.json), so opening
the repository folder in VS Code offers the `lab-catalog` server with nothing
to configure:

1. Open the `agentlab-recipes` folder in VS Code. If VS Code asks whether to
   trust or start the `lab-catalog` MCP server, allow it.
2. Open **Copilot Chat** and switch the mode to **Agent**. Tools are only
   available in Agent mode.
3. Ask it to submit the code, as above.
4. Sign in with your Lab account if a browser opens, then approve the
   `submit_completion_code` call when VS Code asks.

The reply confirms the completion was recorded, or tells you why not — see
*When it fails unexpectedly* below.

### In Claude Code

If `lab-catalog` is not already connected:

```bash
claude mcp add --transport http lab-catalog https://agentlab.choosemission.com/gw/lab-catalog-mcp
```

Then, in a session, run `/mcp`, authenticate `lab-catalog`, and ask as above.

---

## The honest limit, which is also the lesson

The agent required a presentation. It must not, and does not, treat what the
presentation *says* as identifying you.

Two reasons, and both matter more than the credential does.

**Payload extraction is self-asserted.** The DID is a deterministic hash of
fields *you chose to send about yourself*. Change `A2A_AGENT_NAME` in your
`.env` and run again: a different DID, and nothing stopped you. It is a stable
pseudonymous identifier that a gateway signs — not proof that the caller is who
it claims. When a DID must be anchored in something the caller has to
*possess*, the modes for that are mTLS, API key and JWT claim. Say which of the
two you mean when you tell somebody their traffic is "identified".

**And the signature is yours.** The gateway that signed that presentation is
*your* gateway. You control it, so you control what it asserts. The credential
proves you configured identity. It proves nothing about who you are.

So what the agent can honestly say is: *this caller has an identity, here is
what it claims, and I cannot know whether any of it is true.* That is a more
useful position than "look, a credential" — and it is exactly the gap the next
recipes close, where the gateway doing the signing finally belongs to somebody
else.

---

## Make it fail on purpose

Three failures, all of them real, and each teaches something the success does
not.

**Mark nothing with `x-identity`.** Remove the marker from the inbound schema
and save. You get a 400 complaining about undeclared identity fields — which
never names the marker it is missing. Now you know what that message means.

**Mark `version` as an identity field.** Add `"x-identity": true` to `version`,
save, then run with `--agent-version 1.0.1`. Your DID changes. This is why every
record keyed to the old one now refers to nobody, and why the schemas here mark
only stable, configuration-level fields.

**Put the wrong schema on a leg.** Paste the flat response-leg schema onto the
inbound element. The save does not complain — the schema is valid JSON Schema —
but every message is then refused with
`422 identity_validation_failed: Identity field 'name' not found in payload`,
because the gateway looks for a top-level `name` where your client wrote
`agentIdentity.name`. The error names the field and not the leg, so it is easy
to read as a problem with your client. Swap it back and the next message goes
through.

The same mismatch the other way round — the nested inbound schema on the
response leg — has not been recorded here with its exact symptom; expect no
credential on the reply. Whichever leg is wrong, the reliable answer is
**Capture Identity Payload**: capture what the sender really sends, and generate
the schema from that rather than reasoning about it.

---

## When it fails unexpectedly

**Payload Capture first, always.** Four stages per request: what you sent, what
the gateway made of it, what actually arrived at the target, what came back.
Once you can read those four, you can debug everything else in the Lab. Every
request also carries a trace ID, returned as `X-Gateway-Trace-Id` — quote it
with a timestamp when you ask for help.

| What you see | Usually means |
| --- | --- |
| `No route configured for path: …` | The access point URL is wrong, or the surface is not live |
| Card fetch fails, messages never sent | Step 2.3 — the endpoint URL is the host without its path |
| The agent's own 401, through the surface | Step 2.4 — header name or secret value mismatch. Two strings to compare, not a gateway to audit |
| `Invalid JSON-RPC request` | You did a plain GET on the message endpoint |
| Card `url` warning from the client | The surface is serving the card through without rewriting it |
| 400 on save, "no identity fields are declared" | Nothing in the schema carries `"x-identity": true` |
| `422 identity_validation_failed: Identity field 'name' not found in payload` | `agent-response.schema.json` is on the inbound leg. Put `caller-inbound.schema.json` on the Access Point → Managed Agent leg: your client sends `agentIdentity.name`, not a top-level `name` |
| No identity resolved, and no error anywhere | A schema is on the wrong leg, or does not match how that sender nests. Check each against the diagram at the start of Phase B, then use Capture Identity Payload |
| No credential on the reply at all | The second Identity element is not on the Managed Agent → Access Point response leg — often because it was put on the Managed Agent node instead |
| A DID that changes every run | A moving value is marked as an identity field |
| No code, and the agent says why | Working as intended. Finish step 6 or 8, or answer its question (step 10) |
| `submit_completion_code: command not found` | It is an MCP tool, not a shell command. See step 11 |
| `wrong-recipe` when you submit | The code is real and unspent. Submit it again naming `hello-agent` |
| `unknown-code` when you submit | Most likely expired — codes last an hour. Check the digits, then ask the agent for a fresh one |
| `not-signed-in` when you submit | Your client reached the catalogue without a Lab sign-in. Connect it to `https://agentlab.choosemission.com/gw/lab-catalog-mcp`, not to any other catalogue address |

If the agent misbehaves rather than the surface, run the copy in `agent/`
locally and compare. Two one-layer debugs beat one five-layer debug.

Then the Lab Slack, which you joined during onboarding. Honest friction reports
shape what the Lab builds next.

---

## What you can carry back

- An A2A exchange is a **task with state**, not a call and a return, and its
  skills are prose because the callee decides how.
- Identity an agent asserts about itself is worth less than the same fields
  **signed by a gateway** — and knowing exactly how much less is the skill.
- One governed exchange yields a **signed record of which agent acted for which
  caller**, with a trace ID, from configuration rather than code.
- A credential your own gateway signed proves you configured identity, and not
  who you are.

## Licence and provenance

Apache-2.0. Parts of this directory are vendored from Affinidi's
[affinidi-labs-tgw-get-started](https://github.com/affinidi/affinidi-labs-tgw-get-started);
[`PROVENANCE.md`](PROVENANCE.md) records what, from which commit, and what was
changed.
