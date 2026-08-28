# agent/

**A worked example of the server side of A2A.** Two files, mostly comments. Read
it to see what is on the other side of the calls you have been making, run it to
watch one arrive, and take it as the starting point for your own.

The Lab runs **a variation of this** as the agent your surface calls in this
recipe — same card, same extension URIs, same reading of what your gateway
signed, with completion codes and a key on the door. This one is the version
without the deployment on it, so what you read is the mechanism.

## What an A2A server is made of

Three pieces, all of them in [`__main__.py`](__main__.py):

| Piece | What it is | Where |
| --- | --- | --- |
| **The agent card** | What a caller discovers before sending anything: name, description, skills, extensions. Served at `/.well-known/agent-card.json` | `create_agent_card`, in [`agent.py`](agent.py) |
| **The executor** | Your agent. One method: a message arrived, do something | `IdentityMirrorExecutor`, in `agent.py` |
| **The request handler** | The SDK's plumbing between them — parses the JSON-RPC, creates the task, runs your executor, stores the result | `DefaultRequestHandler` |

`A2AStarletteApplication(...).build()` returns an ordinary Starlette app with the
routes A2A requires already mounted. Everything you write is the first two rows.

### The one idea worth taking away

`execute` **returns nothing.** A2A hands you the request and an event queue, and
you publish onto the queue:

```python
async def execute(self, context, event_queue):
    updater = TaskUpdater(event_queue, context.task_id, context.context_id)
    await updater.complete(updater.new_agent_message([...]))
```

That is why the client prints `kind: task` rather than a result. A call is a task
with a lifecycle — it can be polled, answered over several turns, or cancelled —
where an MCP `tools/call` is a function that returns once. `complete()` is the
short path; `start_work()`, `requires_input()`, `failed()` and `add_artifact()`
are the others, and `agent.py` lists them where you would reach for them.

`requires_input` is the one with no MCP equivalent: the agent asks a question,
the task parks in `input-required`, and the caller answers on the next message in
the same `contextId`. That is also what makes `contextId` and `taskId` worth
watching in step 4 — one holds across a conversation, the other is per task.

## Read it

[`agent.py`](agent.py) is the agent. Three things worth finding:

- **The card**, in `create_agent_card`. Its skill is described in **prose**, not
  JSON Schema — put that beside `tools/list` from `hello-gateway` and you have
  the MCP/A2A distinction without a paragraph of theory.
- **The three cases**, in `read_caller_identity` and `describe`: an unsigned
  descriptor the client sent about itself, a presentation the gateway signed, or
  nothing at all. Phase A of the recipe produces the first, Phase B the second.
  Note that identity arrives in `message.metadata` — it rides with the message,
  which is why an agent can read it without being told about a header.
- **Nothing that could mint a credential.** No model, no reasoning, no signing
  key — dictionary reading, end to end. Every DID and presentation in this
  recipe came from the gateway, and an agent this size is where that is easy to
  see.

Note what `describe` says once it has found a presentation: that a proof is
**present**, not that it verified one. Verifying would not change the conclusion,
because the presentation is signed by your own gateway over fields your own
client sent — evidence that identity was configured, and evidence of nothing
else.

## Run it

```bash
./run.sh --card                 # once, if venv/ does not exist yet — it builds it
./venv/bin/python agent/        # serves on http://localhost:8080
```

Then, from another terminal:

```bash
curl -s localhost:8080/.well-known/agent-card.json
./run.sh --card http://localhost:8080/
./run.sh -m "hello" http://localhost:8080/
```

Called directly you get **CASE 3 — NOTHING SIGNED** every time, because there is
no gateway in the path to sign anything. That is the useful part: in step 7 you
send the same message through your surface and get CASE 2, and the difference is
entirely the gateway's doing.

**Do not point a surface at it while running the recipe.** That means a tunnel,
and a restarted tunnel invalidates the target URL and the agent card at the same
moment.

## Adapt it

Smallest useful changes first:

1. **Change what it says.** The body of the reply is one line in `execute`.
   Everything around it — the task, the metadata, the extensions — keeps working.
2. **Change what it advertises.** `create_agent_card` is the name, description
   and skills a caller discovers. Add a skill and describe it in prose; there is
   no schema to fill in, and the description is what another agent reads to
   decide whether to call you.
3. **Answer over more than one turn.** Swap `updater.complete(reply)` for
   `updater.requires_input(reply, final=True)` and the task parks until the
   caller replies. Nothing is remembered for you between turns — read what you
   need off the incoming message each time, or put it in the task store.
4. **Change the agent's own identity.** `AGENT_IDENTITY` is an interface, not a
   label: a response-leg Identity element marks fields in it with
   `"x-identity": true`, so the DID the gateway derives is a hash of exactly
   those. Change one and watch the DID move. `version` is deliberately left
   unmarked — [`../identity/README.md`](../identity/README.md) has why.

Two things this leaves out that you would want in something real:

- **A door.** There is no authentication on it at all. Behind an Agent Gateway
  you would give the agent a key and configure it as target authentication on
  the surface, so the agent admits the gateway and nothing else — which is what
  every Lab target does, and why you cannot call one directly.
  [`__main__.py`](__main__.py) says where the check goes.
- **Verifying the presentation**, rather than checking that one is present. Do
  it if you like — resolve the issuer DID and check the proof. But keep the
  limit honest either way: a server that treats a presentation as proof of *who*
  called it is the one mistake here that matters, and no amount of signature
  checking fixes it while the signer is the caller's own gateway.

## Provenance

Derived at second hand from Affinidi's `a2a/a2a_server.py` (Apache-2.0) by way of
the Lab's own server. The extension URIs, the card's extension block and the flat
identity descriptor in the reply's metadata are carried across unchanged, because
the gateway matches on them. See [`../PROVENANCE.md`](../PROVENANCE.md) and the
repository's `NOTICE`.
