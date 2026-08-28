# identity/

The two schemas you paste into the two Identity elements. One per leg, and they
are different, because the two ends of this exchange nest their descriptors
differently.

| File | Leg | Meta field | Marks |
| --- | --- | --- | --- |
| `caller-inbound.schema.json` | Access Point → Managed Agent (**inbound**) | `agentIdentity` | `name` |
| `agent-response.schema.json` | Managed Agent → Access Point (**response**) | *(empty)* | `name`, `model`, `role` |

## Why they differ

Both sides put their descriptor under the same extension key,
`https://fabric.affinidi.io/extensions/agent-identity/v1`. What they put there
is not the same shape.

This client sends (see `build_message_payload` in `a2a_client.py`):

```json
{ "agentIdentity": { "name": "A2A Test Client", "version": "1.0.0" } }
```

— nested, so the inbound element's **meta field** is `agentIdentity` and the
schema describes what sits inside it.

The agent sends its descriptor **flat**:

```json
{ "name": "…", "model": "…", "role": "…", "version": "1.0.3" }
```

— so the response element's meta field must be **empty**. Leaving `agentIdentity`
in it there is the single most common way to get this wrong, and the diagnostic
is in the credential: `identityFields` comes back with dotted keys like
`agentIdentity.name`, which is the gateway telling you the paths it extracted
were relative to a prefix the sender never used.

## `x-identity` is the whole mechanism

A field is only extracted into the DID if it carries `"x-identity": true`. A
schema that describes the payload perfectly and marks nothing is rejected on
save with a 400 complaining that no identity fields are declared — a message
that never names the marker it is missing.

## Why `version` is not marked

Both descriptors carry a `version`. Neither schema extracts it.

The DID is a deterministic hash of the marked fields, so marking `version` means
the agent gets a different DID the next time anyone bumps a version number.
Every record referring to the old DID then refers to nobody. Mark stable,
configuration-level facts; leave anything that moves on a release out.

Affinidi's own `identity-extension.json` — which is
`agent-response.schema.json` here, byte for byte — makes exactly this choice,
and it is worth noticing that it is a choice rather than an oversight.

## If the extraction does not behave

Do not guess at the nesting. The gateway will tell you: **Capture Identity
Payload** on the Identity element exposes a temporary endpoint with automatic
expiry. Point this client at it, send one message, then select the captured
request and click **Use This Schema**. The schema it generates is the ground
truth for how that sender actually nests; compare it with the file here and
believe the capture.
