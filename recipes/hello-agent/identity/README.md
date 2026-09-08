# Identity schemas

Paste each file's JSON contents into the field editor of the corresponding
Identity element, using payload extraction.

| File | Leg | Marked paths |
| --- | --- | --- |
| `caller-inbound.schema.json` | Caller → managed agent (inbound) | `agentIdentity.name` |
| `agent-response.schema.json` | Managed agent → caller (response) | `name`, `model`, `role` |

The tested A2A dashboard has no separate Meta field control. The schema must
match the descriptor under
`https://fabric.affinidi.io/extensions/agent-identity/v1` in message metadata.

The client sends a nested descriptor:

```json
{ "agentIdentity": { "name": "A2A Test Client", "version": "1.0.0" } }
```

The inbound Request Schema includes that `agentIdentity` wrapper, with
`"x-identity": true` on the nested `name` property.

The hosted agent sends a flat descriptor:

```json
{ "name": "AgentLab Hello A2A Agent", "model": "none", "role": "completion-code issuer", "version": "1.0.0" }
```

The response schema therefore defines its fields directly under `properties`.
The bundled schema marks `name`, `model` and `role`. A schema marking only
`name` is also valid. Dotted field paths in a credential are not inherently an
error: `agentIdentity.name` is the correct path for this caller.

## Choosing identity fields

The `x-identity` marker selects fields that contribute to the derived DID.
Neither bundled schema marks `version`: marking it would change the derived
identity when the version changes. The response schema is retained from
Affinidi's `a2a/identity-extension.json`; see [PROVENANCE.md](../PROVENANCE.md).

## A2A v1.0 release blocker

The tested Affinidi gateway signs responses from the old setup but does not
extract response identity from the v1.0 `result.task.status.message` envelope.
Inbound signing still works. This is a gateway response-processing bug, not a
reason to change a matching identity schema. The migration remains unmerged
until the gateway fix is available and the complete exchange is retested.
