# identity/

The two schemas you paste into the two Identity elements. One per leg, and they
are different, because the two ends of this exchange nest their descriptors
differently.

| File | Leg | Marks |
| --- | --- | --- |
| `caller-inbound.schema.json` | Access Point → Managed Agent (**inbound**) | `agentIdentity.name` |
| `agent-response.schema.json` | Managed Agent → Access Point (**response**) | `name`, `model`, `role` |

## The rule, and it is the only one

**A schema describes the descriptor exactly as its sender writes it**, under the
extension key `https://fabric.affinidi.io/extensions/agent-identity/v1`. Nothing
un-nests it for you and nothing rewrites the paths. What you paste is what the
gateway matches against, key for key.

This client sends (see `build_message_payload` in `a2a_client.py`):

```json
{ "agentIdentity": { "name": "A2A Test Client", "version": "1.0.0" } }
```

— so the inbound schema has an `agentIdentity` object in it, with the marked
field inside. The extracted field is `agentIdentity.name`, and that is the key
that comes back in the credential's `identityFields`. **A dotted key there is
what a nested descriptor looks like.** It is not a symptom of anything.

The agent sends its descriptor **flat**:

```json
{ "name": "…", "model": "…", "role": "…", "version": "1.0.3" }
```

— so the response schema is flat, and its paths are `name`, `model`, `role`.

Two senders, two shapes, two schemas. That is the whole of it.

## `x-identity` is the whole mechanism

A field is only extracted into the DID if it carries `"x-identity": true`. A
schema that describes the payload perfectly and marks nothing is rejected on
save with a 400 complaining that no identity fields are declared — a message
that never names the marker it is missing.

Both schemas here also *describe* `version` without marking it. Describing is
not declaring; the unmarked field is documentation of what arrives.

## Why `version` is not marked

Both descriptors carry a `version`. Neither schema extracts it.

The DID is a deterministic hash of the marked fields, so marking `version` means
the agent gets a different DID the next time anyone bumps a version number.
Every record referring to the old DID then refers to nobody. Mark stable,
configuration-level facts; leave anything that moves on a release out.

Affinidi's own `identity-extension.json` makes exactly the same choice — marking
`name`, `model` and `role`, leaving `version` alone — and it is worth noticing
that it is a choice rather than an oversight.

## If the extraction does not behave

The failure to expect is silent: a schema that is valid JSON Schema but does not
match how that sender nests, extracting nothing and reporting nothing.

Do not guess at the nesting. The gateway will tell you: **Capture Identity
Payload** on the Identity element exposes a temporary endpoint with automatic
expiry. Point this client at it, send one message, then select the captured
request and click **Use This Schema**. The schema it generates is the ground
truth for how that sender actually nests; compare it with the file here and
believe the capture.
