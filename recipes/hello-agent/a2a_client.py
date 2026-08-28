#!/usr/bin/env python3
"""
A2A client for the Agent Lab's "Hello, agent" recipe.

Sends a message to an A2A agent and prints what came back, in full. You point
it at the access point of a surface on your OWN Agent Gateway; the gateway
holds the target's API key and forwards to the Lab-hosted agent behind it. This
client holds no credential for the agent and never will — that is the point.

The client is deliberately dumb. There is no model in it and nothing
non-deterministic: everything interesting in the output was put there by the
gateway, and a caller that reasoned about it would make that impossible to see.

Derived from Affinidi's a2a/a2a_client.py
  https://github.com/affinidi/affinidi-labs-tgw-get-started
  upstream commit a516a170be9e3e68a1f54592e128af1c331df37a (2026-07-15)
  Licensed under the Apache License, Version 2.0. See ../../NOTICE.

The identity extension URI and the shape of the metadata envelope below are
carried over byte for byte, because the gateway matches on them. Everything
else is adapted — see PROVENANCE.md for the list and the reasoning.

Copyright 2026 MISSION. Licensed under the Apache License, Version 2.0.
"""

import argparse
import asyncio
import json
import logging
import os
import pathlib
import sys
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest, TextPart

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("a2a-client")

# --- Extension URIs. Vendored verbatim; the gateway matches on these strings.

# What this client declares about itself. Your gateway's inbound Identity
# element reads the descriptor under this key and mints a DID from the fields
# your schema marks with "x-identity": true.
IDENTITY_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity/v1"

# What the gateway attaches to the reply, once the response leg carries an
# Identity element. Not something this client sends.
CREDENTIAL_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity-credential/v1"

# What the gateway attaches to your message on the way in. You never see this
# one from here — it is added after you send and consumed by the agent, which
# reports what it saw. Named so the recipe's three URIs sit together.
BINDING_EXT_URI = "https://fabric.affinidi.io/extensions/agent-identity-binding/v1"

# Task states where the agent has stopped and is waiting on the caller, rather
# than finishing. Answering one means continuing the SAME task, so the agent can
# match what you say against what it already received.
WAITING_STATES = ("input-required", "auth-required")

DEFAULT_AGENT_NAME = "A2A Test Client"
DEFAULT_AGENT_VERSION = "1.0.0"

RULE = "=" * 68


def build_message_payload(
    text: str,
    agent_name: str,
    agent_version: str,
    context_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    """Build the A2A message, with this client's self-description attached.

    The metadata envelope is upstream's, unchanged: the descriptor nests under
    `agentIdentity`, which is why the inbound Identity element needs its meta
    field set to `agentIdentity` rather than left empty.

    Note what is NOT marked as an identity field by the schema you will paste:
    `version` is sent, and deliberately not extracted. A DID that changes every
    time you bump a version number identifies nothing.
    """
    message: dict[str, Any] = {
        "role": "user",
        "parts": [TextPart(kind="text", text=text).model_dump()],
        "messageId": uuid4().hex,
        "extensions": [IDENTITY_EXT_URI],
        "metadata": {
            IDENTITY_EXT_URI: {
                "agentIdentity": {
                    "name": agent_name,
                    "version": agent_version,
                }
            }
        },
    }

    # Upstream sends every message cold. Carrying the ids back is what makes an
    # A2A task legible as a task: reuse `contextId` and the conversation
    # continues, while each turn gets a `taskId` of its own.
    if context_id:
        message["contextId"] = context_id
    if task_id:
        message["taskId"] = task_id

    return {"message": message}


def _unwrap(response_json: dict[str, Any]) -> dict[str, Any] | None:
    """Return the JSON-RPC result, or None if the agent returned an error."""
    return response_json.get("result")


def _reply_message(result: dict[str, Any]) -> dict[str, Any] | None:
    """The agent's reply, whether the result is a task or a bare message."""
    if result.get("kind") == "message":
        return result
    status_message = (result.get("status") or {}).get("message")
    if status_message:
        return status_message
    history = result.get("history") or []
    for entry in reversed(history):
        if entry.get("role") == "agent":
            return entry
    return None


def _reply_text(message: dict[str, Any] | None) -> str:
    if not message:
        return ""
    chunks = [p.get("text", "") for p in message.get("parts", []) if p.get("kind") == "text"]
    return "\n".join(c for c in chunks if c)


def _presentation(credential: dict[str, Any]) -> dict[str, Any]:
    """The verifiable presentation, however the gateway chose to send it.

    A live surface serialises `verifiablePresentation` to a JSON string; the
    replay fixture carries it as an object. Same document either way, so parse
    the string form rather than letting it reach `.get` as a str.
    """
    vp = credential.get("verifiablePresentation") or {}
    if isinstance(vp, str):
        try:
            vp = json.loads(vp)
        except json.JSONDecodeError:
            return {}
    return vp if isinstance(vp, dict) else {}


def report(response_json: dict[str, Any], show_raw: bool = True) -> dict[str, str | None]:
    """Print the envelope, then name the things worth looking at.

    Returns the ids, so an interactive session can carry them into the next
    message.
    """
    if show_raw:
        print("\n" + RULE)
        print("THE FULL ENVELOPE  — everything that came back, unedited")
        print(RULE)
        print(json.dumps(response_json, indent=2, sort_keys=True))

    result = _unwrap(response_json)
    if result is None:
        print("\n" + RULE)
        print("The agent returned a JSON-RPC error rather than a result.")
        print(RULE + "\n")
        return {"context_id": None, "task_id": None, "state": None}

    message = _reply_message(result)
    text = _reply_text(message)

    print("\n" + RULE)
    print("WHAT THE AGENT SAID")
    print(RULE)
    print(text or "(no text parts in the reply)")

    print("\n" + RULE)
    print("THE ENVELOPE AROUND IT")
    print(RULE)
    # A2A hands back a task with state, where MCP hands back a return value.
    print(f"  kind        {result.get('kind')}")
    print(f"  state       {(result.get('status') or {}).get('state')}")
    print(f"  taskId      {result.get('id')}")
    print(f"  contextId   {result.get('contextId')}")
    print(f"  history     {len(result.get('history') or [])} message(s)")

    print("\n" + RULE)
    print("WHAT YOUR GATEWAY ADDED")
    print(RULE)
    credential = (message or {}).get("metadata", {}).get(CREDENTIAL_EXT_URI)
    if not credential:
        print("  Nothing. No response-leg credential arrived.")
        print()
        print("  Expected before step 8 — the reply is just the agent's own")
        print("  unsigned self-description, which is what an ungoverned")
        print("  exchange looks like. After step 8, this means the Identity")
        print("  element is on the Managed Agent node rather than on the")
        print("  response leg, or you are calling the agent directly rather")
        print("  than through your access point.")
    else:
        print(f"  Holder DID  {credential.get('did')}")
        subject = (
            _presentation(credential)
            .get("verifiableCredential", {})
            .get("credentialSubject", {})
        )
        binding = subject.get("workloadBinding")
        if binding:
            print()
            print("  A workload binding. Not a description of the agent — a signed")
            print("  record of THIS request: which agent acted, for which caller.")
            print()
            for line in json.dumps(binding, indent=2, sort_keys=True).splitlines():
                print(f"    {line}")
            caller = (binding.get("userIdentity") or {}).get("id")
            if caller:
                print()
                print("  userIdentity.id is the DID your gateway minted on the INBOUND")
                print("  leg — your DID, not the agent's. Compare it with the caller")
                print("  DID the agent reports above. They are the same, and nothing")
                print("  either side wrote joined them:")
                print()
                print(f"    {caller}")
        elif subject.get("identityFields"):
            print()
            print("  identityFields, rather than a workload binding:")
            print()
            for line in json.dumps(subject["identityFields"], indent=2, sort_keys=True).splitlines():
                print(f"    {line}")
            print()
            print("  Dotted keys here mean the meta field is still set on the")
            print("  response leg. The agent sends its descriptor flat, so that")
            print("  field must be empty.")
    print(RULE + "\n")

    state = (result.get("status") or {}).get("state")
    if state in WAITING_STATES:
        print("The agent is waiting on you. Answer in the same task:")
        print(f"  --context-id {result.get('contextId')} --task-id {result.get('id')}")
        print("(the prompt below does this for you)\n")

    return {
        "context_id": result.get("contextId"),
        "task_id": result.get("id"),
        "state": state,
    }


async def send(
    client: A2AClient,
    text: str,
    agent_name: str,
    agent_version: str,
    context_id: str | None,
    task_id: str | None,
    show_raw: bool,
) -> dict[str, str | None]:
    request = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(
            **build_message_payload(text, agent_name, agent_version, context_id, task_id)
        ),
    )
    response = await client.send_message(request)
    return report(response.model_dump(mode="json", exclude_none=True), show_raw)


async def resolve_card(httpx_client: httpx.AsyncClient, url: str):
    resolver = A2ACardResolver(httpx_client=httpx_client, base_url=url)
    return await resolver.get_agent_card()


def _host(url: str) -> str:
    return urlparse(url).netloc


def describe_card(card, called_url: str) -> None:
    print("\n" + RULE)
    print("THE AGENT CARD")
    print(RULE)
    print(json.dumps(card.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True))
    print(RULE)
    print(f"  Name        {card.name}")
    print(f"  Version     {card.version}")
    print(f"  url         {card.url}")
    if _host(card.url) == _host(called_url):
        print("              ^ the same address you called. Called through a")
        print("                surface, that means your gateway rewrote the card")
        print("                it served you: discovery itself now routes through")
        print("                the governed door, and the Lab's address for this")
        print("                agent never reached you.")
    else:
        print(f"              ^ NOT the address you called ({_host(called_url)}).")
        print("                Messages will go to the card's url, not yours. If")
        print("                that address is the Lab's, your surface is serving")
        print("                the card through without rewriting it.")
    if card.skills:
        print("  Skills:")
        for skill in card.skills:
            print(f"    - {skill.name}: {skill.description}")
        print("              ^ prose, not JSON Schema. Put this beside the")
        print("                tools/list output from hello-gateway: MCP")
        print("                advertises typed functions for your model to")
        print("                pick between, A2A advertises what an agent can")
        print("                do and leaves the how to the agent.")
    if card.capabilities and card.capabilities.extensions:
        print("  Extensions:")
        for ext in card.capabilities.extensions:
            print(f"    - {ext.uri} (required: {ext.required})")
    print(RULE + "\n")


def retarget_local_card(card, called_url: str) -> None:
    """Point a card advertising localhost at the address actually called.

    Only fires when you are running the agent yourself — the debugging path in
    README.md, not the recipe. A card served through a surface already names
    the gateway, and a mismatch there is a finding rather than something to
    paper over.
    """
    if _host(card.url) == _host(called_url):
        return
    if "localhost" not in card.url and "127.0.0.1" not in card.url:
        return
    card.url = called_url if called_url.endswith("/") else called_url + "/"
    logger.info("Card advertised localhost; sending to %s instead", card.url)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="a2a_client.py",
        description="Call an A2A agent through your own Agent Gateway access point.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=os.environ.get("A2A_ACCESS_POINT"),
        help="Your surface's access point URL. Defaults to $A2A_ACCESS_POINT.",
    )
    parser.add_argument(
        "-m",
        "--message",
        help="Send one message and exit, instead of opening the prompt.",
    )
    parser.add_argument(
        "--card",
        action="store_true",
        help="Print the agent card and exit.",
    )
    parser.add_argument(
        "--context-id",
        help="Continue an existing conversation. Printed by the previous call.",
    )
    parser.add_argument(
        "--task-id",
        help="Continue an existing task, e.g. answering an input-required turn.",
    )
    parser.add_argument(
        "--agent-name",
        default=os.environ.get("A2A_AGENT_NAME", DEFAULT_AGENT_NAME),
        help=(
            "The name this client presents for itself. Your gateway hashes it "
            "into your DID, so changing it gives you a different DID. "
            f"Default: {DEFAULT_AGENT_NAME!r}."
        ),
    )
    parser.add_argument(
        "--agent-version",
        default=os.environ.get("A2A_AGENT_VERSION", DEFAULT_AGENT_VERSION),
        help="Sent, and deliberately not an identity field. Default: 1.0.0.",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Suppress the full JSON envelope and print only the summary.",
    )
    parser.add_argument(
        "--replay",
        help=(
            "Render a saved envelope from a file instead of calling anything. "
            "Try fixtures/example-response.json to see what a configured "
            "surface produces."
        ),
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS verification. For a local agent over plain HTTP only.",
    )
    return parser.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = parse_args(argv)

    show_raw = not args.no_raw

    if args.replay:
        saved = pathlib.Path(args.replay)
        if not saved.is_file():
            print(f"No such file: {saved}", file=sys.stderr)
            return 2
        report(json.loads(saved.read_text()), show_raw)
        return 0

    if not args.url:
        print(
            "No access point given. Pass it as an argument or set "
            "A2A_ACCESS_POINT in .env — see README.md step 2.",
            file=sys.stderr,
        )
        return 2

    async with httpx.AsyncClient(verify=not args.insecure, timeout=60.0) as httpx_client:
        try:
            logger.info("Fetching the agent card through %s", args.url)
            card = await resolve_card(httpx_client, args.url)
        except Exception as exc:  # noqa: BLE001 - the failure is the diagnostic
            print(f"\nCould not fetch the agent card: {exc}\n", file=sys.stderr)
            print(
                "The card sits at <access point>/.well-known/agent-card.json. A "
                "failure here is your surface, not the agent — see the "
                "troubleshooting table in README.md.",
                file=sys.stderr,
            )
            return 1

        retarget_local_card(card, args.url)
        describe_card(card, args.url)

        if args.card:
            return 0

        client = A2AClient(httpx_client=httpx_client, agent_card=card)

        if args.message:
            await send(
                client,
                args.message,
                args.agent_name,
                args.agent_version,
                args.context_id,
                args.task_id,
                show_raw,
            )
            return 0

        print("Type a message. 'exit' or Ctrl-C to stop.\n")
        context_id, task_id = args.context_id, args.task_id
        while True:
            try:
                text = input("you > ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

            if not text:
                continue
            if text.lower() in ("exit", "quit", "q"):
                return 0

            try:
                ids = await send(
                    client,
                    text,
                    args.agent_name,
                    args.agent_version,
                    context_id,
                    task_id,
                    show_raw,
                )
                # Keep the context so the next message continues the
                # conversation. Drop the task so the next message opens a new
                # one — unless the agent is waiting on this one, where the
                # whole point is that the answer arrives inside the task it
                # asked in.
                context_id = ids["context_id"] or context_id
                task_id = ids["task_id"] if ids["state"] in WAITING_STATES else None
            except Exception as exc:  # noqa: BLE001
                logger.error("%s", exc)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main(sys.argv[1:])))
    except KeyboardInterrupt:
        pass
