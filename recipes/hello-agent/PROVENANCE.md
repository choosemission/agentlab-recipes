# Provenance

Parts of this directory come from Affinidi's
[affinidi-labs-tgw-get-started](https://github.com/affinidi/affinidi-labs-tgw-get-started),
Apache-2.0. The editorial line: **their repository is a reference
implementation, this one is a lesson.** Anything whose bytes have to match
gateway behaviour is carried across unchanged; anything that only has to teach
is ours.

## Vendored unchanged

| File here | Upstream path | Upstream commit |
| --- | --- | --- |
| `identity/agent-response.schema.json` | `a2a/identity-extension.json` | `b29bf48a45cfcbc1aeafad173b66e0a3a3705d4a` (2026-04-22) |
| `requirements.txt` (the `a2a-sdk` pin) | `a2a/requirements.txt` | `a516a170be9e3e68a1f54592e128af1c331df37a` (2026-07-15) |

`agent-response.schema.json` is byte-identical to upstream, which is why it has
no header comment and no trailing newline. It is the schema for the response
leg, and its choice to mark `name`, `model` and `role` while leaving `version`
out is a decision worth preserving rather than a detail — see
`identity/README.md`.

## Adapted

**`a2a_client.py`**, from `a2a/a2a_client.py` at
`a516a170be9e3e68a1f54592e128af1c331df37a` (2026-07-15).

Carried over unchanged, because the gateway matches on them:

- the extension URI `https://fabric.affinidi.io/extensions/agent-identity/v1`
- the shape of the metadata envelope — the descriptor nested under
  `agentIdentity`, with `name` and `version` and no `model` or `role`. The
  inbound schema in `identity/` is written against exactly this.
- the default descriptor values, `"A2A Test Client"` / `"1.0.0"`, so a DID
  minted from this client is the same DID upstream's would mint.

Changed, and why:

| Change | Why |
| --- | --- |
| Carries `contextId` forward between messages | Upstream sends every message cold, so the server opens a new context each time and Phase A step 4 — "watch `contextId` persist while `taskId` changes" — cannot be observed at all |
| Accepts `--task-id`, and `--context-id` | Continues an existing task, so an `input-required` turn can be answered rather than restarted |
| Pretty-prints the envelope as JSON | Upstream prints a Python dict `repr`: one unwrapped line, thousands of characters. The participant is asked to read this envelope closely in steps 4 and 9 |
| Adds the "what to notice" summary | Names the envelope fields, and extracts the response-leg credential and workload binding. Reporting, not reasoning — the full envelope is still printed above it, and the summary points rather than concludes |
| Adds `--card` | Step 3 is reading the agent card. Upstream logs three fields of it in passing |
| Adds `-m/--message` for one-shot sends | The participant's own agent drives this; an interactive-only REPL is awkward to script and awkward to show output from |
| Adds `--replay` | Renders a saved envelope, so `fixtures/example-response.json` shows what step 9 looks like before it works |
| Adds `--agent-name` / `--agent-version` | Changing the presented name and watching the DID change is how the recipe's central honest limit is demonstrated in one command |
| TLS verification **on** by default, `--insecure` to opt out | Upstream hard-codes `verify=False` and suppresses the warning. The recipe calls an HTTPS gateway; shipping participants a client that never checks a certificate teaches the wrong habit |
| Drops the silent localhost card rewrite; warns on a host mismatch instead | A card whose `url` is not the address you called is a *finding* in this recipe — the gateway rewrites cards, so a mismatch means the surface did not. Upstream's silent fix hides exactly the thing step 3 exists to show. The rewrite is kept only for a card advertising localhost, which is the local-debugging path, and it says when it fires |
| `argparse`, env-var defaults, structured exits | It is now configured by `.env`, and run by an agent as well as a person |

Not changed, deliberately: there is no model in it, and nothing
non-deterministic. Upstream's interactive REPL that prints raw JSON is the right
client for a path whose failures have to stay diagnosable.

## Ours

`README.md`, `CLAUDE.md`, `run.sh`, `.env.example`, `identity/README.md`,
`identity/caller-inbound.schema.json`, `fixtures/` and this file.

`fixtures/example-response.json` is **synthetic** — placeholder DIDs, zeroed
UUIDs, and `proofValue`s that are strings rather than signatures. It records the
shape of a response, and nothing in it was issued by or verifies against any
gateway.

## `agent/`

**Second-order derivation, and the one place in this repository where that is
true.** `agent/agent.py` and `agent/__main__.py` come from Affinidi's
`a2a/a2a_server.py` at `64babfc3ef27a3b1fb73ec9c25246b032b5708c4` **by way of**
`hello_a2a/agent.py` and `hello_a2a/identity.py` in the Lab's own repository.
Both files carry that chain in their headers.

Carried across unchanged, because the gateway matches on them: the extension
URIs, the agent card's extension block, and the flat identity descriptor in the
reply's metadata. Carried across from the Lab's server: the reading of a
gateway-signed presentation, including the fact that `verifiablePresentation`
arrives serialised rather than nested.

**The Lab runs a variation of this**, and this is intentionally not that one —
not a copy of it, and not a stand-in awaiting one. It is a documented example of
the server side of A2A: the smallest thing that still speaks the protocol,
written to be read in a sitting and adapted into something else. The completion
codes, the API-key gate, the health endpoints, the logging module and the
env-driven public-URL configuration are all left out, and its card names it
`Hello A2A Agent (example)` so a DID derived from it cannot be confused with one
derived from the Lab's agent.

## Keeping up with upstream


When a vendored file changes upstream, `git log` on the recorded commit shows
what moved. Re-vendor the unchanged files directly; for `a2a_client.py`, diff
upstream against the recorded commit and apply only what the table above does
not deliberately override.
