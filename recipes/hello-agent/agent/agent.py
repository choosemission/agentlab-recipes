# Copyright 2026 Choose Mission Ltd
# Portions copyright Affinidi Pte. Ltd., from `affinidi-labs-tgw-get-started`
# at commit 64babfc3ef27a3b1fb73ec9c25246b032b5708c4 (`a2a/a2a_server.py`), by
# way of `hello_a2a/agent.py` and `hello_a2a/identity.py` in the Lab's own
# repository. See PROVENANCE.md.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at http://www.apache.org/licenses/LICENSE-2.0
#
# See NOTICE for the attribution this file carries.
"""A minimal A2A server. Read it, run it, build on it.

**Intentionally not the agent your surface calls.** The Lab hosts that one, and
this is not a copy of it — it is the smallest thing that still speaks the
protocol the recipe is about, so what you read is the mechanism rather than a
deployment. Left out on purpose, none of it A2A: completion codes, the API-key
gate that admits only a gateway, health endpoints, structured logging, and
env-driven public-URL configuration.

Two places to change if you are building on this. `create_agent_card` is what
callers discover, and `IdentityMirrorExecutor.execute` is what happens when one
sends a message — replace the body of the reply and everything below stays true.

What is here is what the exchange turns on — the card with the extension URIs
the gateway reads and writes, and the three descriptions of a caller that can
arrive in one message:

1. **Self-asserted** — your client's own descriptor, under
   `.../extensions/agent-identity/v1`. Unsigned. What Phase A sees.
2. **Gateway-signed** — a Verifiable Presentation your gateway attached once an
   Identity element was configured on the inbound leg. It arrives **serialised**:
   `verifiablePresentation` holds a JSON string, not a nested object.
3. **Nothing at all**, when the call reached the agent some other way.

**What (2) is worth, exactly.** This checks that a well-formed presentation
carrying a proof is present. It does not verify the signature and does not
resolve the issuer DID — and verifying would not change the conclusion, because
the presentation is signed by *your own* gateway over fields *your own* client
sent. It is evidence that identity was configured, and evidence of nothing else:
not of who you are, not of the truth of any field inside it. Keep that limit in
anything you build on this; a server that reports a presentation as proof of who
called it is the one mistake here that matters.

Nothing in this file produces a credential: no model, no reasoning, no signing
key, just dictionary reading. Everything verifiable in the recipe came from the
gateway, and an agent this size is where that is easy to see.

Pinned against `a2a-sdk==0.3.25` and `uvicorn==0.38.0` — what the deployed target
and Affinidi's own sample use, because a minor version that moved a field would
break the envelope this recipe is about.
"""

from __future__ import annotations

import json
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentSkill, Part, TextPart

#: Verbatim from upstream, and the reason this file exists: these are the keys
#: the gateway matches on. Your client puts its unsigned descriptor under the
#: first; the gateway puts what it signed under one of the second pair —
#: `binding` on the inbound leg, `credential` on the response leg.
SELF_ASSERTED_EXTENSION = "https://fabric.affinidi.io/extensions/agent-identity/v1"
GATEWAY_EXTENSIONS = (
    "https://fabric.affinidi.io/extensions/agent-identity-binding/v1",
    "https://fabric.affinidi.io/extensions/agent-identity-credential/v1",
)
METADATA_EXTENSION = "https://fabric.affinidi.io/extensions/agent-metadata/v1"

#: The fields a response-leg Identity element marks with `"x-identity": true`,
#: so the DID the gateway derives for this agent is a hash of exactly these.
#: `version` is here and deliberately *not* marked: mark it and the DID moves on
#: the next release. Change any of the other three and the DID changes with it,
#: which is worth doing once to watch happen.
AGENT_IDENTITY: dict[str, str] = {
    "name": "Hello A2A Agent (example)",
    "model": "none",
    "role": "identity mirror",
    "version": "1.0.0",
}


def create_agent_card(public_url: str) -> AgentCard:
    """The discovery document, and two things it shows you for free: a skill in
    **prose** rather than JSON Schema — the MCP/A2A distinction, beside
    `tools/list` from `hello-gateway` — and, once fetched *through* your surface,
    a `url` naming your gateway, because the gateway rewrote the card it served.
    """
    return AgentCard(
        name=AGENT_IDENTITY["name"],
        description=(
            "Reads what your Agent Gateway signed about you on the way in and tells you what "
            "it saw. It runs no model: everything verifiable about your call was added by the "
            "gateway, not by this agent."
        ),
        url=public_url.rstrip("/") + "/",
        version=AGENT_IDENTITY["version"],
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[
                # `params` is the response-leg schema: the fields the Identity
                # element on that leg reads, published so it can be configured.
                AgentExtension(uri=SELF_ASSERTED_EXTENSION, description="Supports agent identity exchange",
                               required=False, params=dict(AGENT_IDENTITY)),
                AgentExtension(uri=METADATA_EXTENSION, description="Exposes agent model and runtime metadata",
                               required=False),
            ],
        ),
        skills=[
            AgentSkill(
                id="describe-caller-identity",
                name="Say what your gateway signed about you",
                description=(
                    "Tell me anything. I report which of three things arrived with your message: "
                    "an unsigned descriptor your client sent about itself, a presentation your "
                    "gateway signed, or nothing at all. The contrast is the whole exercise."
                ),
                tags=["identity", "agent-lab"],
                examples=["hello", "What did my gateway tell you about me?"],
            )
        ],
    )


def _as_object(value: Any) -> dict[str, Any] | None:
    """The value as a JSON object, whether it arrived as one or as a string.

    The gateway sends `verifiablePresentation` **serialised** — a JSON string.
    Read only the nested form and a participant whose Identity element is
    configured correctly is told their gateway signed nothing, then sent back to
    re-configure something that was working.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _has_proof(container: dict[str, Any]) -> bool:
    proof = container.get("proof")
    return isinstance(proof, dict) and bool(proof.get("proofValue"))


def read_caller_identity(metadata: Any) -> dict[str, Any]:
    """Sort one message's metadata into the three cases. Never raises.

    Returns `self_asserted` (case 1, or None) and `presentation` (case 2, or
    None — which with no descriptor either is case 3).
    """
    metadata = metadata if isinstance(metadata, dict) else {}

    # Flat, or wrapped in `agentIdentity` — the meta field you set on the
    # Identity element decides which, and both are worth showing back.
    descriptor = metadata.get(SELF_ASSERTED_EXTENSION)
    descriptor = descriptor if isinstance(descriptor, dict) else {}
    inner = descriptor.get("agentIdentity")
    self_asserted = dict(inner) if isinstance(inner, dict) else dict(descriptor) or None

    for extension, entry in metadata.items():
        if extension == SELF_ASSERTED_EXTENSION or not isinstance(entry, dict):
            continue
        document = _as_object(entry.get("verifiablePresentation"))
        if document is None:
            continue
        credential = document.get("verifiableCredential")  # an object here, a list in the W3C model
        credential = _as_object(next(iter(credential), None) if isinstance(credential, list) else credential)
        # A presentation with no credential or no proof is not one. Refusing it
        # here is what stops a caller pasting `{"type": ["VerifiablePresentation"]}`
        # into its own metadata and being reported as gateway-signed.
        if credential is None or not (_has_proof(document) or _has_proof(credential)):
            continue
        subject = credential.get("credentialSubject")
        subject = subject if isinstance(subject, dict) else {}
        issuer = credential.get("issuer")
        fields = subject.get("identityFields")
        return {
            "self_asserted": self_asserted,
            "presentation": {
                # On the inbound leg this DID is your *surface's*, which is what
                # makes the response leg's workload binding joinable to it.
                "did": next((v for v in (entry.get("did"), document.get("holder"), subject.get("id"))
                             if isinstance(v, str) and v), None),
                # The fields the gateway hashed to derive that DID: the ones you
                # marked `"x-identity": true`.
                "identity_fields": dict(fields) if isinstance(fields, dict) else {},
                # Your gateway's own DID. It identifies the signer, not you.
                "issuer": issuer.get("id") if isinstance(issuer, dict) else issuer,
                # Reported back so a URI change shows up as data, not as a bug.
                "extension": extension,
            },
        }

    return {"self_asserted": self_asserted, "presentation": None}


def describe(identity: dict[str, Any]) -> str:
    """Say which of the three arrived. That contrast is the lesson."""
    self_asserted, presentation = identity["self_asserted"], identity["presentation"]
    lines = []

    if self_asserted:
        told = ", ".join(f"{k}={v!r}" for k, v in self_asserted.items())
        lines.append(f"CASE 1 - SELF-ASSERTED. Your client told me, unsigned and unchecked: {told}")
    else:
        lines.append("CASE 1 - SELF-ASSERTED: absent. Your client sent no self-description.")

    if presentation is None:
        lines.append(
            "CASE 3 - NOTHING SIGNED. Your gateway vouched for nothing on this call, so nothing in "
            "it is verifiable. Before you configure an Identity element on the inbound leg, this is "
            "the expected result rather than a fault."
        )
        return "\n".join(lines)

    lines.append(f"CASE 2 - GATEWAY-SIGNED. A presentation arrived under {presentation['extension']}.")
    lines.append(f"  caller DID: {presentation['did'] or '(the presentation named none)'}")
    if presentation["identity_fields"]:
        signed = ", ".join(f"{k}={v!r}" for k, v in presentation["identity_fields"].items())
        lines.append(f"  fields it hashed into that DID: {signed}")
    lines.append(f"  signed by: {presentation['issuer'] or '(unstated)'} - which is your own gateway")
    lines.append(
        "  I checked that a proof is present. I did not verify it, and it would not tell me who you "
        "are if I had: you control the gateway that signed it, over fields your own client sent. "
        "Evidence that identity was configured, and evidence of nothing else."
    )
    return "\n".join(lines)


class IdentityMirrorExecutor(AgentExecutor):
    """The server side of A2A, in one class — and the half of it you write.

    An executor is the whole contract. A2A hands you the request and an event
    queue, and you publish what happens onto that queue; **you do not return a
    value**. That is the protocol's central choice, and the reason the client
    prints `kind: task` instead of a result: a call becomes a task with a
    lifecycle, which can be polled, answered over several turns, or cancelled.

    Subclass it, implement these two methods, hand it to a request handler (see
    `__main__.py`), and you have an agent. Everything else — routing, the card
    endpoint, task storage, the JSON-RPC envelope — the SDK does.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # `context` is the request, already parsed. Three things on it:
        #
        #   context.message           what arrived, whole — parts and metadata
        #   context.get_user_input()  the text parts of it, joined, when that is
        #                             all you need
        #   context.task_id /         assigned for you: a new task per message,
        #   context.context_id        one context threaded across a conversation.
        #                             Step 4 is watching one change and one hold
        #
        # Everything the gateway signed is in `message.metadata`, which is why
        # identity is readable here at all — it rides with the message rather
        # than in a header the agent would have to be told about.
        message = context.message
        identity = read_caller_identity(message.metadata if message else None)

        # `TaskUpdater` is how you publish a task's progress onto the queue.
        # This agent answers in one turn, so it goes straight to `completed`.
        # The other endings, all one call each:
        #
        #   await updater.start_work()             -> 'working', before a long job
        #   await updater.requires_input(reply,
        #                                final=True)  -> 'input-required': ask a
        #                                             question and stop, then pick
        #                                             the answer up on the next
        #                                             message in this context. No
        #                                             MCP equivalent exists.
        #                                             `final` closes the stream,
        #                                             which a non-streaming agent
        #                                             wants
        #   await updater.failed(reply)            -> 'failed'
        #   await updater.add_artifact([...])      -> a named output alongside
        #                                             the reply, for results a
        #                                             caller keeps rather than
        #                                             reads
        #
        # A streaming agent calls these as it goes and the client watches the
        # task change state; this card advertises `streaming=False`, so the
        # client gets one final task instead.
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        reply = updater.new_agent_message(
            [Part(root=TextPart(kind="text", text=describe(identity)))],
            # The agent's own descriptor on the way out, which is what a
            # response-leg Identity element reads to derive a DID for the agent.
            #
            # Flat under the extension URI, and NOT wrapped in `agentIdentity`:
            # that element is configured with an empty meta field to match. Wrap
            # it here and every `identityFields` comes back with dotted keys.
            metadata={SELF_ASSERTED_EXTENSION: dict(AGENT_IDENTITY)},
        )
        # Declaring which extensions this reply uses. Advertised on the card,
        # named again here on the message that actually carries one.
        reply.extensions = [SELF_ASSERTED_EXTENSION]
        await updater.complete(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Required by the interface, and honest to refuse: an agent that answers
        # in one turn has nothing to interrupt. A long-running one would stop its
        # work here and publish `canceled`.
        raise Exception("cancel not supported")
