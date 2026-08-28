# CLAUDE.md — Hello, agent

You are helping a participant run **Hello, agent**, a recipe from the Agent Lab
— a neutral environment for practical experimentation with agent trust, run by
MISSION.

Walk them through it; do not complete it silently. Almost everything worth
learning here is something they have to *see*: a card that was rewritten, an
envelope that is a task rather than a return value, a DID that appeared without
either side sending it. Run the commands, then stop and point at what changed.
A run you did for them while they read the output afterwards teaches half as
much.

## Orientation

Discovery lives on the Lab's catalogue MCP server, not in this file. If this
session is not connected:

```bash
claude mcp add --transport http lab-catalog https://agentlab.choosemission.com/mcp
```

Sign-in opens a browser and they authenticate as themselves — expected, not
broken. Tell them it is coming. Then `get_started` orients you, and
`get_recipe` with id `hello-agent` returns the catalogue entry.

## What this recipe is

They put **their own** Agent Gateway in front of an A2A agent **the Lab hosts**,
then configure two Identity elements. The result is a signed record of which
agent acted for which caller, produced by configuration rather than code.

- **Entry point:** `README.md` in this directory. It is the authority; if
  anything here contradicts it, the README wins and this file needs the fix.
- **Phase A** (steps 1–5, ~15 min) teaches the protocol from artefacts they
  already have. **Phase B** (steps 6–10, ~45 min) is the identity work.

## The one thing not to get wrong

**They call the Lab's hosted agent through their own gateway. They do not run
the agent.** The source in `agent/` is there to be *read* — reading it is what
proves the agent contributed none of the credentials.

`agent/` is example code: the smallest A2A server that still speaks this
protocol, written to be read and built on, and **intentionally not the agent
they are calling**. Do not present it as the deployed one, and do not treat a
difference between the two as a finding. Running it on localhost is fine and
step 5 asks for it. **Pointing a surface at it is not** — that means a tunnel,
and a restarted tunnel invalidates the target URL and the agent card at once.

## Before running anything

Check rather than assume:

- **Python 3.10+.** `python3 --version`.
- **`hello-gateway` completed**, and a gateway from the `get-a-gateway` setup
  step. Steps 2–3 assume they have created a surface before.
- **A Lab account.** Everything is behind sign-in; send them to the Lab website
  rather than improvising.
- **`.env` exists**, copied from `.env.example`, with `A2A_ACCESS_POINT` set to
  their surface's access point — not the Lab's resource URL.

**The Lab's API key goes into their gateway as target authentication, never into
this client.** The client has no way to accept one. If you find yourself looking
for where to put a key in the code, that is the recipe working.

## Running it

Everything goes through `./run.sh`, which creates `venv/` on first use, loads
`.env`, and passes its arguments to `a2a_client.py`.

| Step | Command | Stop and point at |
| --- | --- | --- |
| 3 | `./run.sh --card` | Skills in **prose**, not JSON Schema — contrast with `tools/list` from `hello-gateway`. And `url` naming their gateway, because it was rewritten |
| 4 | `./run.sh` then two messages | `kind: task`, and `contextId` holding while `taskId` changes |
| 5 | read `agent/`, then `./venv/bin/python agent/` | What an A2A server actually is, and that nothing in one this size could mint a credential. Run it: no gateway in front of it, so **CASE 3 — NOTHING SIGNED**, and the contrast with step 7 is the point. It is example code, **intentionally not the deployed agent** — say so plainly |
| 7 | `./run.sh -m "I would like my completion code."` | The caller DID the agent reports. **Record it** — step 9 needs it |
| 9 | same command again | The `workloadBinding`, and `userIdentity.id` matching step 7's DID |
| — | `./run.sh --replay fixtures/example-response.json` | The shape of a working step 9, using synthetic placeholder data |

Gateway configuration is theirs to do in the console — steps 2, 6 and 8. You
cannot do those for them. Your job there is to have the right schema file open
and to be precise about *which leg*.

## What you will see, and what it means

- **Success:** the reply carries
  `https://fabric.affinidi.io/extensions/agent-identity-credential/v1`, and its
  subject is a `workloadBinding` whose `userIdentity.id` is the DID minted on
  the inbound leg. The client prints it under "WHAT YOUR GATEWAY ADDED".
- **Before step 6, and between 6 and 8, there is no credential.** That is the
  baseline, not a fault. Say so rather than debugging it.
- **The deliberate failures** are in the README and worth doing: unmark
  `x-identity` (a 400 that never names the marker), mark `version` (a DID that
  moves on redeploy), leave the meta field set on the response leg
  (`identityFields` with dotted keys). Show the failure before fixing it.

## The claim to state accurately

If they conclude the credential proves who they are, correct it — it is the
point of the recipe, not a footnote.

The DID is a hash of fields **they chose to send about themselves**, and the
signature is from **their own gateway**. It proves identity was configured. It
proves nothing about who they are. `--agent-name` demonstrates this in one
command: change it, run again, watch the DID change with nothing stopping it.

Modes anchored in something the caller must possess are mTLS, API key and JWT
claim. Do not oversell payload extraction as any of those.

## Rules of engagement

Lab-wide, and not negotiable:

- **Calls to Lab targets go through the Agent Gateway, and the target admits
  nothing else.** If a call fails, do not route around the gateway and do not
  try to reach the agent directly except for the deliberate 401 in step 5.
  Being unable to is the security property this Lab demonstrates. Read the
  refusal, then read Payload Capture: what was sent, what the gateway made of
  it, what arrived, what came back.
- **Short-lived tokens are normal.** A call that worked minutes ago can start
  returning 401. Re-authenticate and carry on.
- **This is an experimental environment.** No production data, no personal
  content, no real credentials beyond the ones the Lab issues. No warranty, no
  SLA.
- **Secrets stay local.** `.env` and `venv/` are gitignored. Never commit the
  Lab's API key, and never paste a completion code into anything but
  `submit_completion_code`.

## When something fails unexpectedly

The README's troubleshooting table covers what this recipe actually produces —
work it before improvising. In order:

1. **Payload Capture** on the surface. Four stages. Nearly every failure here is
   visible in the difference between stage 1 and stage 2.
2. **Which leg?** A missing credential is usually an Identity element on the
   Managed Agent node rather than on the response leg.
3. **Which meta field?** Dotted keys in `identityFields` mean the meta field is
   set on a leg whose sender sends flat.
4. **Capture Identity Payload**, on the Identity element, if the nesting is in
   doubt at all. It generates the schema from a real request and settles the
   question; do not guess at it.
5. If you cannot tell whether the surface or the agent is at fault, `agent/`
   answers one question well: what a request looks like when no gateway touched
   it. Run it, send the same message directly, and compare envelopes. It is not
   the hosted agent, so a difference in *behaviour* proves nothing — the
   envelope is what is worth comparing.

Then the Lab Slack, which they joined during onboarding. Encourage them to
report what they hit — honest friction reports shape what the Lab builds next.
